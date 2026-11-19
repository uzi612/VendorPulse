"""
Backfill the money snapshot for orders that existed before the pricing model.

Existing rows have zeroed fee fields, which would make the seller/agent/admin
dashboards read as zero. This migration prices them with the current rate card
and recomputes each order's subtotal/delivery/total from its items, so the
whole dataset is internally consistent from day one.

Cancelled items carry no money: the buyer was not charged and nobody was paid.

Forward-only on purpose (reverse is a no-op): undoing it would just recreate
zeros, which is not more correct than the backfilled values.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import migrations

TWO_PLACES = Decimal('0.01')


def _money(value):
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def backfill_money(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    OrderItem = apps.get_model('orders', 'OrderItem')
    Item = apps.get_model('products', 'Item')

    intra_fee = Decimal(str(settings.DELIVERY_FEE_INTRA))
    intercity_fee = Decimal(str(settings.DELIVERY_FEE_INTERCITY))
    intra_pay = Decimal(str(settings.AGENT_PAY_INTRA))
    pickup_pay = Decimal(str(settings.AGENT_PAY_PICKUP))
    delivery_pay = Decimal(str(settings.AGENT_PAY_DELIVERY))
    percent = Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))
    zero = Decimal('0.00')

    # Pickup city per item id, in one query (items can be deleted -> no city).
    pickup_cities = dict(
        Item.objects.values_list('id', 'location')
    )

    for order in Order.objects.all().iterator():
        subtotal = zero
        delivery_total = zero

        for item in OrderItem.objects.filter(order_id=order.id).iterator():
            price = _money(item.item_price)
            pickup_city = pickup_cities.get(item.item_id) or ''
            intercity = bool(pickup_city) and order.shipping_city != pickup_city

            if item.status == 'CANCELLED':
                item.delivery_charge = zero
                item.platform_fee = zero
                item.seller_payout = zero
                item.pickup_agent_pay = zero
                item.delivery_agent_pay = zero
            else:
                fee = _money(price * percent / Decimal('100'))
                item.delivery_charge = intercity_fee if intercity else intra_fee
                item.platform_fee = fee
                item.seller_payout = _money(price - fee)
                item.pickup_agent_pay = pickup_pay if intercity else intra_pay
                item.delivery_agent_pay = delivery_pay if intercity else zero
                subtotal += price
                delivery_total += item.delivery_charge

            if item.status == 'DELIVERED' and item.delivered_at is None:
                item.delivered_at = order.created_at

            item.save(update_fields=[
                'delivery_charge', 'platform_fee', 'seller_payout',
                'pickup_agent_pay', 'delivery_agent_pay', 'delivered_at',
            ])

        order.subtotal = _money(subtotal)
        order.delivery_charge = _money(delivery_total)
        order.total_price = _money(order.subtotal + order.delivery_charge)
        order.save(update_fields=['subtotal', 'delivery_charge', 'total_price'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0013_order_delivery_charge_order_subtotal_and_more'),
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_money, migrations.RunPython.noop),
    ]
