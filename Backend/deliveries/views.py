from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from django.contrib.auth.models import User, Group
from django.db import transaction
from vendorpulse_core.pagination import paginate_queryset as _paginate_queryset
from vendorpulse_core.throttles import OtpVerifyThrottle
from django.db.models import Count, Sum, Q, Avg
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from vendorpulse_core.pricing import money
from orders.models import Order, OrderItem
from orders.models import Dispute, ReturnRequest
from accounts.models import Profile
from products.models import CITY_CHOICES
from products.models import Item as ProductItem
from locations.models import Zone
from notifications.utils import notify
from locations.views import hub_for_city
from orders.signals import is_intercity, assign_delivery_leg
from deliveries.linehaul import (
    linehaul_eta_hours, stamp_linehaul_departure, _notify_arrival,
    settle_linehaul_arrivals,
)

STATUS_LABELS = dict(OrderItem.ORDER_STATUS_CHOICES)

# In-flight statuses shared by analytics + agent utilization (both city legs
# of the fulfillment ladder: intra-city and the intercity hub flow).
ACTIVE_STATUSES = ['PICKUP_SCHEDULED', 'PICKED_UP', 'DISPATCHED',
                   'DROPPED_AT_ORIGIN_HUB', 'IN_TRANSIT', 'AT_DESTINATION_HUB']


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_delivery_list(request):
    # Timed line-haul: materialize any hub arrivals whose ETA has elapsed
    # before rendering statuses (lazy settlement - no scheduler needed).
    settle_linehaul_arrivals()

    order_items = OrderItem.objects.select_related(
        'order', 'seller', 'seller__profile', 'assigned_agent', 'delivery_agent',
        'item', 'order__shipping_zone'
    ).order_by('-id')

    group = request.GET.get('status_group')
    if group == 'active':
        order_items = order_items.exclude(status__in=['DELIVERED', 'CANCELLED'])
    elif group == 'completed':
        order_items = order_items.filter(status='DELIVERED')
    elif group == 'cancelled':
        order_items = order_items.filter(status='CANCELLED')

    # Tracking-ID search inside the current group. Scoped strictly to
    # tracking_number ("TRK-<order_id>"): partial matches work, and it
    # composes with the group filter before pagination so `count` reflects
    # the matches.
    search = (request.GET.get('search') or '').strip()
    if search:
        order_items = order_items.filter(tracking_number__icontains=search)

    active_count = OrderItem.objects.exclude(status__in=['DELIVERED', 'CANCELLED']).count()
    completed_count = OrderItem.objects.filter(status='DELIVERED').count()
    cancelled_count = OrderItem.objects.filter(status='CANCELLED').count()

    rows, meta, all_requested = _paginate_queryset(order_items, request)

    data = []
    for item in rows:
        # Fetch seller's city/address from their Profile model safely
        seller_city = getattr(item.seller, 'profile', None) and getattr(item.seller.profile, 'city', '') or 'N/A'
        
        data.append({
            "id": item.id,
            "order_id": item.order.id,
            "shipping_address": item.order.shipping_address or 'N/A',
            "shipping_city": item.order.shipping_city or '',
            "phone": item.order.phone or 'N/A',
            "item_title": item.item_title,
            "item_price": str(item.item_price),
            "seller_username": item.seller.username,
            "seller_address": seller_city if seller_city else 'N/A', # Added seller address
            "pickup_address": (
                f"{item.item.address}, {item.item.location}"
                if item.item and item.item.address
                else (seller_city if seller_city else 'N/A')
            ),
            "status": item.status,
            "tracking_number": item.tracking_number or '',
            "cancel_reason": item.cancel_reason,
            "cancel_note": item.cancel_note,
            "agent_username": item.assigned_agent.username if item.assigned_agent else None,
            "assigned_agent": item.assigned_agent.id if item.assigned_agent else None,
            "delivery_agent": item.delivery_agent.id if item.delivery_agent else None,
            "delivery_agent_username": item.delivery_agent.username if item.delivery_agent else None,
            "pickup_zone": item.item.zone.name if (item.item and item.item.zone) else '',
            "shipping_zone": item.order.shipping_zone_name
                             or (item.order.shipping_zone.name if item.order.shipping_zone else ''),
            "pincode": item.order.pincode or '',
            "is_intercity": bool(item.item and item.item.location)
                            and item.order.shipping_city != item.item.location,
            "origin_hub": (hub_for_city(item.item.location).name
                           if (item.item and item.item.location and hub_for_city(item.item.location)) else ''),
            "destination_hub": (hub_for_city(item.order.shipping_city).name
                                if (item.order.shipping_city and hub_for_city(item.order.shipping_city)) else ''),
            "seller_id": item.seller.id,
            "is_seller_verified": bool(getattr(item.seller, 'profile', None) and item.seller.profile.is_verified),
            # Timed line-haul: when this in-transit item is expected to arrive
            # at the destination hub (ISO string; admin UI shows the ETA).
            "linehaul_eta_at": item.linehaul_eta_at.isoformat() if item.linehaul_eta_at else None,
            # Money snapshot for this item (see vendorpulse_core.pricing):
            # the buyer's delivery fee, the seller's 5% commission + payout,
            # and what the agents earn across both legs.
            "item_subtotal": str(item.item_price),
            "delivery_charge": str(item.delivery_charge),
            "platform_fee": str(item.platform_fee),
            "seller_payout": str(item.seller_payout),
            "agent_pay": str(item.agent_pay_total),
            "platform_earnings": str(money(
                item.platform_fee + item.delivery_charge
                - item.pickup_agent_pay - item.delivery_agent_pay)),
            "return_status": (item.return_request.status
                              if getattr(item, 'return_request', None) else None),
        })

    # ?all=1 keeps the legacy flat-list shape (frontend Sellers tab);
    # normal calls get the pagination envelope.
    if all_requested:
        return Response(data, status=status.HTTP_200_OK)

    meta["active_count"] = active_count
    meta["completed_count"] = completed_count
    meta["cancelled_count"] = cancelled_count
    return Response({**meta, "results": data}, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_assign_delivery(request, pk):
    try:
        item = OrderItem.objects.get(pk=pk)
    except OrderItem.DoesNotExist:
        return Response({"error": "Order item not found."}, status=status.HTTP_404_NOT_FOUND)

    agent_id = request.data.get('assigned_agent')
    tracking_number = request.data.get('tracking_number')

    if agent_id:
        try:
            agent = User.objects.get(pk=agent_id)
            item.assigned_agent = agent
        except User.DoesNotExist:
            return Response({"error": "Agent not found."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        item.assigned_agent = None

    # Optional leg-2 override: for intercity items an admin can pick the
    # delivery agent in the buyer's city (auto-assignment stays the default).
    d_agent = None
    if 'delivery_agent' in request.data:
        delivery_agent_id = request.data.get('delivery_agent')
        if delivery_agent_id:
            try:
                d_agent = User.objects.get(pk=delivery_agent_id)
                item.delivery_agent = d_agent
            except User.DoesNotExist:
                return Response({"error": "Delivery agent not found."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            item.delivery_agent = None

    if tracking_number is not None:
        item.tracking_number = tracking_number

    item.save()

    if d_agent:
        notify(
            d_agent,
            'NEW_TASK',
            f"You have been assigned DELIVERY of '{item.item_title}' to the buyer in "
            f"{item.order.shipping_city} - {item.order.shipping_zone_name or ''} "
            f"({item.tracking_number or 'TRK pending'}). Collect the buyer's 4-digit OTP.",
            order_item=item,
        )

    if item.assigned_agent:
        notify(
            item.assigned_agent,
            'NEW_TASK',
            f"You have been assigned delivery of '{item.item_title}' "
            f"({item.tracking_number or 'TRK pending'})",
            order_item=item,
        )
        if item.status == 'ORDER_PLACED':
            item.status = 'PICKUP_SCHEDULED'
            item.save()
            notify(
                item.order.user,
                'STATUS_UPDATE',
                f"Order '{item.item_title}': VendorPulse pickup has been scheduled.",
                order_item=item,
            )
    notify(
        item.order.user,
        'AGENT_ASSIGNED',
        f"Update on your order '{item.item_title}': a delivery agent has been assigned. "
        f"Tracking: {item.tracking_number or 'pending'}",
        order_item=item,
    )

    return Response({"message": "Delivery assignment updated successfully!"}, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_order_update(request, pk):
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

    shipping_city = request.data.get('shipping_city')
    shipping_address = request.data.get('shipping_address')
    phone = request.data.get('phone')

    if shipping_city is not None:
        if shipping_city not in [c[0] for c in CITY_CHOICES]:
            return Response({"error": "Invalid shipping city."}, status=status.HTTP_400_BAD_REQUEST)
        order.shipping_city = shipping_city

    if shipping_address is not None:
        if not shipping_address.strip():
            return Response({"error": "Shipping address cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
        order.shipping_address = shipping_address.strip()

    if phone is not None:
        if not phone.strip():
            return Response({"error": "Phone number cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
        order.phone = phone.strip()

    order.save()

    notify(
        order.user,
        'ORDER_UPDATED',
        f"Shipping details of your order (TRK items) were updated by VendorPulse support. "
        f"Now: {order.shipping_address}, {order.shipping_city}, {order.phone}.",
    )

    return Response({
        "message": "Order updated successfully!",
        "order_id": order.id,
        "shipping_city": order.shipping_city,
        "shipping_address": order.shipping_address,
        "phone": order.phone,
    }, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def admin_fulfillment_status(request, pk):
    """
    Line-haul control for INTERCITY orders (the hub flow's admin leg):
      IN_TRANSIT         : item left the origin hub (DROPPED_AT_ORIGIN_HUB or
                           legacy DISPATCHED). Stamps the timed line-haul:
                           linehaul_departed_at/linehaul_eta_at are computed
                           from the HubRoute duration; when the ETA elapses
                           the item auto-arrives (settle_linehaul_arrivals).
      AT_DESTINATION_HUB : manual override - arrive the item early. Auto-
                           assigns a delivery agent in the buyer's city/zone
                           inside this transaction (None -> admin alert).
    """
    new_status = request.data.get('status')

    ALLOWED = {
        'IN_TRANSIT': ('DROPPED_AT_ORIGIN_HUB', 'DISPATCHED'),
        'AT_DESTINATION_HUB': ('IN_TRANSIT', 'DISPATCHED'),   # DISPATCHED = legacy pre-hub items
    }
    if new_status not in ALLOWED:
        return Response(
            {"error": "Admins can only set 'IN_TRANSIT' or 'AT_DESTINATION_HUB'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        try:
            order_item = OrderItem.objects.select_for_update().select_related(
                'order', 'item').get(pk=pk)
        except OrderItem.DoesNotExist:
            return Response({"error": "Order item not found."}, status=status.HTTP_404_NOT_FOUND)

        if not is_intercity(order_item):
            return Response(
                {"error": "This order does not travel between cities - agents handle it directly."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if order_item.status not in ALLOWED[new_status]:
            valid_previous = ' or '.join(
                STATUS_LABELS.get(s, s) for s in ALLOWED[new_status])
            return Response(
                {"error": f"Out of sequence: this order must first be marked "
                          f"'{valid_previous}' before it can become "
                          f"'{STATUS_LABELS.get(new_status, new_status)}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        order_item.status = new_status

        # Dispatching between hubs -> stamp the timed line-haul ETA so the
        # arrival happens automatically when the route duration elapses.
        eta_at = None
        transit_hours = None
        if new_status == 'IN_TRANSIT':
            transit_hours = linehaul_eta_hours(
                order_item.item.location if order_item.item else '',
                order_item.order.shipping_city,
            )
            eta_at = stamp_linehaul_departure(order_item)

        # Arrival in the buyer's city -> assign the local delivery agent
        # atomically (hub flow's replacement of the DISPATCHED handover).
        delivery_agent = None
        delivery_needs_assignment = False
        if new_status == 'AT_DESTINATION_HUB' and order_item.delivery_agent_id is None:
            delivery_agent = assign_delivery_leg(order_item)
            delivery_needs_assignment = delivery_agent is None

        order_item.save()

    # Notify only after the transition has committed
    if new_status == 'IN_TRANSIT':
        destination_city = order_item.order.shipping_city or 'the destination city'
        notify(
            order_item.order.user,
            'STATUS_UPDATE',
            f"Your order '{order_item.item_title}' ({order_item.tracking_number}) is on its way "
            f"from {order_item.item.location if order_item.item else 'the origin city'} to "
            f"{destination_city}. Expected to reach the {destination_city} hub by "
            f"{timezone.localtime(eta_at).strftime('%d %b, %I:%M %p')}.",
            order_item=order_item,
        )

    if new_status == 'AT_DESTINATION_HUB':
        _notify_arrival(order_item, delivery_agent, delivery_needs_assignment)

    return Response({
        "message": "Fulfillment status updated!",
        "id": order_item.id,
        "status": order_item.status,
        "delivery_agent": delivery_agent.username if delivery_agent else None,
        # Timed line-haul info (IN_TRANSIT dispatch): the admin UI shows when
        # the item will arrive at the destination hub by itself.
        "transit_hours": transit_hours,
        "linehaul_eta_at": timezone.localtime(eta_at).isoformat() if eta_at else None,
    }, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_staff_management(request):
    if request.method == 'GET':
        staff_users = User.objects.filter(is_staff=True) | User.objects.filter(groups__name='DeliveryAgent') | User.objects.filter(profile__is_delivery_agent=True)
        staff_users = staff_users.distinct().select_related('profile').prefetch_related('groups').order_by('id')

        rows, meta, all_requested = _paginate_queryset(staff_users, request)

        data = []
        for u in rows:
            city = getattr(u, 'profile', None) and getattr(u.profile, 'city', '') or 'N/A'
            profile_zone = getattr(u, 'profile', None) and u.profile.zone or None
            is_agent = (getattr(u, 'profile', None) and u.profile.is_delivery_agent) \
                or any(g.name == 'DeliveryAgent' for g in u.groups.all())
            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "address": city if city else 'N/A',
                "zone": profile_zone.id if profile_zone else None,
                "zone_name": profile_zone.name if profile_zone else '',
                "is_staff": u.is_staff,
                "is_agent": is_agent,
                "is_verified": getattr(u.profile, 'is_verified', False),
            })
        return Response({**meta, "results": data}, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email', '')
        city = request.data.get('address', '')
        role = request.data.get('role', 'agent')
        zone_id = request.data.get('zone')

        zone = None
        if zone_id:
            zone = Zone.objects.filter(pk=zone_id).first()
            if zone is None:
                return Response({"error": "Zone not found."}, status=status.HTTP_400_BAD_REQUEST)
            if city and zone.city != city:
                return Response({"error": f"The selected zone belongs to {zone.city}, not {city}."},
                                status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password, email=email)
        
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.city = city
        profile.zone = zone
        if role == 'agent':
            profile.is_delivery_agent = True
            group, _ = Group.objects.get_or_create(name='DeliveryAgent')
            user.groups.add(group)
        profile.save()

        if role == 'admin':
            user.is_staff = True
            user.save()

        return Response({"message": "Staff/Agent created successfully!"}, status=status.HTTP_201_CREATED)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_update_staff(request, pk):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({"error": "Staff member not found."}, status=status.HTTP_404_NOT_FOUND)

    email = request.data.get('email')
    city = request.data.get('address')
    role = request.data.get('role')

    if email is not None:
        user.email = email
    
    if role == 'admin':
        user.is_staff = True
        group = Group.objects.filter(name='DeliveryAgent').first()
        if group:
            user.groups.remove(group)
        if hasattr(user, 'profile'):
            user.profile.is_delivery_agent = False
            user.profile.save()
    elif role == 'agent':
        user.is_staff = False
        group, _ = Group.objects.get_or_create(name='DeliveryAgent')
        user.groups.add(group)
        if hasattr(user, 'profile'):
            user.profile.is_delivery_agent = True
            user.profile.save()

    user.save()

    if city is not None:
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.city = city
        profile.save()

    # Optional zone update: validated against the (possibly new) city.
    if 'zone' in request.data:
        zone_id = request.data.get('zone')
        if zone_id:
            zone = Zone.objects.filter(pk=zone_id).first()
            if zone is None:
                return Response({"error": "Zone not found."}, status=status.HTTP_400_BAD_REQUEST)
            profile, _ = Profile.objects.get_or_create(user=user)
            if profile.city and zone.city != profile.city:
                return Response({"error": f"The selected zone belongs to {zone.city}, not {profile.city}."},
                                status=status.HTTP_400_BAD_REQUEST)
            profile.zone = zone
        else:
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.zone = None
        profile.save()

    return Response({"message": "Staff profile updated successfully!"}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_delivery_list(request):
    # Timed line-haul: a due hub arrival may hand this agent a new task in
    # their city - settle before reading tasks so the card shows up now.
    settle_linehaul_arrivals()

    # Tasks for BOTH legs: items this agent must pick up / transport
    # (assigned_agent) AND intercity items waiting for their delivery
    # handover in the buyer's city (delivery_agent).
    order_items = OrderItem.objects.filter(
        Q(assigned_agent=request.user) | Q(delivery_agent=request.user)
    ).exclude(
        status='ORDER_PLACED'
    ).select_related(
        'order', 'seller', 'seller__profile', 'item', 'order__shipping_zone'
    ).order_by('-id')

    # Hub context per card: the pickup agent drops at the ORIGIN city hub;
    # the delivery agent collects from the BUYER's city hub. Cached per city
    # so a list of N tasks doesn't do 2N hub queries.
    hub_cache = {}

    def _hub_for(city):
        if not city:
            return None
        if city not in hub_cache:
            hub = hub_for_city(city)
            hub_cache[city] = ({"name": hub.name, "address": hub.address} if hub else None)
        return hub_cache[city]

    data = []
    for item in order_items:
        seller_city = getattr(item.seller, 'profile', None) and getattr(item.seller.profile, 'city', '') or 'N/A'
        intercity = bool(item.item and item.item.location) and item.order.shipping_city != item.item.location

        data.append({
            "id": item.id,
            "order_id": item.order.id,
            "shipping_address": item.order.shipping_address or 'N/A',
            "shipping_city": item.order.shipping_city or '',
            "shipping_zone": item.order.shipping_zone_name
                             or (item.order.shipping_zone.name if item.order.shipping_zone else ''),
            "pincode": item.order.pincode or '',
            "pickup_zone": item.item.zone.name if (item.item and item.item.zone) else '',
            "is_intercity": intercity,
            # Intercity handover points (null when a city has no active hub)
            "origin_hub": _hub_for(item.item.location if item.item else '') if intercity else None,
            "destination_hub": _hub_for(item.order.shipping_city) if intercity else None,
            "phone": item.order.phone or 'N/A',
            "item_title": item.item_title,
            "seller_username": item.seller.username,
            "seller_address": seller_city if seller_city else 'N/A',
            "pickup_address": (
                f"{item.item.address}, {item.item.location}"
                if item.item and item.item.address
                else (seller_city if seller_city else 'N/A')
            ),
            "status": item.status,
            "tracking_number": item.tracking_number or '',
            # Which leg this task is for the requesting agent (the UI shows a
            # "Delivery" badge for intercity handover tasks).
            "my_role": 'delivery' if item.delivery_agent_id == request.user.id else 'pickup',
            # What this agent earns for this task (snapshot from checkout):
            # the pickup leg fee, or the destination delivery-leg fee.
            "my_pay": str(item.delivery_agent_pay
                          if item.delivery_agent_id == request.user.id
                          else item.pickup_agent_pay),
        })
    return Response(data, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, OtpVerifyThrottle])
def agent_update_status(request, pk):
    new_status = request.data.get('status')

    # Row lock: two concurrent requests for the same item (e.g. a double-click)
    # serialize here. The second one re-reads the already-applied status and is
    # rejected by the ladder check instead of re-applying the transition and
    # firing a duplicate notification.
    with transaction.atomic():
        try:
            order_item = OrderItem.objects.select_for_update().select_related(
                'order', 'item').get(pk=pk)
        except OrderItem.DoesNotExist:
            return Response(
                {"error": "Order item not found or not assigned to you."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Context-aware fulfillment ladder: what an agent may do depends on
        # whether the order crosses cities.
        #   intra-city:  PICKUP_SCHEDULED -> PICKED_UP -> DISPATCHED -> DELIVERED
        #                (same agent delivers, OTP)
        #   intercity:   PICKED_UP -> DROPPED_AT_ORIGIN_HUB   (pickup agent's
        #                leg ENDS at their city's hub - they never carry items
        #                across cities)  ... admin line-haul ...  delivery
        #                agent collects from the buyer's-city hub -> DELIVERED
        # DISPATCHED stays valid for intercity DELIVERED as a legacy fallback
        # for items dispatched before the hub flow existed.
        intercity = is_intercity(order_item)
        required_statuses = None   # tuple; None means unknown/invalid status

        if new_status == 'DELIVERED':
            # Delivery leg: delivery_agent when one exists (intercity), else
            # the assigned agent (intra-city: same agent delivers).
            authorized = (order_item.delivery_agent_id == request.user.id
                          if order_item.delivery_agent_id
                          else order_item.assigned_agent_id == request.user.id)
            required_statuses = ('AT_DESTINATION_HUB', 'DISPATCHED') if intercity else ('DISPATCHED',)
        elif new_status == 'PICKED_UP':
            authorized = order_item.assigned_agent_id == request.user.id
            required_statuses = ('PICKUP_SCHEDULED',)
        elif new_status == 'DISPATCHED':
            # Out for delivery - intra-city only. Intercity items stop at the
            # origin hub (DROPPED_AT_ORIGIN_HUB) instead; the admin runs the
            # line-haul and the buyer's-city agent delivers.
            if intercity:
                return Response(
                    {"error": "Intercity orders are dropped at the origin hub, not dispatched. "
                              "Use 'Dropped at Origin Hub' to complete your pickup leg."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            authorized = order_item.assigned_agent_id == request.user.id
            required_statuses = ('PICKED_UP',)
        elif new_status == 'DROPPED_AT_ORIGIN_HUB':
            # Intercity pickup leg completion: drop the item at the origin
            # city hub; line-haul is the admin's job from here.
            authorized = order_item.assigned_agent_id == request.user.id
            required_statuses = ('PICKED_UP',)
        else:
            authorized = None

        if required_statuses is None:
            return Response(
                {"error": "Agents can only move an order to: Picked Up from Seller, "
                          "Dropped at Origin Hub (intercity), In Transit / Dispatched "
                          "(local delivery), or Delivered to Buyer."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not authorized:
            return Response(
                {"error": "Order item not found or not assigned to you."},
                status=status.HTTP_404_NOT_FOUND
            )

        if order_item.status not in required_statuses:
            valid_previous = ' or '.join(
                STATUS_LABELS.get(s, s) for s in required_statuses)
            return Response(
                {"error": f"Out of sequence: this order must first be marked "
                          f"'{valid_previous}' "
                          f"before it can become '{STATUS_LABELS.get(new_status, new_status)}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_status == 'DELIVERED' and order_item.order.delivery_otp:
            if str(request.data.get('otp', '')) != order_item.order.delivery_otp:
                return Response(
                    {"error": "Incorrect OTP. Ask the buyer for their 4-digit delivery code."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if new_status == 'DELIVERED' and order_item.delivered_at is None:
            # Starts the buyer's 24-hour return window.
            order_item.delivered_at = timezone.now()
        order_item.status = new_status
        order_item.save()

        if new_status == 'DELIVERED' and order_item.item:
            order_item.item.status = 'SOLD'
            order_item.item.save()

    # Notify only after the transition has committed
    label = STATUS_LABELS.get(new_status, new_status)
    message = f"Order '{order_item.item_title}' ({order_item.tracking_number}): {label}."
    buyer_message = message
    if new_status == 'DISPATCHED' and not intercity:
        buyer_message += " Your order is out for delivery - have your 4-digit OTP ready to share with the agent."
    if new_status == 'DROPPED_AT_ORIGIN_HUB':
        buyer_message += f" Your order is being prepared for intercity transit to {order_item.order.shipping_city}."
    if new_status == 'DELIVERED':
        buyer_message += " Loved the service? Rate your seller & delivery agent in Profile → Orders."
    notify(order_item.order.user, 'STATUS_UPDATE', buyer_message, order_item=order_item)
    notify(order_item.seller, 'STATUS_UPDATE', message, order_item=order_item)

    # Hub drop = the pickup agent's leg is complete; ops must now run the
    # line-haul. Alert admins so the item doesn't sit at the hub.
    if new_status == 'DROPPED_AT_ORIGIN_HUB':
        origin_hub = hub_for_city(order_item.item.location if order_item.item else '')
        for admin in User.objects.filter(is_staff=True):
            notify(
                admin,
                'ASSIGNMENT_NEEDED',
                f"Intercity order '{order_item.item_title}' was dropped at "
                f"{origin_hub.name if origin_hub else 'the origin hub'} "
                f"({order_item.item.location if order_item.item else 'origin city'}) - ready for "
                f"line-haul dispatch to {order_item.order.shipping_city} (TRK-{order_item.order.id}).",
                order_item=order_item,
            )



    return Response({
        "message": "Status updated successfully!",
        "id": order_item.id,
        "status": order_item.status,
        "hub": hub_for_city(order_item.item.location if order_item.item else '').name
               if (new_status == 'DROPPED_AT_ORIGIN_HUB'
                   and hub_for_city(order_item.item.location if order_item.item else '')) else None,
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_profile_view(request):
    user = request.user
    city = getattr(user, 'profile', None) and getattr(user.profile, 'city', '') or 'N/A'
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email or 'N/A',
        "address": city if city else 'N/A'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_earnings(request):
    """
    Earnings for the calling delivery agent across both legs.

    A leg is earned when it is completed:
      * intercity pickup (delivery_agent_pay > 0 in the item snapshot) is paid
        as soon as the item is dropped at the origin hub;
      * intra-city (delivery_agent_pay == 0) is a single agent end to end, paid
        when the item is DELIVERED;
      * the intercity delivery leg is paid on DELIVERED.
    `pending_total` is what the agent's open tasks will add once finished.
    """
    user = request.user

    pickup_qs = OrderItem.objects.filter(assigned_agent=user)
    delivery_qs = OrderItem.objects.filter(delivery_agent=user)

    # The snapshot tells the two flows apart: only intercity items carry a
    # delivery-leg fee.
    pickup_earned = (
        (Q(delivery_agent_pay__gt=0)
         & Q(status__in=['DROPPED_AT_ORIGIN_HUB', 'IN_TRANSIT',
                         'AT_DESTINATION_HUB', 'DELIVERED']))
        | (Q(delivery_agent_pay=0) & Q(status='DELIVERED'))
    )

    earned_pickup = pickup_qs.filter(pickup_earned).aggregate(
        t=Sum('pickup_agent_pay'))['t'] or 0
    earned_delivery = delivery_qs.filter(status='DELIVERED').aggregate(
        t=Sum('delivery_agent_pay'))['t'] or 0

    pending_pickup = pickup_qs.exclude(pickup_earned).exclude(
        status='CANCELLED').aggregate(t=Sum('pickup_agent_pay'))['t'] or 0
    pending_delivery = delivery_qs.exclude(status='DELIVERED').exclude(
        status='CANCELLED').aggregate(t=Sum('delivery_agent_pay'))['t'] or 0

    completed_tasks = (pickup_qs.filter(pickup_earned).count()
                       + delivery_qs.filter(status='DELIVERED').count())

    rows = []
    for item in OrderItem.objects.filter(
            Q(assigned_agent=user) | Q(delivery_agent=user)
    ).exclude(status__in=['ORDER_PLACED', 'CANCELLED']).select_related(
        'order').order_by('-id')[:10]:
        is_delivery_leg = item.delivery_agent_id == user.id
        amount = (item.delivery_agent_pay if is_delivery_leg
                  else item.pickup_agent_pay)
        rows.append({
            "id": item.id,
            "item_title": item.item_title,
            "tracking_number": item.tracking_number or '',
            "role": 'delivery' if is_delivery_leg else 'pickup',
            "amount": str(amount),
            "status": item.status,
        })

    return Response({
        "earned_total": str(money(earned_pickup + earned_delivery)),
        "pending_total": str(money(pending_pickup + pending_delivery)),
        "completed_tasks": completed_tasks,
        "recent": rows,
    }, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def toggle_seller_verification(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        profile, created = Profile.objects.get_or_create(user=user)
        profile.is_verified = request.data.get('is_verified', not profile.is_verified)
        profile.save()
        notify(
            user,
            'VERIFICATION',
            f"Your VendorPulse seller account is now "
            f"{'verified ✓' if profile.is_verified else 'unverified'}."
        )
        return Response({'status': 'success', 'is_verified': profile.is_verified})
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)


DISPUTE_STATUS_FILTERS = {
    'open': ['OPEN'],
    'resolved': ['RESOLVED'],
    'rejected': ['REJECTED'],
}


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_dispute_list(request):
    """
    Admin queue of buyer disputes. Paginated like the other admin lists;
    ?status=open|resolved|rejected filters the queue.
    """
    disputes = Dispute.objects.select_related(
        'buyer', 'seller', 'resolved_by', 'order_item', 'order_item__order',
        'order_item__item',
    ).order_by('-id')

    status_filter = DISPUTE_STATUS_FILTERS.get(request.GET.get('status'))
    if status_filter:
        disputes = disputes.filter(status__in=status_filter)

    open_count = Dispute.objects.filter(status='OPEN').count()
    resolved_count = Dispute.objects.filter(status='RESOLVED').count()
    rejected_count = Dispute.objects.filter(status='REJECTED').count()

    rows, meta, all_requested = _paginate_queryset(disputes, request, default_page_size=10)

    data = [{
        "id": d.id,
        "status": d.status,
        "reason": d.reason,
        "description": d.description,
        "item_title": d.order_item.item_title,
        "item_price": str(d.order_item.item_price),
        "order_id": d.order_item.order.id,
        "tracking_number": d.order_item.tracking_number or '',
        "buyer": d.buyer.username,
        "seller": d.seller.username,
        "created_at": d.created_at.strftime("%d %b %Y, %I:%M %p"),
        "resolution_note": d.resolution_note,
        "resolved_by": d.resolved_by.username if d.resolved_by else None,
        "resolved_at": d.resolved_at.strftime("%d %b %Y, %I:%M %p") if d.resolved_at else None,
    } for d in rows]

    if all_requested:
        return Response(data, status=status.HTTP_200_OK)

    meta["open_count"] = open_count
    meta["resolved_count"] = resolved_count
    meta["rejected_count"] = rejected_count
    return Response({**meta, "results": data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_resolve_dispute(request, dispute_id):
    """
    Admin decides a dispute: {status: 'RESOLVED'|'REJECTED', note: required}.
    Buyer and seller are notified with the decision.
    """
    try:
        dispute = Dispute.objects.select_related('buyer', 'seller', 'order_item').get(pk=dispute_id)
    except Dispute.DoesNotExist:
        return Response({"error": "Dispute not found."}, status=status.HTTP_404_NOT_FOUND)

    if dispute.status != 'OPEN':
        return Response({"error": f"This dispute was already {dispute.status.lower()}."},
                        status=status.HTTP_400_BAD_REQUEST)

    decision = request.data.get('status')
    if decision not in ('RESOLVED', 'REJECTED'):
        return Response({"error": "Decision must be RESOLVED or REJECTED."},
                        status=status.HTTP_400_BAD_REQUEST)

    note = str(request.data.get('note') or '').strip()
    if not note:
        return Response({"error": "A resolution note is required (it is shown to both parties)."},
                        status=status.HTTP_400_BAD_REQUEST)

    dispute.status = decision
    dispute.resolution_note = note[:1000]
    dispute.resolved_by = request.user
    dispute.resolved_at = timezone.now()
    dispute.save()

    item_title = dispute.order_item.item_title
    decision_label = 'resolved in your favor' if decision == 'RESOLVED' else 'rejected'
    message = f"Dispute on '{item_title}' was {decision_label} by the VendorPulse team. Note: {note}"

    notify(dispute.buyer, 'DISPUTE', message, order_item=dispute.order_item)
    notify(dispute.seller, 'DISPUTE', message, order_item=dispute.order_item)

    return Response({
        "message": f"Dispute {decision.lower()}.",
        "dispute": {"id": dispute.id, "status": dispute.status,
                    "resolution_note": dispute.resolution_note},
    }, status=status.HTTP_200_OK)


RETURN_STATUS_FILTERS = {
    'requested': ['REQUESTED'],
    'approved': ['APPROVED'],
    'rejected': ['REJECTED'],
}


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_return_list(request):
    """
    Admin queue of buyer return requests, newest first. Paginated like the
    other admin lists; ?status=requested|approved|rejected filters the queue.
    """
    returns = ReturnRequest.objects.select_related(
        'order_item', 'order_item__order', 'buyer', 'seller', 'resolved_by',
    ).order_by('-id')

    status_filter = RETURN_STATUS_FILTERS.get(request.GET.get('status'))
    if status_filter:
        returns = returns.filter(status__in=status_filter)

    requested_count = ReturnRequest.objects.filter(status='REQUESTED').count()
    approved_count = ReturnRequest.objects.filter(status='APPROVED').count()
    rejected_count = ReturnRequest.objects.filter(status='REJECTED').count()

    rows, meta, all_requested = _paginate_queryset(returns, request, default_page_size=10)

    data = [{
        "id": r.id,
        "status": r.status,
        "reason": r.reason,
        "note": r.note,
        "item_title": r.order_item.item_title,
        "item_price": str(r.order_item.item_price),
        "delivery_charge": str(r.order_item.delivery_charge),
        "refund_amount": str(r.refund_amount),
        "order_id": r.order_item.order.id,
        "tracking_number": r.order_item.tracking_number or '',
        "buyer": r.buyer.username,
        "seller": r.seller.username,
        "delivered_at": (r.order_item.delivered_at.strftime("%d %b %Y, %I:%M %p")
                         if r.order_item.delivered_at else None),
        "created_at": r.created_at.strftime("%d %b %Y, %I:%M %p"),
        "admin_note": r.admin_note,
        "resolved_by": r.resolved_by.username if r.resolved_by else None,
        "resolved_at": (r.resolved_at.strftime("%d %b %Y, %I:%M %p")
                        if r.resolved_at else None),
    } for r in rows]

    if all_requested:
        return Response(data, status=status.HTTP_200_OK)

    meta["requested_count"] = requested_count
    meta["approved_count"] = approved_count
    meta["rejected_count"] = rejected_count
    return Response({**meta, "results": data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_resolve_return(request, return_id):
    """
    Admin decides a return: {status: 'APPROVED'|'REJECTED', note: required}.

    Approval is the money-moving step: the buyer is refunded the item price
    plus that item's delivery charge, the 5% platform fee is reversed (the
    seller payout for the item becomes 0) and the listing returns to the
    marketplace. Agent pay is untouched - the agents already did the work.
    """
    decision = request.data.get('status')
    if decision not in ('APPROVED', 'REJECTED'):
        return Response({"error": "Decision must be APPROVED or REJECTED."},
                        status=status.HTTP_400_BAD_REQUEST)

    note = str(request.data.get('note') or '').strip()
    if not note:
        return Response({"error": "A note is required (it is shown to both parties)."},
                        status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        return_request = ReturnRequest.objects.select_for_update().select_related(
            'order_item', 'order_item__item', 'buyer', 'seller',
        ).filter(pk=return_id).first()
        if return_request is None:
            return Response({"error": "Return request not found."},
                            status=status.HTTP_404_NOT_FOUND)
        if return_request.status != 'REQUESTED':
            return Response(
                {"error": f"This return was already {return_request.status.lower()}."},
                status=status.HTTP_400_BAD_REQUEST)

        order_item = return_request.order_item
        if decision == 'APPROVED':
            # Full refund = what the buyer paid for this item.
            return_request.refund_amount = money(
                order_item.item_price + order_item.delivery_charge)
            # Commission reversed and the seller's payout cancelled: the sale
            # is undone, not discounted.
            order_item.platform_fee = Decimal('0.00')
            order_item.seller_payout = Decimal('0.00')
            order_item.save(update_fields=['platform_fee', 'seller_payout'])
            # The returned item goes back on the marketplace.
            if order_item.item:
                order_item.item.status = 'AVAILABLE'
                order_item.item.save(update_fields=['status'])

        return_request.status = decision
        return_request.admin_note = note[:1000]
        return_request.resolved_by = request.user
        return_request.resolved_at = timezone.now()
        return_request.save()

    item_title = order_item.item_title
    if decision == 'APPROVED':
        message = (f"Return approved for '{item_title}'. Refund of "
                   f"Rs. {return_request.refund_amount} is on its way. Note: {note}")
    else:
        message = f"Return request for '{item_title}' was rejected. Note: {note}"

    notify(return_request.buyer, 'RETURN', message, order_item=order_item)
    notify(return_request.seller, 'RETURN', message, order_item=order_item)

    return Response({
        "message": f"Return {decision.lower()}.",
        "return": {
            "id": return_request.id,
            "status": return_request.status,
            "refund_amount": str(return_request.refund_amount),
            "admin_note": return_request.admin_note,
        },
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_analytics(request):
    # --- summary counters (one aggregate query each) ---
    delivered_q = OrderItem.objects.filter(status='DELIVERED')

    # Money roll-up across every non-cancelled item, from the per-item
    # snapshots taken at checkout (so it survives rate-card changes).
    money_totals = OrderItem.objects.exclude(status='CANCELLED').aggregate(
        gross_sales=Sum('item_price'),
        commission=Sum('platform_fee'),
        delivery=Sum('delivery_charge'),
        seller_payouts=Sum('seller_payout'),
        pickup_pay=Sum('pickup_agent_pay'),
        delivery_pay=Sum('delivery_agent_pay'),
    )
    refunds = ReturnRequest.objects.filter(status='APPROVED').aggregate(
        t=Sum('refund_amount'))['t'] or 0
    agent_payouts = money((money_totals['pickup_pay'] or 0)
                          + (money_totals['delivery_pay'] or 0))

    summary = {
        "total_orders": Order.objects.count(),
        "completed_revenue": delivered_q.aggregate(t=Sum('item_price'))['t'] or 0,
        "delivered_items": delivered_q.count(),
        "in_transit_items": OrderItem.objects.filter(status__in=ACTIVE_STATUSES).count(),
        "awaiting_assignment": OrderItem.objects.filter(
            status='ORDER_PLACED', assigned_agent=None).count(),
        "active_listings": ProductItem.objects.filter(status='AVAILABLE', approval_status='APPROVED').count(),
        "pending_listings": ProductItem.objects.filter(approval_status='PENDING').count(),
        "registered_users": User.objects.count(),
        "total_agents": User.objects.filter(profile__is_delivery_agent=True).count(),
        # Money model (vendorpulse_core.pricing)
        "gross_sales": money_totals['gross_sales'] or 0,
        "platform_commission": money_totals['commission'] or 0,
        "delivery_revenue": money_totals['delivery'] or 0,
        "seller_payouts": money_totals['seller_payouts'] or 0,
        "agent_payouts": agent_payouts,
        "platform_earnings": money((money_totals['commission'] or 0)
                                   + (money_totals['delivery'] or 0)
                                   - agent_payouts),
        "refunds": refunds,
        "pending_returns": ReturnRequest.objects.filter(status='REQUESTED').count(),
    }

    # --- orders per city (buyer demand) ---
    orders_per_city = Order.objects.exclude(shipping_city=None).values(
        'shipping_city',
    ).annotate(
        orders=Count('id'),
        revenue=Sum('total_price'),
    ).order_by('-orders')

    # --- item status breakdown (fulfillment health) ---
    status_breakdown = OrderItem.objects.values('status').annotate(
        count=Count('id'),
    ).order_by('-count')

    # --- agent utilization (per agent: active load vs completed work) ---
    # select_related('profile'): the loop reads profile.city — without the
    # join this is 1 extra query PER agent (121+ with the seeded agents).
    agent_rows = User.objects.filter(profile__is_delivery_agent=True).select_related(
        'profile',
    ).annotate(
        active_load=Count('assigned_deliveries',
                          filter=Q(assigned_deliveries__status__in=ACTIVE_STATUSES)),
        completed=Count('assigned_deliveries',
                        filter=Q(assigned_deliveries__status='DELIVERED')),
        avg_rating=Avg('agent_ratings_received__agent_stars'),
    ).order_by('-completed', '-active_load')

    agents = [{
        "username": u.username,
        "city": getattr(u, 'profile', None) and u.profile.city or '',
        "active_load": u.active_load,
        "completed": u.completed,
        "avg_rating": round(u.avg_rating, 1) if u.avg_rating is not None else None,
    } for u in agent_rows]

    # --- top sellers by payout (net of the 5% platform commission) ---
    top_sellers = OrderItem.objects.values('seller__username').annotate(
        sales=Count('id'),
        revenue=Sum('seller_payout'),
        avg_rating=Avg('seller__seller_ratings_received__seller_stars'),
    ).order_by('-revenue')[:5]

    top_seller_rows = [{
        "seller__username": row['seller__username'],
        "sales": row['sales'],
        "revenue": row['revenue'],
        "avg_rating": round(row['avg_rating'], 1) if row['avg_rating'] is not None else None,
    } for row in top_sellers]

    # --- revenue trend (orders per day, last 14 days) ---
    trend_rows = Order.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=14),
    ).annotate(
        day=TruncDate('created_at'),
    ).values('day').annotate(
        orders=Count('id'),
        revenue=Sum('total_price'),
    ).order_by('day')

    trend = [{
        "date": row['day'].isoformat(),
        "orders": row['orders'],
        "revenue": row['revenue'],
    } for row in trend_rows]

    return Response({
        "summary": summary,
        "orders_per_city": list(orders_per_city),
        "status_breakdown": list(status_breakdown),
        "agents": agents,
        "top_sellers": top_seller_rows,
        "revenue_trend": trend,
    }, status=status.HTTP_200_OK)
