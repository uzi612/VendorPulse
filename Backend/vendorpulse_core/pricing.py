"""
Marketplace money model: delivery charges, seller commission and agent pay.

Every order item ships as its own package (its own tracking number and its own
agent), so charges are calculated per item and snapshotted onto the order rows
at checkout. A later rate change therefore never rewrites historical orders.

    buyer pays     item price + delivery charge (intra-city / intercity)
    seller gets    item price - PLATFORM_COMMISSION_PERCENT (5%)
    agents get     a flat fee per leg; a single agent does both legs intra-city
    platform keeps the commission + (delivery charge - agent pay)

Rates live in settings (DELIVERY_FEE_*, AGENT_PAY_*, ...) so they can be tuned
without touching this module. All helpers return Decimal rounded to paise.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

TWO_PLACES = Decimal('0.01')

# Why per-leg pay differs: an intercity item is handled twice (pickup agent to
# the origin hub, then a buyer-city agent to the door), while an intra-city
# item is one agent end to end.
INTERCITY_PICKUP_PAY = 'AGENT_PAY_PICKUP'
INTERCITY_DELIVERY_PAY = 'AGENT_PAY_DELIVERY'
INTRA_AGENT_PAY = 'AGENT_PAY_INTRA'


def money(value):
    """Decimal -> 2 dp, half-up (Rupees and paise, never float drift)."""
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def delivery_charge(is_intercity):
    """What the buyer pays for one item's delivery."""
    key = 'DELIVERY_FEE_INTERCITY' if is_intercity else 'DELIVERY_FEE_INTRA'
    return money(getattr(settings, key))


def agent_pay(is_intercity):
    """(pickup_agent_pay, delivery_agent_pay) for one item.

    Intra-city: the assigned agent performs pickup and delivery, so the whole
    fee sits in the pickup slot (the delivery slot stays zero - there is no
    second agent).
    """
    if is_intercity:
        return (money(getattr(settings, INTERCITY_PICKUP_PAY)),
                money(getattr(settings, INTERCITY_DELIVERY_PAY)))
    return money(getattr(settings, INTRA_AGENT_PAY)), Decimal('0.00')


def commission(item_price):
    """Platform's 5% cut of the item price (never charged on delivery)."""
    percent = Decimal(str(getattr(settings, 'PLATFORM_COMMISSION_PERCENT')))
    return money(Decimal(item_price) * percent / Decimal('100'))


def item_quote(item_price, is_intercity):
    """Full money breakdown for one order item, ready to snapshot."""
    price = money(item_price)
    fee = commission(price)
    charge = delivery_charge(is_intercity)
    pickup_pay, delivery_pay = agent_pay(is_intercity)
    return {
        'delivery_charge': charge,
        'platform_fee': fee,
        'seller_payout': money(price - fee),
        'pickup_agent_pay': pickup_pay,
        'delivery_agent_pay': delivery_pay,
        'agent_pay': money(pickup_pay + delivery_pay),
        'platform_margin': money(charge - pickup_pay - delivery_pay),
    }


def is_return_window_open(delivered_at, now=None):
    """True while the buyer can still request a return (24 h by default)."""
    from datetime import timedelta

    from django.utils import timezone

    if delivered_at is None:
        return False
    now = now or timezone.now()
    hours = int(getattr(settings, 'RETURN_WINDOW_HOURS'))
    return now <= delivered_at + timedelta(hours=hours)


def return_window_ends_at(delivered_at):
    from datetime import timedelta

    if delivered_at is None:
        return None
    hours = int(getattr(settings, 'RETURN_WINDOW_HOURS'))
    return delivered_at + timedelta(hours=hours)
