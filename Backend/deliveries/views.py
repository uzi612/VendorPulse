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
from orders.models import Order, OrderItem
from orders.models import Dispute
from accounts.models import Profile
from products.models import CITY_CHOICES
from products.models import Item as ProductItem
from notifications.utils import notify

STATUS_LABELS = dict(OrderItem.ORDER_STATUS_CHOICES)

ACTIVE_STATUSES = ['PICKUP_SCHEDULED', 'PICKED_UP', 'DISPATCHED']


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_delivery_list(request):
    order_items = OrderItem.objects.select_related(
        'order', 'seller', 'seller__profile', 'assigned_agent', 'item'
    ).order_by('-id')

    group = request.GET.get('status_group')
    if group == 'active':
        order_items = order_items.exclude(status__in=['DELIVERED', 'CANCELLED'])
    elif group == 'completed':
        order_items = order_items.filter(status='DELIVERED')
    elif group == 'cancelled':
        order_items = order_items.filter(status='CANCELLED')

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
            "seller_id": item.seller.id,
            "is_seller_verified": bool(getattr(item.seller, 'profile', None) and item.seller.profile.is_verified),
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

    if tracking_number is not None:
        item.tracking_number = tracking_number

    item.save()

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
            is_agent = (getattr(u, 'profile', None) and u.profile.is_delivery_agent) \
                or any(g.name == 'DeliveryAgent' for g in u.groups.all())
            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "address": city if city else 'N/A',
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

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password, email=email)
        
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.city = city
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

    return Response({"message": "Staff profile updated successfully!"}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_delivery_list(request):
    order_items = OrderItem.objects.filter(assigned_agent=request.user).exclude(
        status='ORDER_PLACED'
    ).select_related(
        'order', 'seller', 'seller__profile', 'item'
    ).order_by('-id')
    
    data = []
    for item in order_items:
        seller_city = getattr(item.seller, 'profile', None) and getattr(item.seller.profile, 'city', '') or 'N/A'
        
        data.append({
            "id": item.id,
            "order_id": item.order.id,
            "shipping_address": item.order.shipping_address or 'N/A',
            "shipping_city": item.order.shipping_city or '',
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
        })
    return Response(data, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, OtpVerifyThrottle])
def agent_update_status(request, pk):
    new_status = request.data.get('status')

    AGENT_TRANSITIONS = {
        'PICKED_UP': 'PICKUP_SCHEDULED',
        'DISPATCHED': 'PICKED_UP',
        'DELIVERED': 'DISPATCHED',
    }

    if new_status not in AGENT_TRANSITIONS:
        return Response(
            {"error": "Agents can only move an order to: Picked Up from Seller, "
                      "In Transit / Dispatched, or Delivered to Buyer."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Row lock: two concurrent requests for the same item (e.g. a double-click)
    # serialize here. The second one re-reads the already-applied status and is
    # rejected by the ladder check instead of re-applying the transition and
    # firing a duplicate notification.
    with transaction.atomic():
        try:
            order_item = OrderItem.objects.select_for_update().get(
                pk=pk, assigned_agent=request.user
            )
        except OrderItem.DoesNotExist:
            return Response(
                {"error": "Order item not found or not assigned to you."},
                status=status.HTTP_404_NOT_FOUND
            )

        required_status = AGENT_TRANSITIONS[new_status]
        if order_item.status != required_status:
            return Response(
                {"error": f"Out of sequence: this order must first be marked "
                          f"'{STATUS_LABELS.get(required_status, required_status)}' "
                          f"before it can become '{STATUS_LABELS.get(new_status, new_status)}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_status == 'DELIVERED' and order_item.order.delivery_otp:
            if str(request.data.get('otp', '')) != order_item.order.delivery_otp:
                return Response(
                    {"error": "Incorrect OTP. Ask the buyer for their 4-digit delivery code."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        order_item.status = new_status
        order_item.save()

        if new_status == 'DELIVERED' and order_item.item:
            order_item.item.status = 'SOLD'
            order_item.item.save()

    # Notify only after the transition has committed
    label = STATUS_LABELS.get(new_status, new_status)
    message = f"Order '{order_item.item_title}' ({order_item.tracking_number}): {label}."
    buyer_message = message
    if new_status == 'DISPATCHED':
        buyer_message += " Your order is out for delivery - have your 4-digit OTP ready to share with the agent."
    if new_status == 'DELIVERED':
        buyer_message += " Loved the service? Rate your seller & delivery agent in Profile → Orders."
    notify(order_item.order.user, 'STATUS_UPDATE', buyer_message, order_item=order_item)
    notify(order_item.seller, 'STATUS_UPDATE', message, order_item=order_item)

    return Response({
        "message": "Status updated successfully!",
        "id": order_item.id,
        "status": order_item.status
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


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_analytics(request):
    """
    Aggregated operational analytics for the admin dashboard.
    Everything is computed with SQL aggregates (values + annotate) so the
    whole response costs a fixed handful of queries, not per-row loops.
    """
    ACTIVE_STATUSES = ['PICKUP_SCHEDULED', 'PICKED_UP', 'DISPATCHED']

    # --- summary counters (one aggregate query each) ---
    delivered_q = OrderItem.objects.filter(status='DELIVERED')
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

    # --- top sellers by revenue ---
    top_sellers = OrderItem.objects.values('seller__username').annotate(
        sales=Count('id'),
        revenue=Sum('item_price'),
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
