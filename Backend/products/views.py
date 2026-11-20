from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Prefetch, Avg, Count, Q
import secrets
from decimal import Decimal

from .models import Item, Cart, CartItem, CITY_CHOICES
from orders.models import Order, OrderItem, Rating
from .serializers import ItemSerializer, CartSerializer, SELLER_RATING_ANNOTATIONS
from locations.models import Zone
from locations.views import zone_for_pincode
from vendorpulse_core.pagination import paginate_queryset
from vendorpulse_core.pricing import item_quote, money
from vendorpulse_core.throttles import CheckoutThrottle, ListingCreateThrottle
from notifications.utils import notify

ITEMS_PER_PAGE = 24


def _resolve_item_zone(request, item):
    """
    Pickup zone for a listing: an explicit zone id (validated against the
    listing's city) wins; otherwise fall back to the seller's profile zone
    when it belongs to the same city. Returns (zone_or_None, error_or_None).
    """
    zone_id = request.data.get('zone')
    if zone_id:
        try:
            zone = Zone.objects.get(pk=zone_id)
        except (Zone.DoesNotExist, ValueError, TypeError):
            return None, "Selected pickup zone was not found."
        if zone.city != item.location:
            return None, "The pickup zone must belong to the listing's city."
        return zone, None
    profile_zone = getattr(getattr(request.user, 'profile', None), 'zone', None)
    if profile_zone and profile_zone.city == item.location:
        return profile_zone, None
    return None, None


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle, UserRateThrottle, ListingCreateThrottle])
def item_list_create_api(request):
    if request.method == 'GET':
        items = Item.objects.filter(status='AVAILABLE', approval_status='APPROVED').select_related(
            'seller', 'seller__profile'
        ).annotate(**SELLER_RATING_ANNOTATIONS).order_by('-created_at')
        
        category = request.GET.get('category')
        condition = request.GET.get('condition')
        location_query = request.GET.get('city') or request.GET.get('location') 
        search_query = request.GET.get('search') or request.GET.get('q')

        if category:
            items = items.filter(category=category)
        if condition:
            items = items.filter(condition=condition)
        if location_query:
            items = items.filter(location__icontains=location_query) 
        if search_query:
            items = items.filter(title__icontains=search_query) 

        rows, meta, _ = paginate_queryset(items, request, default_page_size=ITEMS_PER_PAGE)

        serializer = ItemSerializer(rows, many=True, context={'request': request})
        return Response({**meta, "results": serializer.data}, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = ItemSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # Every listing goes through admin moderation before it appears
            # on the marketplace (user decision: no verified-seller exemption).
            item = serializer.save(seller=request.user, status='AVAILABLE', approval_status='PENDING')
            item.zone, zone_error = _resolve_item_zone(request, item)
            if zone_error:
                item.delete()   # don't leave a half-created listing behind
                return Response({"error": zone_error}, status=status.HTTP_400_BAD_REQUEST)
            item.save(update_fields=['zone'])
            for admin in User.objects.filter(is_staff=True):
                notify(admin, 'MODERATION',
                       f"New listing awaiting review: '{item.title}' by {request.user.username} "
                       f"(Rs. {item.price}).", )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([AllowAny])
def item_detail_api(request, pk):
    item = get_object_or_404(
        Item.objects.select_related('seller', 'seller__profile').annotate(**SELLER_RATING_ANNOTATIONS),
        pk=pk)

    is_owner = request.user.is_authenticated and item.seller == request.user
    is_admin = request.user.is_authenticated and request.user.is_staff

    if request.method == 'GET':
        # Unapproved listings are hidden from the marketplace — only the
        # owner and admins can view them while they wait for review.
        if item.approval_status != 'APPROVED' and not (is_owner or is_admin):
            return Response({"error": "This listing is not available."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ItemSerializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)

    if item.seller != request.user:
        return Response({"detail": "You do not have permission to modify this listing."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'PUT':
        serializer = ItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            # Edited content must be reviewed again — a live listing can't be
            # silently changed into something that bypasses moderation.
            serializer.save(approval_status='PENDING', rejection_reason=None,
                            reviewed_by=None, reviewed_at=None)
            if 'location' in request.data or 'zone' in request.data:
                item.refresh_from_db()
                item.zone, zone_error = _resolve_item_zone(request, item)
                if zone_error:
                    return Response({"error": zone_error}, status=status.HTTP_400_BAD_REQUEST)
                item.save(update_fields=['zone'])
            # The item just left the marketplace; drop it from buyers' carts.
            CartItem.objects.filter(item=item).delete()
            for admin in User.objects.filter(is_staff=True):
                notify(admin, 'MODERATION',
                       f"Listing re-submitted for review: '{item.title}' by {request.user.username} "
                       f"(Rs. {item.price}).")
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        item.delete()
        return Response({"detail": "Listing deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart_detail_api(request):
    cart = Cart.objects.filter(user=request.user).prefetch_related(
        Prefetch('items', queryset=CartItem.objects.select_related(
            'item', 'item__seller', 'item__seller__profile'))
    ).first()
    if cart is None:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    serializer = CartSerializer(cart)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart_api(request, item_id):
    try:
        item = Item.objects.get(pk=item_id)
    except Item.DoesNotExist:
        return Response({"error": "Item not found."}, status=status.HTTP_404_NOT_FOUND)

    if item.seller == request.user:
        return Response({"error": "You cannot add your own item to the cart."}, status=status.HTTP_400_BAD_REQUEST)

    if item.status != 'AVAILABLE' or item.approval_status != 'APPROVED':
        return Response({"error": "This item is no longer available."}, status=status.HTTP_400_BAD_REQUEST)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    
    cart_item, created = CartItem.objects.get_or_create(cart=cart, item=item)

    if not created:
        return Response({"message": "Item is already in your cart."}, status=status.HTTP_200_OK)

    return Response({"message": "Item added to cart successfully!"}, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_cart_api(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    cart_item.delete()
    return Response({"detail": "Item removed from cart."}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def checkout_quote_api(request):
    """
    Read-only price preview for the checkout page: resolves the pincode and
    prices the cart exactly as checkout will, so the buyer sees the delivery
    charge (and which items are intercity) before placing the order.

    Query: ?pincode=400051
    """
    pincode = str(request.GET.get('pincode') or '').strip()
    if not (pincode.isdigit() and len(pincode) == 6):
        return Response({"error": "A valid 6-digit delivery pincode is required."},
                        status=status.HTTP_400_BAD_REQUEST)

    zone = zone_for_pincode(pincode)
    if zone is None:
        return Response({"error": "We don't deliver to this pincode yet."},
                        status=status.HTTP_400_BAD_REQUEST)

    cart_items = CartItem.objects.filter(cart__user=request.user).select_related('item')
    if not cart_items.exists():
        return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    lines = []
    subtotal = Decimal('0.00')
    delivery_total = Decimal('0.00')
    for cart_item in cart_items:
        item = cart_item.item
        intercity = bool(item.location) and item.location != zone.city
        quote = item_quote(item.price, intercity)
        subtotal += item.price
        delivery_total += quote['delivery_charge']
        lines.append({
            "cart_item_id": cart_item.id,
            "item_id": item.id,
            "title": item.title,
            "price": str(money(item.price)),
            "is_intercity": intercity,
            "delivery_charge": str(quote['delivery_charge']),
            "available": item.status == 'AVAILABLE' and item.approval_status == 'APPROVED',
        })

    subtotal, delivery_total = money(subtotal), money(delivery_total)
    return Response({
        "pincode": pincode,
        "city": zone.city,
        "zone_id": zone.id,
        "zone_name": zone.name,
        "items": lines,
        "subtotal": str(subtotal),
        "delivery_charge": str(delivery_total),
        "total_price": str(money(subtotal + delivery_total)),
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, CheckoutThrottle])
@transaction.atomic
def checkout_api(request):
    """
    Pincode-first checkout: the buyer's 6-digit pincode resolves the delivery
    zone AND the city (each city owns a distinct pincode range), so no city
    dropdown is needed. Body: {pincode: required 6 digits, phone: required,
    address: optional short detail (flat/house no.)}.
    """
    user = request.user

    try:
        cart = Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    cart_items = cart.items.select_related('item', 'item__seller')  # avoids re-fetching each item in the loop
    if not cart_items.exists():
        return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    pincode = str(request.data.get('pincode') or '').strip()
    if not (pincode.isdigit() and len(pincode) == 6):
        return Response({"error": "A valid 6-digit delivery pincode is required."},
                        status=status.HTTP_400_BAD_REQUEST)

    zone = zone_for_pincode(pincode)
    if zone is None:
        return Response({"error": "We don't deliver to this pincode yet."},
                        status=status.HTTP_400_BAD_REQUEST)

    phone = str(request.data.get('phone') or '').strip()
    address = str(request.data.get('address') or '').strip()[:255]  # optional short detail
    if not phone.strip():
        return Response({"error": "A phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

    subtotal = Decimal('0.00')
    delivery_total = Decimal('0.00')
    priced = []
    for cart_item in cart_items:
        item = cart_item.item
        if item.status != 'AVAILABLE' or item.approval_status != 'APPROVED':
            return Response({"error": f"Item '{item.title}' is no longer available."}, status=status.HTTP_400_BAD_REQUEST)
        # The route sets the fee: a cross-city item travels as two hub legs,
        # a same-city item is one agent end to end (vendorpulse_core.pricing).
        intercity = bool(item.location) and item.location != zone.city
        quote = item_quote(item.price, intercity)
        subtotal += item.price
        delivery_total += quote['delivery_charge']
        priced.append((cart_item, quote))

    subtotal, delivery_total = money(subtotal), money(delivery_total)

    order = Order.objects.create(
        user=user,
        subtotal=subtotal,
        delivery_charge=delivery_total,
        total_price=money(subtotal + delivery_total),
        shipping_address=address,
        shipping_city=zone.city,          # derived from the pincode, never trusted from the client
        shipping_zone=zone,
        shipping_zone_name=zone.name,     # name snapshot, survives zone renames/deactivation
        pincode=pincode,
        delivery_otp=f"{secrets.randbelow(10000):04d}"
    )
    for cart_item, quote in priced:
        item = cart_item.item

        order_item = OrderItem.objects.create(
            order=order,
            item=item,
            seller=item.seller,
            item_title=item.title,
            item_price=item.price,
            status='ORDER_PLACED',
            # Money snapshot: commission split + per-leg agent pay.
            delivery_charge=quote['delivery_charge'],
            platform_fee=quote['platform_fee'],
            seller_payout=quote['seller_payout'],
            pickup_agent_pay=quote['pickup_agent_pay'],
            delivery_agent_pay=quote['delivery_agent_pay'],
        )
        item.status = 'RESERVED'
        item.save()

        notify(
            item.seller,
            'NEW_SALE',
            f"Your item '{item.title}' has been sold! Price: Rs. {item.price} "
            f"(buyer also paid Rs. {quote['delivery_charge']} delivery). "
            f"Your payout after the platform fee: Rs. {quote['seller_payout']}. "
            f"Order TRK-{order.id} by {user.username}.",
            order_item=order_item,
        )

    cart_items.delete()

    return Response({
        "message": "Checkout successful!",
        "order_id": order.id,
        "subtotal": str(subtotal),
        "delivery_charge": str(delivery_total),
        "total_price": str(order.total_price),
        "delivery_otp": order.delivery_otp
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_listings_api(request):
    items = Item.objects.filter(seller=request.user).select_related(
        'seller', 'seller__profile'
    ).annotate(**SELLER_RATING_ANNOTATIONS).order_by('-created_at')
    serializer = ItemSerializer(items, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seller_dashboard_api(request):
    user = request.user
    seller_items = Item.objects.filter(seller=user)
    
    active_listings_count = seller_items.filter(status='AVAILABLE', approval_status='APPROVED').count()
    pending_review_count = seller_items.filter(approval_status='PENDING').count()
    rejected_count = seller_items.filter(approval_status='REJECTED').count()
    sold_order_items = OrderItem.objects.filter(seller=user)
    sold_items_count = sold_order_items.exclude(status='CANCELLED').count()

    # Revenue partition — one consistent split so the numbers reconcile:
    #   gross    = item prices of everything non-cancelled, non-refunded
    #   fees     = the platform's 5% commission on those sales
    #   net      = gross - fees  (what actually reaches the seller)
    #   cleared  = delivered items (payout complete)
    #   pending  = in-escrow items (order placed / scheduled / picked up /
    #              dispatched / at hub / in intercity transit — money earned
    #              but delivery not finished)
    # Approved returns are excluded: their payout was reversed.
    ACTIVE_STATUSES = ['ORDER_PLACED', 'PICKUP_SCHEDULED', 'PICKED_UP', 'DISPATCHED',
                       'DROPPED_AT_ORIGIN_HUB', 'IN_TRANSIT', 'AT_DESTINATION_HUB']

    earning_items = sold_order_items.exclude(status='CANCELLED').exclude(
        return_request__status='APPROVED')

    gross_revenue = earning_items.aggregate(t=Sum('item_price'))['t'] or 0
    platform_fees = earning_items.aggregate(t=Sum('platform_fee'))['t'] or 0
    net_payout = earning_items.aggregate(t=Sum('seller_payout'))['t'] or 0

    completed_payouts = earning_items.filter(
        status='DELIVERED'
    ).aggregate(t=Sum('seller_payout'))['t'] or 0

    pending_payouts = earning_items.filter(
        status__in=ACTIVE_STATUSES
    ).aggregate(t=Sum('seller_payout'))['t'] or 0

    # What buyers got back on approved returns (item price + delivery charge,
    # from the refund snapshot recorded by the admin approval).
    refunded_amount = sold_order_items.filter(
        return_request__status='APPROVED'
    ).aggregate(t=Sum('return_request__refund_amount'))['t'] or 0

    total_revenue = gross_revenue   # kept for older clients; equals gross

    # Seller rating stats — one aggregate over the buyer ratings on this
    # seller's OrderItems (stars only counted; null seller_stars excluded).
    rating_stats = Rating.objects.filter(seller=user).aggregate(
        avg_rating=Avg('seller_stars'),
        rating_count=Count('id', filter=Q(seller_stars__isnull=False)),
    )

    recent_sales = [{
        "order_id": sale.order.id,
        "item_title": sale.item_title,
        "item_price": sale.item_price,
        "platform_fee": sale.platform_fee,
        "seller_payout": sale.seller_payout,
        "status": sale.status,
        "return_status": (sale.return_request.status
                          if getattr(sale, 'return_request', None) else None),
        "cancel_reason": sale.cancel_reason,
        "buyer": sale.order.user.username,
        "shipping_address": sale.order.shipping_address
    } for sale in sold_order_items.select_related('order__user', 'item', 'return_request').order_by('-id')[:10]]

    recent_ratings = [{
        "stars": r.seller_stars,
        "comment": r.seller_comment,
        "buyer": r.buyer.username,
        "item_title": r.order_item.item_title,
    } for r in Rating.objects.filter(seller=user, seller_stars__isnull=False)
        .select_related('buyer', 'order_item').order_by('-id')[:5]]

    return Response({
        "total_revenue": total_revenue,
        "gross_revenue": gross_revenue,
        "platform_fees": platform_fees,
        "net_payout": net_payout,
        "completed_payouts": completed_payouts,
        "pending_payouts": pending_payouts,
        "refunded_amount": refunded_amount,
        "active_listings_count": active_listings_count,
        "pending_review_count": pending_review_count,
        "rejected_count": rejected_count,
        "sold_items_count": sold_items_count,
        "avg_rating": round(rating_stats['avg_rating'], 1) if rating_stats['avg_rating'] is not None else None,
        "rating_count": rating_stats['rating_count'],
        "recent_ratings": recent_ratings,
        "recent_sales": recent_sales
    })


# ------------------------------------------------------------------
# Admin listing moderation
# ------------------------------------------------------------------

MODERATION_FILTERS = {
    'pending': ['PENDING'],
    'approved': ['APPROVED'],
    'rejected': ['REJECTED'],
}

APPROVAL_LABELS = dict(Item.APPROVAL_CHOICES)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_moderation_queue(request):
    """
    Admin queue of listings awaiting review.
    ?status=pending|approved|rejected (default pending), paginated.
    """
    items = Item.objects.select_related('seller', 'seller__profile').order_by('id')

    status_filter = MODERATION_FILTERS.get(request.GET.get('status'))
    if status_filter:
        items = items.filter(approval_status__in=status_filter)

    pending_count = Item.objects.filter(approval_status='PENDING').count()
    approved_count = Item.objects.filter(approval_status='APPROVED').count()
    rejected_count = Item.objects.filter(approval_status='REJECTED').count()

    rows, meta, all_requested = paginate_queryset(items, request, default_page_size=12)

    data = [{
        "id": i.id,
        "title": i.title,
        "description": i.description,
        "price": str(i.price),
        "category": i.category,
        "condition": i.condition,
        "image": request.build_absolute_uri(i.image.url) if i.image else None,
        "location": i.location,
        "approval_status": i.approval_status,
        "rejection_reason": i.rejection_reason,
        "seller_username": i.seller.username,
        "is_seller_verified": bool(getattr(i.seller, 'profile', None) and i.seller.profile.is_verified),
        "created_at": i.created_at.strftime("%d %b %Y, %I:%M %p"),
        "reviewed_at": i.reviewed_at.strftime("%d %b %Y, %I:%M %p") if i.reviewed_at else None,
    } for i in rows]

    if all_requested:
        return Response(data, status=status.HTTP_200_OK)

    meta["pending_count"] = pending_count
    meta["approved_count"] = approved_count
    meta["rejected_count"] = rejected_count
    return Response({**meta, "results": data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_review_listing(request, item_id):
    """
    Admin decides a listing: {decision: 'APPROVED'|'REJECTED', reason?}.
    A reason is required to reject; the seller is notified either way.
    """
    try:
        item = Item.objects.select_related('seller').get(pk=item_id)
    except Item.DoesNotExist:
        return Response({"error": "Listing not found."}, status=status.HTTP_404_NOT_FOUND)

    decision = request.data.get('decision')
    if decision not in ('APPROVED', 'REJECTED'):
        return Response({"error": "Decision must be APPROVED or REJECTED."}, status=status.HTTP_400_BAD_REQUEST)

    if item.approval_status == decision:
        return Response({"error": f"This listing is already {APPROVAL_LABELS.get(decision, decision).lower()}."},
                        status=status.HTTP_400_BAD_REQUEST)

    if decision == 'REJECTED':
        reason = str(request.data.get('reason') or '').strip()
        if not reason:
            return Response({"error": "A rejection reason is required (it is shown to the seller)."},
                            status=status.HTTP_400_BAD_REQUEST)
        item.rejection_reason = reason[:500]
    else:
        item.rejection_reason = None

    item.approval_status = decision
    item.reviewed_by = request.user
    item.reviewed_at = timezone.now()
    item.save()

    if decision == 'APPROVED':
        notify(item.seller, 'MODERATION',
               f"Your listing '{item.title}' was approved and is now live on the marketplace.")
    else:
        # Rejected listings shouldn't linger in buyers' carts.
        CartItem.objects.filter(item=item).delete()
        notify(item.seller, 'MODERATION',
               f"Your listing '{item.title}' was rejected by the VendorPulse team. "
               f"Reason: {item.rejection_reason} You can edit it and resubmit for review.")

    return Response({
        "message": f"Listing {decision.lower()}.",
        "item": {"id": item.id, "approval_status": item.approval_status,
                 "rejection_reason": item.rejection_reason},
    }, status=status.HTTP_200_OK)
