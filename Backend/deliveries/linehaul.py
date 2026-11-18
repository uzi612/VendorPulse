"""
Timed line-haul: hub-to-hub transit with automatic arrival.

Flow
----
1. Admin dispatches an intercity item (IN_TRANSIT) -> the admin endpoint
   stamps linehaul_departed_at / linehaul_eta_at on the OrderItem using the
   HubRoute duration for the origin->destination hub pair (default 24h).
2. When the ETA elapses, settle_linehaul_arrivals() marks the item
   AT_DESTINATION_HUB and auto-assigns the buyer-city delivery agent -
   exactly what the admin's manual "arrived" button did, but on schedule.

Settlement is LAZY: the function runs at the top of every endpoint that
displays order status (admin deliveries list, agent task list, buyer
tracking). Any dashboard poll materializes due arrivals within seconds,
so no background scheduler is needed. The same function is idempotent and
race-safe (row-lock + status re-check), so at deployment it can equally be
driven by a Celery beat task or cron'd management command without changes.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from orders.models import OrderItem
from locations.models import HubRoute
from notifications.utils import notify
from locations.views import hub_for_city
from orders.signals import assign_delivery_leg

# Fallback transit duration when no HubRoute row exists for the pair.
DEFAULT_LINEHAUL_HOURS = 24

# Upper bound per settle pass: keeps one straggling dashboard request from
# doing unbounded work; the next poll settles the remainder.
SETTLE_BATCH_SIZE = 50


def linehaul_eta_hours(origin_city, destination_city):
    """Transit hours for an origin->destination hub pair (int, >= 1)."""
    route = None
    if origin_city and destination_city:
        route = HubRoute.objects.filter(
            from_hub__city=origin_city,
            to_hub__city=destination_city,
            is_active=True,
        ).first()
    return route.transit_hours if route else DEFAULT_LINEHAUL_HOURS


def stamp_linehaul_departure(order_item, departed_at=None):
    """
    Stamp departure + ETA on an item that just went IN_TRANSIT. Returns the
    ETA datetime (also stored on the row; caller saves).
    """
    departed_at = departed_at or timezone.now()
    hours = linehaul_eta_hours(
        order_item.item.location if order_item.item else '',
        order_item.order.shipping_city,
    )
    order_item.linehaul_departed_at = departed_at
    order_item.linehaul_eta_at = departed_at + timedelta(hours=hours)
    return order_item.linehaul_eta_at


def _notify_arrival(order_item, delivery_agent, needs_assignment):
    """
    Buyer + delivery-agent (or admin-alert) notifications for a hub arrival.
    Call AFTER the transition transaction has committed, so a rollback never
    sends mail.
    """
    buyer = order_item.order.user
    destination_hub = hub_for_city(order_item.order.shipping_city)
    notify(
        buyer,
        'STATUS_UPDATE',
        f"Your order '{order_item.item_title}' has arrived in {order_item.order.shipping_city}"
        f"{f' ({destination_hub.name})' if destination_hub else ''}. "
        f"A local agent will deliver it shortly - have your 4-digit OTP ready "
        f"(TRK-{order_item.order.id}).",
        order_item=order_item,
    )
    if delivery_agent:
        notify(
            delivery_agent,
            'NEW_TASK',
            f"New delivery task: collect '{order_item.item_title}' from "
            f"{destination_hub.name if destination_hub else 'the destination hub'} in "
            f"{order_item.order.shipping_city}"
            f"{f' ({destination_hub.address})' if destination_hub else ''} and hand it to the "
            f"buyer at {order_item.order.shipping_city} - "
            f"{order_item.order.shipping_zone_name or ''} "
            f"(pincode {order_item.order.pincode or 'n/a'}, TRK-{order_item.order.id}). "
            f"Collect the buyer's 4-digit OTP to complete delivery.",
            order_item=order_item,
        )
    elif needs_assignment:
        for admin in _staff_users():
            notify(
                admin,
                'ASSIGNMENT_NEEDED',
                f"Intercity order '{order_item.item_title}' reached the "
                f"{destination_hub.name if destination_hub else 'destination hub'} in "
                f"{order_item.order.shipping_city} but no delivery agent has capacity - "
                f"manual assignment needed (TRK-{order_item.order.id}).",
                order_item=order_item,
            )


def _staff_users():
    from django.contrib.auth.models import User
    return User.objects.filter(is_staff=True)


def arrive_at_destination(order_item_id):
    """
    Complete one hub arrival atomically:
      status IN_TRANSIT -> AT_DESTINATION_HUB (+ auto-assign delivery agent).

    Row-locked and re-checked, so it is safe against concurrent callers
    (admin manual click racing the settle pass) - only one wins. Returns
    True if THIS call performed the transition, False if the row was not
    eligible (already arrived, cancelled, gone). Notifications are sent
    after commit.
    """
    with transaction.atomic():
        order_item = (OrderItem.objects.select_for_update()
                      .select_related('order', 'item')
                      .filter(pk=order_item_id).first())
        if order_item is None or order_item.status != 'IN_TRANSIT':
            return False

        order_item.status = 'AT_DESTINATION_HUB'
        delivery_agent = None
        if order_item.delivery_agent_id is None:
            delivery_agent = assign_delivery_leg(order_item)
        order_item.save()

    _notify_arrival(order_item, delivery_agent, delivery_agent is None)
    return True


def settle_linehaul_arrivals(now=None):
    """
    Materialize hub arrivals whose line-haul ETA has elapsed.

    One cheap indexed scan (status='IN_TRANSIT', eta <= now); each due row is
    then transitioned under its own row lock. Returns the number of arrivals
    processed. Call at the top of status-displaying endpoints.

    Legacy tolerance: pre-feature items already IN_TRANSIT with no ETA are
    backfilled once (ETA = now + route hours) so they arrive on schedule
    instead of instantly.
    """
    now = now or timezone.now()

    # Backfill stragglers dispatched before this feature existed.
    stale = OrderItem.objects.filter(status='IN_TRANSIT', linehaul_eta_at__isnull=True)
    if stale.exists():
        for oi in stale:
            stamp_linehaul_departure(oi, departed_at=oi.linehaul_departed_at or now)
            oi.save(update_fields=['linehaul_departed_at', 'linehaul_eta_at'])

    due_ids = list(OrderItem.objects.filter(
        status='IN_TRANSIT',
        linehaul_eta_at__isnull=False,
        linehaul_eta_at__lte=now,
    ).values_list('id', flat=True)[:SETTLE_BATCH_SIZE])

    arrived = 0
    for pk in due_ids:
        if arrive_at_destination(pk):
            arrived += 1
    return arrived
