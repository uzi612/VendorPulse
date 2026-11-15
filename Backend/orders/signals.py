from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models import Count, Q

from .models import OrderItem
from notifications.utils import notify

MAX_ACTIVE_LOAD = 5   # max in-flight deliveries per agent
ACTIVE_STATUSES = ['PICKUP_SCHEDULED', 'PICKED_UP', 'DISPATCHED']


@receiver(post_save, sender=OrderItem)
def auto_assign_agent(sender, instance, created, **kwargs):
    """
    When an OrderItem is created unassigned, find the least-loaded verified
    agent in the item's pickup city and assign them automatically.
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

    # One annotated query: each agent's active load is computed in SQL
    # (COUNT with a status filter) instead of one COUNT query per agent,
    # then we pick the least-loaded with capacity.
    agents = User.objects.filter(
        profile__city__iexact=pickup_city,
        profile__is_delivery_agent=True,
        profile__is_verified=True,
    ).annotate(
        load=Count('assigned_deliveries',
                   filter=Q(assigned_deliveries__status__in=ACTIVE_STATUSES))
    ).exclude(load__gte=MAX_ACTIVE_LOAD).order_by('load')

    best_agent = agents.first()

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
