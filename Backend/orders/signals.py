from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models import Count, Q

from .models import OrderItem
from notifications.utils import notify

MAX_ACTIVE_LOAD = 8   # max in-flight deliveries per agent (across BOTH legs)
# Statuses where the agent currently holds responsibility for the item:
PICKUP_LEG_ACTIVE = ['PICKUP_SCHEDULED', 'PICKED_UP', 'DISPATCHED']  # as assigned_agent
DELIVERY_LEG_ACTIVE = ['DISPATCHED', 'AT_DESTINATION_HUB']           # as delivery_agent (intercity:
# assigned at arrival in the buyer's city, holds until DELIVERED)


def active_load_annotation():
    """One annotated expression computing an agent's total in-flight load from
    BOTH columns: items they must pick up/transit (assigned_agent) plus
    intercity items waiting for their delivery leg (delivery_agent)."""
    return (Count('assigned_deliveries',
                  filter=Q(assigned_deliveries__status__in=PICKUP_LEG_ACTIVE))
            + Count('delivery_tasks',
                    filter=Q(delivery_tasks__status__in=DELIVERY_LEG_ACTIVE)))


def pick_agent(city, zone):
    """
    Zone-first agent matching, least-loaded within each tier:
      tier 1: verified agents whose operating zone == the target zone
      tier 2: any verified agent in the same city
    Returns a User or None (callers fall back to ASSIGNMENT_NEEDED).
    """
    agents = User.objects.filter(
        profile__city__iexact=city,
        profile__is_delivery_agent=True,
        profile__is_verified=True,
    ).annotate(load=active_load_annotation()).exclude(load__gte=MAX_ACTIVE_LOAD)

    if zone:
        best = agents.filter(profile__zone=zone).order_by('load').first()
        if best:
            return best
    return agents.order_by('load').first()


def is_intercity(order_item):
    """True when the item must cross city boundaries (buyer's city differs
    from the item's pickup city). Unknown pickup city (item deleted) -> intra."""
    pickup_city = order_item.item.location if order_item.item else ''
    return bool(pickup_city) and order_item.order.shipping_city != pickup_city


def assign_delivery_leg(order_item):
    """
    Leg 2 of an intercity item: assign the delivery agent in the BUYER's
    city/zone. Called when the item ARRIVES in the buyer's city (hub flow:
    the admin's AT_DESTINATION_HUB transition; legacy flow: DISPATCHED).
    Call inside that transition's transaction so the assignment is atomic;
    notifications stay post-commit.
    """
    if not is_intercity(order_item) or order_item.delivery_agent_id:
        return None
    agent = pick_agent(order_item.order.shipping_city, order_item.order.shipping_zone)
    if agent is None:
        return None
    order_item.delivery_agent = agent
    order_item.save(update_fields=['delivery_agent'])
    return agent


@receiver(post_save, sender=OrderItem)
def auto_assign_agent(sender, instance, created, **kwargs):
    """
    LEG 1 - pickup assignment. When an OrderItem is created unassigned, find
    the least-loaded verified agent in the item's PICKUP city, preferring
    agents whose operating zone matches the item's pickup zone (Item.zone).
    Tracking number = TRK-<order_id> (shared by all items of the same order).

    Also fires notifications:
      - buyer: "An agent has been assigned..."
      - agent: "New delivery task..."
      - admins: "Order needs manual assignment" (when no agent has capacity)
    """
    if not created or instance.assigned_agent is not None:
        return

    pickup_city = instance.item.location if instance.item else ''
    if not pickup_city:
        return

    pickup_zone = instance.zone if getattr(instance, 'zone_id', None) else None
    best_agent = pick_agent(pickup_city, pickup_zone)

    if best_agent is None:
        # No agent with capacity -> stays ORDER_PLACED / unassigned.
        # Alert every staff user so an admin can assign manually.
        for admin in User.objects.filter(is_staff=True):
            notify(
                admin,
                'ASSIGNMENT_NEEDED',
                f"Order '{instance.item_title}' in {pickup_city} needs manual assignment "
                f"- no delivery agent with free capacity."
            )
        return

    instance.assigned_agent = best_agent
    instance.tracking_number = f'TRK-{instance.order.id}'
    instance.status = 'PICKUP_SCHEDULED'
    instance.save()   # re-fires post_save, but created=False -> returns immediately (no loop)

    # Notify the buyer and the newly assigned agent
    notify(
        instance.order.user,
        'AGENT_ASSIGNED',
        f"A delivery agent ({best_agent.username}) has been assigned to your order "
        f"'{instance.item_title}'. Tracking: TRK-{instance.order.id}",
        order_item=instance,
    )
    notify(
        best_agent,
        'NEW_TASK',
        f"New delivery task: pick up '{instance.item_title}' from {pickup_city} "
        f"(TRK-{instance.order.id})",
        order_item=instance,
    )
