from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from products.models import CITY_CHOICES
from vendorpulse_core.pagination import paginate_queryset
from .models import Zone, DeliveryHub

CITY_CHOICES_VALUES = [c[0] for c in CITY_CHOICES]


def hub_for_city(city):
    if not city:
        return None
    return DeliveryHub.objects.filter(city=city, is_active=True).first()


def zone_for_pincode(pincode_str):
    if not pincode_str or not str(pincode_str).strip().isdigit() or len(str(pincode_str).strip()) != 6:
        return None
    return Zone.objects.filter(
        is_active=True,
        pincode_from__lte=int(pincode_str),
        pincode_to__gte=int(pincode_str),
    ).first()


def _validate_zone_payload(data, instance=None):
    """Return (cleaned_fields, error_response). Shared by create and update."""
    city = data.get('city', getattr(instance, 'city', None))
    name = str(data.get('name') or getattr(instance, 'name', '') or '').strip()
    try:
        pincode_from = int(data.get('pincode_from', getattr(instance, 'pincode_from')))
        pincode_to = int(data.get('pincode_to', getattr(instance, 'pincode_to')))
    except (TypeError, ValueError):
        return None, Response({"error": "pincode_from and pincode_to must be integers."},
                              status=status.HTTP_400_BAD_REQUEST)

    if city not in CITY_CHOICES_VALUES:
        return None, Response({"error": f"A valid city is required: {CITY_CHOICES_VALUES}."},
                              status=status.HTTP_400_BAD_REQUEST)
    if not name:
        return None, Response({"error": "A zone name is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not (100000 <= pincode_from <= 999999 and 100000 <= pincode_to <= 999999):
        return None, Response({"error": "Pincode bounds must be 6-digit numbers."}, status=status.HTTP_400_BAD_REQUEST)
    if pincode_from > pincode_to:
        return None, Response({"error": "pincode_from must be <= pincode_to."}, status=status.HTTP_400_BAD_REQUEST)

    clash = Zone.objects.filter(city=city, name=name).exclude(pk=getattr(instance, 'pk', None))
    if clash.exists():
        return None, Response({"error": f"Zone '{name}' already exists in {city}."},
                              status=status.HTTP_400_BAD_REQUEST)
    overlap = Zone.objects.filter(
        city=city, is_active=True,
        pincode_from__lte=pincode_to, pincode_to__gte=pincode_from,
    ).exclude(pk=getattr(instance, 'pk', None))
    if overlap.exists():
        return None, Response(
            {"error": f"Pincode range overlaps with {overlap.first().name} in {city}."},
            status=status.HTTP_400_BAD_REQUEST)

    return {'city': city, 'name': name, 'pincode_from': pincode_from, 'pincode_to': pincode_to}, None


@api_view(['GET'])
@permission_classes([AllowAny])
def resolve_zone_api(request):
    """GET /locations/zones/resolve/?pincode=400051 -> city + zone for the pincode."""
    pincode = str(request.GET.get('pincode') or '').strip()
    if not pincode.isdigit() or len(pincode) != 6:
        return Response({"error": "A valid 6-digit pincode is required."}, status=status.HTTP_400_BAD_REQUEST)

    zone = zone_for_pincode(pincode)
    if zone is None:
        return Response({"error": "We don't deliver to this pincode yet."},
                        status=status.HTTP_404_NOT_FOUND)

    return Response({
        "zone_id": zone.id,
        "zone_name": zone.name,
        "city": zone.city,
        "pincode": pincode,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_zones_api(request):
    """GET /locations/zones/?city=Mumbai -> active zones of one city (zone pickers)."""
    city = request.GET.get('city')
    zones = Zone.objects.filter(is_active=True)
    if city:
        if city not in CITY_CHOICES_VALUES:
            return Response({"error": "Unknown city."}, status=status.HTTP_400_BAD_REQUEST)
        zones = zones.filter(city=city)
    return Response({
        "results": [{
            "id": z.id,
            "city": z.city,
            "name": z.name,
            "pincode_from": z.pincode_from,
            "pincode_to": z.pincode_to,
        } for z in zones],
    }, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_zones_api(request):
    """Admin zone management: paginated list (?city= filter, with agent counts) + create."""
    if request.method == 'GET':
        zones = Zone.objects.select_related().all()
        city = request.GET.get('city')
        if city and city in CITY_CHOICES_VALUES:
            zones = zones.filter(city=city)
        rows, meta, _ = paginate_queryset(zones.order_by('city', 'pincode_from'), request)

        from django.contrib.auth.models import User
        from django.db.models import Count, Q
        agent_counts = {
            p['zone_id']: p['n']
            for p in User.objects.filter(profile__zone__isnull=False).values('zone_id')
            .annotate(n=Count('id', filter=Q(profile__is_delivery_agent=True)))
        }
        data = [{
            "id": z.id,
            "city": z.city,
            "name": z.name,
            "pincode_from": z.pincode_from,
            "pincode_to": z.pincode_to,
            "is_active": z.is_active,
            "agents": agent_counts.get(z.id, 0),
        } for z in rows]
        return Response({**meta, "results": data}, status=status.HTTP_200_OK)

    cleaned, err = _validate_zone_payload(request.data)
    if err:
        return err
    zone = Zone.objects.create(is_active=True, **cleaned)
    return Response({"message": "Zone created.", "zone": {"id": zone.id, "city": zone.city,
                                                          "name": zone.name}}, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_zone_detail_api(request, pk):
    try:
        zone = Zone.objects.get(pk=pk)
    except Zone.DoesNotExist:
        return Response({"error": "Zone not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        zone.is_active = False    # deactivate, never hard-delete: FKs may reference it
        zone.save()
        return Response({"message": "Zone deactivated."}, status=status.HTTP_200_OK)

    cleaned, err = _validate_zone_payload(request.data, instance=zone)
    if err:
        return err
    for field, value in cleaned.items():
        setattr(zone, field, value)
    zone.save()
    return Response({"message": "Zone updated.", "zone": {"id": zone.id, "city": zone.city,
                                                          "name": zone.name}}, status=status.HTTP_200_OK)


def _validate_hub_payload(data, instance=None):
    """Return (cleaned_fields, error_response). Shared by hub create and update."""
    city = data.get('city', getattr(instance, 'city', None))
    name = str(data.get('name') or getattr(instance, 'name', '') or '').strip()
    address = str(data.get('address') or getattr(instance, 'address', '') or '').strip()
    zone_id = data.get('zone', getattr(instance, 'zone_id', None)) or None

    if city not in CITY_CHOICES_VALUES:
        return None, Response({"error": f"A valid city is required: {CITY_CHOICES_VALUES}."},
                              status=status.HTTP_400_BAD_REQUEST)
    if not name:
        return None, Response({"error": "A hub name is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not address:
        return None, Response({"error": "A hub address is required."}, status=status.HTTP_400_BAD_REQUEST)
    if len(address) > 255:
        return None, Response({"error": "Hub address must be 255 characters or fewer."},
                              status=status.HTTP_400_BAD_REQUEST)

    zone = None
    if zone_id:
        zone = Zone.objects.filter(pk=zone_id).first()
        if zone is None:
            return None, Response({"error": "Zone not found."}, status=status.HTTP_400_BAD_REQUEST)
        if zone.city != city:
            return None, Response({"error": f"The selected zone belongs to {zone.city}, not {city}."},
                                  status=status.HTTP_400_BAD_REQUEST)

    clash = DeliveryHub.objects.filter(city=city, name=name).exclude(pk=getattr(instance, 'pk', None))
    if clash.exists():
        return None, Response({"error": f"Hub '{name}' already exists in {city}."},
                              status=status.HTTP_400_BAD_REQUEST)

    return {'city': city, 'name': name, 'address': address, 'zone': zone}, None


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_hubs_api(request):
    """Admin hub management: list (?city= filter) + create. Small dataset,
    so the list is unpaginated and grouped client-side."""
    if request.method == 'GET':
        hubs = DeliveryHub.objects.select_related('zone').all()
        city = request.GET.get('city')
        if city and city in CITY_CHOICES_VALUES:
            hubs = hubs.filter(city=city)
        data = [{
            "id": h.id,
            "city": h.city,
            "name": h.name,
            "address": h.address,
            "zone": h.zone_id,
            "zone_name": h.zone.name if h.zone else '',
            "is_active": h.is_active,
        } for h in hubs]
        return Response({"results": data}, status=status.HTTP_200_OK)

    cleaned, err = _validate_hub_payload(request.data)
    if err:
        return err
    hub = DeliveryHub.objects.create(is_active=True, **cleaned)
    return Response({"message": "Hub created.", "hub": {"id": hub.id, "city": hub.city,
                                                        "name": hub.name}}, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_hub_detail_api(request, pk):
    try:
        hub = DeliveryHub.objects.get(pk=pk)
    except DeliveryHub.DoesNotExist:
        return Response({"error": "Hub not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        hub.is_active = False    # deactivate, never hard-delete (referenced in flows)
        hub.save()
        return Response({"message": "Hub deactivated."}, status=status.HTTP_200_OK)

    cleaned, err = _validate_hub_payload(request.data, instance=hub)
    if err:
        return err
    for field, value in cleaned.items():
        setattr(hub, field, value)
    hub.save()
    return Response({"message": "Hub updated.", "hub": {"id": hub.id, "city": hub.city,
                                                        "name": hub.name}}, status=status.HTTP_200_OK)
