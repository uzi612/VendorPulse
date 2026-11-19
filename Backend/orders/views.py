from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from decimal import Decimal
from vendorpulse_core.throttles import CancelThrottle, DisputeThrottle, RatingThrottle
from vendorpulse_core.pricing import (
    is_return_window_open, money, return_window_ends_at,
)
from notifications.utils import notify
from deliveries.linehaul import settle_linehaul_arrivals
from locations.views import hub_for_city
from .models import Order, OrderItem, Rating, Dispute, ReturnRequest


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_success_api(request, order_id):
    try:
        order = Order.objects.get(pk=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

    items_data = []
    for item in order.items.all():
        items_data.append({
            "item_title": item.item_title,
            "item_price": str(item.item_price),
            "status": item.status,
            "tracking_number": item.tracking_number or ''
        })

    return Response({
        "order_id": order.id,
        "subtotal": str(order.subtotal),
        "delivery_charge": str(order.delivery_charge),
        "total_price": str(order.total_price),
        "shipping_address": order.shipping_address,
        "shipping_city": order.shipping_city,
        "shipping_zone": order.shipping_zone_name or (order.shipping_zone.name if order.shipping_zone else ''),
        "pincode": order.pincode or '',
        "phone": order.phone,
        "delivery_otp": order.delivery_otp,  
        "created_at": order.created_at,
        "items": items_data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, RatingThrottle])
@transaction.atomic
def rate_order_item_api(request, order_item_id):
    """
    Buyer rates the seller and/or the delivery agent for one delivered item.

    Body: {seller_stars?, seller_comment?, agent_stars?, agent_comment?}
    Rules:
      - Only the buyer of the order can rate.
      - The item must be DELIVERED.
      - At least one stars field is required (1-5).
      - Each sub-rating can be set exactly once — no overwrites.
      - agent_stars is only allowed when an agent was assigned.
    """
    try:
        order_item = OrderItem.objects.select_related('order', 'seller', 'assigned_agent').get(
            pk=order_item_id)
    except OrderItem.DoesNotExist:
        return Response({"error": "Order item not found."}, status=status.HTTP_404_NOT_FOUND)

    if order_item.order.user != request.user:
        return Response({"error": "Only the buyer can rate this order item."},
                        status=status.HTTP_403_FORBIDDEN)

    if order_item.status != 'DELIVERED':
        return Response({"error": "You can rate only after the item is delivered."},
                        status=status.HTTP_400_BAD_REQUEST)

    # Load any existing rating WITHOUT creating one — validation must happen
    # before insert because the DB check-constraint forbids all-NULL rows.
    rating = Rating.objects.filter(order_item=order_item).first()

    def clean_stars(field):
        """None when absent; validated 1-5 int otherwise."""
        raw = request.data.get(field)
        if raw in (None, ''):
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return f"__error__{field} must be an integer between 1 and 5."
        if not 1 <= value <= 5:
            return f"__error__{field} must be between 1 and 5."
        return value

    seller_stars = clean_stars('seller_stars')
    agent_stars = clean_stars('agent_stars')

    # First error wins — clean_stars returns an error marker when invalid
    for value in (seller_stars, agent_stars):
        if isinstance(value, str):
            return Response({"error": value.replace('__error__', '')},
                            status=status.HTTP_400_BAD_REQUEST)

    if seller_stars is None and agent_stars is None:
        return Response({"error": "Provide at least one rating: seller_stars or agent_stars."},
                        status=status.HTTP_400_BAD_REQUEST)

    if agent_stars is not None and not order_item.assigned_agent:
        return Response({"error": "No delivery agent was assigned to this item."},
                        status=status.HTTP_400_BAD_REQUEST)

    if seller_stars is not None:
        if rating is not None and rating.seller_stars is not None:
            return Response(
                {"error": "You have already rated the seller for this item."},
                status=status.HTTP_400_BAD_REQUEST)

    if agent_stars is not None:
        if rating is not None and rating.agent_stars is not None:
            return Response(
                {"error": "You have already rated the delivery agent for this item."},
                status=status.HTTP_400_BAD_REQUEST)

    # All inputs valid — now create the row if this is the first submission.
    if rating is None:
        rating = Rating(order_item=order_item, buyer=request.user, seller=order_item.seller)

    if seller_stars is not None:
        rating.seller_stars = seller_stars
        comment = request.data.get('seller_comment')
        if comment:
            rating.seller_comment = str(comment)[:500]

    if agent_stars is not None:
        rating.agent_stars = agent_stars
        rating.agent = order_item.assigned_agent
        comment = request.data.get('agent_comment')
        if comment:
            rating.agent_comment = str(comment)[:500]

    rating.save()

    # Notify the rated parties
    if seller_stars is not None:
        notify(
            order_item.seller,
            'RATING',
            f"{request.user.username} rated your sale of '{order_item.item_title}' "
            f"{seller_stars}/5 ★.",
            order_item=order_item,
        )
    if agent_stars is not None:
        notify(
            order_item.assigned_agent,
            'RATING',
            f"{request.user.username} rated your delivery of '{order_item.item_title}' "
            f"{agent_stars}/5 ★.",
            order_item=order_item,
        )

    return Response({
        "message": "Thanks for your feedback!",
        "rating": {
            "id": rating.id,
            "seller_stars": rating.seller_stars,
            "seller_comment": rating.seller_comment,
            "agent_stars": rating.agent_stars,
            "agent_comment": rating.agent_comment,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def track_order_item_api(request, tracking_number):
    # Timed line-haul: materialize a due hub arrival so the buyer's tracking
    # view shows the up-to-date status (lazy settlement hook).
    settle_linehaul_arrivals()

    order_item = OrderItem.objects.select_related('order', 'item').filter(
        tracking_number=tracking_number,
        order__user=request.user
    ).first()

    if order_item is None:
        return Response({"error": "Invalid Tracking Id"}, status=status.HTTP_404_NOT_FOUND)

    # Route context so the tracking UI can render the correct ladder
    # (intra-city 5 steps vs intercity 7 steps with the hub legs).
    origin_city = order_item.item.location if order_item.item else None
    destination_city = order_item.order.shipping_city
    is_intercity = bool(origin_city) and destination_city != origin_city
    origin_hub = hub_for_city(origin_city) if is_intercity else None
    destination_hub = hub_for_city(destination_city) if is_intercity else None

    return Response({
        "tracking_number": order_item.tracking_number,
        "item_title": order_item.item_title,
        "item_price": str(order_item.item_price),
        "status": order_item.status,
        "order_id": order_item.order.id,
        "shipping_address": order_item.order.shipping_address,
        "phone": order_item.order.phone,
        "created_at": order_item.order.created_at,
        # Route type + hub context for the fulfillment timeline
        "is_intercity": is_intercity,
        "origin_city": origin_city,
        "destination_city": destination_city,
        "origin_hub": origin_hub.name if origin_hub else None,
        "destination_hub": destination_hub.name if destination_hub else None,
        # Timed line-haul: expected arrival at the destination hub (ISO) while
        # the item is IN_TRANSIT; null otherwise.
        "linehaul_eta_at": order_item.linehaul_eta_at.isoformat() if order_item.linehaul_eta_at else None,
        # Returns: the 24-hour window opens when the item is delivered.
        "delivery_charge": str(order_item.delivery_charge),
        "delivered_at": order_item.delivered_at.isoformat() if order_item.delivered_at else None,
        "return_window_ends_at": (
            return_window_ends_at(order_item.delivered_at).isoformat()
            if order_item.delivered_at else None),
        "return_status": (order_item.return_request.status
                          if getattr(order_item, 'return_request', None) else None),
    }, status=status.HTTP_200_OK)


CANCEL_REASON_LABELS = dict(OrderItem.CANCEL_REASON_CHOICES)
DISPUTE_REASON_LABELS = dict(Dispute.REASON_CHOICES)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, CancelThrottle])
@transaction.atomic
def cancel_order_item_api(request, order_item_id):
    """
    Buyer cancels one order item — only BEFORE the agent picks it up.

    Body: {reason: 'CHANGED_MIND'|'WRONG_ADDRESS'|'FOUND_ELSEWHERE'|'OTHER',
           note?: free text}
    Effects: item restocked (RESERVED -> AVAILABLE), agent released,
    order total recalculated, seller/agent/buyer notified. From PICKED_UP
    onward the goods are physically in transit -> dispute flow instead.
    """
    try:
        order_item = OrderItem.objects.select_related('order', 'item', 'seller',
                                                      'assigned_agent').get(pk=order_item_id)
    except OrderItem.DoesNotExist:
        return Response({"error": "Order item not found."}, status=status.HTTP_404_NOT_FOUND)

    if order_item.order.user != request.user:
        return Response({"error": "Only the buyer can cancel this order item."},
                        status=status.HTTP_403_FORBIDDEN)

    if order_item.status == 'DELIVERED':
        return Response(
            {"error": "This item was already delivered — use 'Report a problem' to open a dispute instead."},
            status=status.HTTP_400_BAD_REQUEST)

    if order_item.status not in ('ORDER_PLACED', 'PICKUP_SCHEDULED'):
        return Response(
            {"error": "Too late to cancel: the item is already in transit. "
                      "Once delivered, you can open a dispute."},
            status=status.HTTP_400_BAD_REQUEST)

    reason = request.data.get('reason')
    if reason not in [c[0] for c in OrderItem.CANCEL_REASON_CHOICES]:
        return Response(
            {"error": f"A valid cancellation reason is required: "
                      f"{[c[0] for c in OrderItem.CANCEL_REASON_CHOICES]}."},
            status=status.HTTP_400_BAD_REQUEST)

    note = str(request.data.get('note') or '').strip()[:500]

    order_item.status = 'CANCELLED'
    order_item.cancel_reason = reason
    order_item.cancel_note = note or None
    order_item.assigned_agent = None   # frees the agent's active-load slot
    # No money moves on a cancelled item: no delivery charged, no commission,
    # no payout and no agent pay (cancellation is only possible before pickup).
    order_item.delivery_charge = Decimal('0.00')
    order_item.platform_fee = Decimal('0.00')
    order_item.seller_payout = Decimal('0.00')
    order_item.pickup_agent_pay = Decimal('0.00')
    order_item.delivery_agent_pay = Decimal('0.00')
    order_item.save()

    # Restock the listing so others can buy it (item record may be gone)
    if order_item.item and order_item.item.status == 'RESERVED':
        order_item.item.status = 'AVAILABLE'
        order_item.item.save()

    # Order totals = what is still being fulfilled on this order: item
    # subtotal plus the delivery charge of the surviving items.
    remaining = OrderItem.objects.filter(order=order_item.order).exclude(
        status='CANCELLED').aggregate(
            items=Sum('item_price'), delivery=Sum('delivery_charge'))
    order = order_item.order
    order.subtotal = remaining['items'] or 0
    order.delivery_charge = remaining['delivery'] or 0
    order.total_price = (order.subtotal or 0) + (order.delivery_charge or 0)
    order.save(update_fields=['subtotal', 'delivery_charge', 'total_price'])

    reason_label = CANCEL_REASON_LABELS.get(reason, reason)
    detail = f" Reason: {reason_label}." + (f" Note: {note}" if note else "")

    notify(order_item.seller, 'CANCELLATION',
           f"{request.user.username} cancelled the order for '{order_item.item_title}'.{detail}",
           order_item=order_item)
    if request.user != order_item.order.user:
        notify(order_item.order.user, 'CANCELLATION', f"Your order '{order_item.item_title}' was cancelled.{detail}",
               order_item=order_item)

    return Response({
        "message": "Order item cancelled.",
        "item": {
            "id": order_item.id,
            "status": order_item.status,
            "cancel_reason": order_item.cancel_reason,
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, DisputeThrottle])
def open_dispute_api(request, order_item_id):
    """
    Buyer opens a dispute on a DELIVERED item (one per item, like ratings).

    Body: {reason: 'DAMAGED'|'NOT_AS_DESCRIBED'|'NOT_RECEIVED'|'OTHER',
           description: required text}
    The admin then resolves or rejects it; see admin_dispute_endpoints.
    """
    try:
        order_item = OrderItem.objects.select_related('order', 'seller').get(pk=order_item_id)
    except OrderItem.DoesNotExist:
        return Response({"error": "Order item not found."}, status=status.HTTP_404_NOT_FOUND)

    if order_item.order.user != request.user:
        return Response({"error": "Only the buyer can dispute this order item."},
                        status=status.HTTP_403_FORBIDDEN)

    if order_item.status != 'DELIVERED':
        return Response(
            {"error": "Disputes can be opened only for delivered items."},
            status=status.HTTP_400_BAD_REQUEST)

    if Dispute.objects.filter(order_item=order_item).exists():
        return Response(
            {"error": "A dispute was already filed for this item."},
            status=status.HTTP_400_BAD_REQUEST)

    reason = request.data.get('reason')
    if reason not in [c[0] for c in Dispute.REASON_CHOICES]:
        return Response(
            {"error": f"A valid reason is required: {[c[0] for c in Dispute.REASON_CHOICES]}."},
            status=status.HTTP_400_BAD_REQUEST)

    description = str(request.data.get('description') or '').strip()
    if len(description) < 10:
        return Response({"error": "Please describe the problem (at least 10 characters)."},
                        status=status.HTTP_400_BAD_REQUEST)

    dispute = Dispute.objects.create(
        order_item=order_item,
        buyer=request.user,
        seller=order_item.seller,
        reason=reason,
        description=description[:1000],
    )

    reason_label = DISPUTE_REASON_LABELS.get(reason, reason)
    notify(order_item.seller, 'DISPUTE',
           f"{request.user.username} opened a dispute on '{order_item.item_title}': {reason_label}.",
           order_item=order_item)
    for admin in User.objects.filter(is_staff=True):
        notify(admin, 'DISPUTE',
               f"New dispute #{dispute.id} on '{order_item.item_title}' by {request.user.username}: {reason_label}.",
               order_item=order_item)

    return Response({
        "message": "Dispute filed. Our team will review it and get back to you.",
        "dispute": {"id": dispute.id, "status": dispute.status, "reason": dispute.reason},
    }, status=status.HTTP_201_CREATED)


RETURN_REASON_LABELS = dict(ReturnRequest.REASON_CHOICES)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, DisputeThrottle])
@transaction.atomic
def request_return_api(request, order_item_id):
    """
    Buyer requests a return for one delivered item inside the return window.

    Body: {reason: 'CHANGED_MIND'|'DAMAGED'|'NOT_AS_DESCRIBED'|'WRONG_ITEM'|'OTHER',
           note?: free text}
    The window is settings.RETURN_WINDOW_HOURS (24 h) from delivered_at. One
    request per item; an admin approves or rejects it. Approval refunds the
    item price + delivery charge and reverses the seller's payout.
    """
    try:
        order_item = OrderItem.objects.select_related('order', 'seller').get(pk=order_item_id)
    except OrderItem.DoesNotExist:
        return Response({"error": "Order item not found."}, status=status.HTTP_404_NOT_FOUND)

    if order_item.order.user != request.user:
        return Response({"error": "Only the buyer can request a return."},
                        status=status.HTTP_403_FORBIDDEN)

    if order_item.status != 'DELIVERED':
        return Response({"error": "Returns can be requested only after the item is delivered."},
                        status=status.HTTP_400_BAD_REQUEST)

    if ReturnRequest.objects.filter(order_item=order_item).exists():
        return Response({"error": "A return request already exists for this item."},
                        status=status.HTTP_400_BAD_REQUEST)

    if not is_return_window_open(order_item.delivered_at):
        hours = int(settings.RETURN_WINDOW_HOURS)
        return Response(
            {"error": f"The {hours}-hour return window for this item has closed."},
            status=status.HTTP_400_BAD_REQUEST)

    reason = request.data.get('reason')
    if reason not in [c[0] for c in ReturnRequest.REASON_CHOICES]:
        return Response(
            {"error": f"A valid reason is required: "
                      f"{[c[0] for c in ReturnRequest.REASON_CHOICES]}."},
            status=status.HTTP_400_BAD_REQUEST)

    note = str(request.data.get('note') or '').strip()[:1000]

    return_request = ReturnRequest.objects.create(
        order_item=order_item,
        buyer=request.user,
        seller=order_item.seller,
        reason=reason,
        note=note or None,
    )

    reason_label = RETURN_REASON_LABELS.get(reason, reason)
    notify(order_item.seller, 'RETURN',
           f"{request.user.username} requested a return for '{order_item.item_title}': "
           f"{reason_label}.",
           order_item=order_item)
    for admin in User.objects.filter(is_staff=True):
        notify(admin, 'RETURN',
               f"Return #{return_request.id} on '{order_item.item_title}' by "
               f"{request.user.username}: {reason_label}.",
               order_item=order_item)

    return Response({
        "message": "Return requested. Our team will review it within 24 hours.",
        "return": {
            "id": return_request.id,
            "status": return_request.status,
            "reason": return_request.reason,
            "refund_amount": str(return_request.refund_amount),
        },
    }, status=status.HTTP_201_CREATED)
