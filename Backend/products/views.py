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

from .models import Item, Cart, CartItem, CITY_CHOICES
from orders.models import Order, OrderItem, Rating
from .serializers import ItemSerializer, CartSerializer, SELLER_RATING_ANNOTATIONS
from vendorpulse_core.pagination import paginate_queryset
from vendorpulse_core.throttles import CheckoutThrottle, ListingCreateThrottle
from notifications.utils import notify

ITEMS_PER_PAGE = 24


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, CheckoutThrottle])
@transaction.atomic
def checkout_api(request):
    user = request.user
    
    try:
        cart = Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    cart_items = cart.items.select_related('item', 'item__seller')  # avoids re-fetching each item in the loop
    if not cart_items.exists():
        return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    shipping_address = request.data.get('address') or request.data.get('shipping_address', '')
    phone = request.data.get('phone', '')
    shipping_city = request.data.get('city', '')

    if not shipping_address.strip() or not phone.strip():
        return Response({"error": "Shipping address and phone number are required."}, status=status.HTTP_400_BAD_REQUEST)

    if shipping_city not in [c[0] for c in CITY_CHOICES]:
        return Response({"error": "A valid shipping city is required."}, status=status.HTTP_400_BAD_REQUEST)

    total_price = 0
    for cart_item in cart_items:
        item = cart_item.item
        if item.status != 'AVAILABLE' or item.approval_status != 'APPROVED':
            return Response({"error": f"Item '{item.title}' is no longer available."}, status=status.HTTP_400_BAD_REQUEST)
        total_price += item.price

    order = Order.objects.create(
        user=user,
        total_price=total_price,
        shipping_address=shipping_address,
        shipping_city=shipping_city,
        phone=phone,
        delivery_otp=f"{secrets.randbelow(10000):04d}"
    )
    for cart_item in cart_items:
        item = cart_item.item
        
        order_item = OrderItem.objects.create(
            order=order,
            item=item,
            seller=item.seller,
            item_title=item.title,
            item_price=item.price,
            status='ORDER_PLACED'
        )
        item.status = 'RESERVED'
        item.save()

        notify(
            item.seller,
            'NEW_SALE',
            f"Your item '{item.title}' has been sold! Price: Rs. {item.price}. "
            f"Order TRK-{order.id} by {user.username}.",
            order_item=order_item,
        )

    cart_items.delete()

    return Response({
        "message": "Checkout successful!",
        "order_id": order.id,
        "total_price": str(total_price),
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

    total_revenue_dict = sold_order_items.filter(
        status__in=['ORDER_PLACED', 'PICKED_UP', 'DISPATCHED', 'DELIVERED']
    ).aggregate(total=Sum('item_price'))
    
    total_revenue = total_revenue_dict['total'] or 0.00

    pending_payouts_dict = sold_order_items.exclude(
        status__in=['DELIVERED', 'CANCELLED']
    ).aggregate(total=Sum('item_price'))
    
    completed_payouts_dict = sold_order_items.filter(
        status='DELIVERED'
    ).aggregate(total=Sum('item_price'))

    pending_payouts = pending_payouts_dict['total'] or 0.00
    completed_payouts = completed_payouts_dict['total'] or 0.00

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
        "status": sale.status,
        "cancel_reason": sale.cancel_reason,
        "buyer": sale.order.user.username,
        "shipping_address": sale.order.shipping_address
    } for sale in sold_order_items.select_related('order__user', 'item').order_by('-id')[:10]]

    recent_ratings = [{
        "stars": r.seller_stars,
        "comment": r.seller_comment,
        "buyer": r.buyer.username,
        "item_title": r.order_item.item_title,
    } for r in Rating.objects.filter(seller=user, seller_stars__isnull=False)
        .select_related('buyer', 'order_item').order_by('-id')[:5]]

    return Response({
        "total_revenue": total_revenue,
        "completed_payouts": completed_payouts,
        "pending_payouts": pending_payouts,
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
