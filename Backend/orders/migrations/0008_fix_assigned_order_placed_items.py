"""Fix legacy fulfillment state: assigned items must not sit in ORDER_PLACED.

The fulfillment cycle is:
  ORDER_PLACED (pre-assignment, no agent)
  -> PICKUP_SCHEDULED  (set by assignment: auto-assign signal or admin)
  -> PICKED_UP         (agent)
  -> DISPATCHED        (agent)
  -> DELIVERED         (agent, OTP-gated)

Historically, manual admin assignment did not bump the status, leaving
assigned items in ORDER_PLACED where agents could not legally act on them.
"""
from django.db import migrations


def fix_assigned_items(apps, schema_editor):
    OrderItem = apps.get_model('orders', 'OrderItem')
    OrderItem.objects.filter(
        assigned_agent__isnull=False,
        status='ORDER_PLACED',
    ).update(status='PICKUP_SCHEDULED')


def unfix(apps, schema_editor):
    # Cannot reliably reverse (can't tell legacy rows apart anymore).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_rating'),
    ]

    operations = [
        migrations.RunPython(fix_assigned_items, unfix),
    ]
