"""
Hub-flow scenario test - Pune -> Hyderabad intercity with the hub ladder,
plus intra-city regression and legacy tolerance. Everything runs inside one
atomic transaction that is ROLLED BACK (no residue), CSRF disabled.

Ladder under test (intercity):
  PICKUP_SCHEDULED -> PICKED_UP -> DROPPED_AT_ORIGIN_HUB
    -> (admin) IN_TRANSIT -> (admin) AT_DESTINATION_HUB [auto-assigns
    delivery agent] -> DELIVERED (delivery agent, OTP)
Ladder under test (intra-city, regression):
  PICKED_UP -> DISPATCHED -> DELIVERED (same agent, OTP)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vendorpulse_core.settings')
django.setup()

from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

import json
from decimal import Decimal
from django.db import transaction
from django.test import Client
from django.contrib.auth.models import User

# The test fires several checkouts/OTP attempts in a burst - lift the rate
# limits (checkout / otp_verify / user) for this script only.
from rest_framework.settings import api_settings
api_settings.DEFAULT_THROTTLE_RATES = {
    **api_settings.DEFAULT_THROTTLE_RATES,
    'user': '100000/min', 'checkout': '100000/min', 'otp_verify': '100000/min',
}

from orders.models import Order, OrderItem
from products.models import Item, Cart
from locations.models import DeliveryHub

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print(('PASS' if ok else 'FAIL'), '-', name, ('| ' + detail if detail else ''))


def patch(client, url, payload):
    return client.patch(url, data=json.dumps(payload), content_type='application/json')


def make_item(seller, title, city):
    return Item.objects.create(seller=seller, title=title, description='temp',
                               price=Decimal('999.00'), condition='GOOD',
                               status='AVAILABLE', approval_status='APPROVED',
                               location=city)


def checkout_as(client, pincode):
    return client.post('/api/products/checkout/',
                       data=json.dumps({'pincode': pincode, 'phone': '9876543210',
                                        'address': 'Flat 9, Hitech Layout'}),
                       content_type='application/json')


def cart_is_only(buyer, item):
    """The buyer's real cart may hold leftover items from manual testing -
    checkout consumes the WHOLE cart, so each scenario must run in isolation."""
    cart, _ = Cart.objects.get_or_create(user=buyer)
    cart.items.all().delete()
    cart.items.create(item=item)


with transaction.atomic():
    sid = transaction.savepoint()

    buyer = User.objects.get(username='mohan123')
    seller = User.objects.get(username='rohan123')
    admin = User.objects.filter(is_staff=True).first()
    admin_client = Client(); admin_client.force_login(admin)

    # ================= INTERCITY: PUNE -> HYDERABAD =======================
    item = make_item(seller, 'HubTest Intercity', 'Pune')
    cart_is_only(buyer, item)
    client = Client(); client.force_login(buyer)
    resp = checkout_as(client, '500001')
    check('checkout pincode 500001 -> 201', resp.status_code in (200, 201), f"status={resp.status_code}")

    order = Order.objects.filter(user=buyer).order_by('-id').first()
    oi = OrderItem.objects.filter(order=order).first()

    # The engine assigns the LEAST-LOADED verified Pune agent - whoever that is.
    pickup_agent = oi.assigned_agent
    check('order item intercity (Pune -> Hyderabad) + Pune pickup agent assigned',
          oi is not None and pickup_agent is not None
          and pickup_agent.profile.city.lower() == 'pune'
          and oi.status == 'PICKUP_SCHEDULED',
          f"pickup_agent={pickup_agent.username if pickup_agent else None} status={getattr(oi, 'status', None)}")

    aclient = Client(); aclient.force_login(pickup_agent)
    oi_url = f'/api/deliveries/agent/deliveries/{oi.id}/update/'
    admin_status_url = f'/api/deliveries/admin/deliveries/{oi.id}/status/'

    resp = patch(aclient, oi_url, {'status': 'PICKED_UP'})
    check('pickup agent: PICKED_UP', resp.status_code == 200, f"status={resp.status_code}")

    resp = patch(aclient, oi_url, {'status': 'DISPATCHED'})
    check('intercity DISPATCHED now rejected for pickup agent (hub flow)',
          resp.status_code == 400, f"status={resp.status_code} body={resp.content[:120]}")

    resp = patch(aclient, oi_url, {'status': 'DROPPED_AT_ORIGIN_HUB'})
    body = resp.json()
    oi.refresh_from_db()
    pune_hub = DeliveryHub.objects.get(city='Pune', name='Central Hub')
    check('pickup agent: DROPPED_AT_ORIGIN_HUB at Pune Central Hub',
          resp.status_code == 200 and oi.status == 'DROPPED_AT_ORIGIN_HUB' and body.get('hub') == pune_hub.name,
          f"status={resp.status_code} hub={body.get('hub')}")

    # ---- admin line-haul -------------------------------------------------
    resp = patch(admin_client, admin_status_url, {'status': 'AT_DESTINATION_HUB'})
    check('admin: jumping straight to AT_DESTINATION_HUB rejected',
          resp.status_code == 400, f"status={resp.status_code}")

    resp = patch(admin_client, admin_status_url, {'status': 'IN_TRANSIT'})
    check('admin: IN_TRANSIT (Pune hub -> Hyderabad hub)', resp.status_code == 200,
          f"status={resp.status_code}")

    resp = patch(admin_client, admin_status_url, {'status': 'AT_DESTINATION_HUB'})
    body = resp.json()
    oi.refresh_from_db()
    delivery_agent = oi.delivery_agent
    check('admin: AT_DESTINATION_HUB auto-assigns Hyderabad delivery agent',
          resp.status_code == 200 and oi.status == 'AT_DESTINATION_HUB'
          and delivery_agent is not None
          and delivery_agent.profile.city.lower() == 'hyderabad',
          f"delivery_agent={delivery_agent.username if delivery_agent else None}")

    # ---- leg 2: collect from hub, deliver with OTP -----------------------
    dclient = Client(); dclient.force_login(delivery_agent)
    resp = patch(aclient, oi_url, {'status': 'DELIVERED', 'otp': '0000'})
    check('wrong-leg DELIVERED (pickup agent) still rejected', resp.status_code == 404,
          f"status={resp.status_code}")

    resp = patch(dclient, oi_url, {'status': 'DELIVERED', 'otp': '9999'})
    check('delivery agent: wrong OTP rejected', resp.status_code == 400, f"status={resp.status_code}")

    resp = patch(dclient, oi_url, {'status': 'DELIVERED', 'otp': order.delivery_otp})
    oi.refresh_from_db(); item.refresh_from_db()
    check('delivery agent: DELIVERED with OTP -> item SOLD',
          resp.status_code == 200 and oi.status == 'DELIVERED' and item.status == 'SOLD',
          f"oi={oi.status} item={item.status}")

    # ================ REGRESSION: INTRA-CITY LADDER =======================
    intra_item = make_item(seller, 'HubTest IntraCity', 'Hyderabad')
    cart_is_only(buyer, intra_item)
    resp = checkout_as(client, '500089')
    order2 = Order.objects.filter(user=buyer).order_by('-id').first()
    intra_oi = OrderItem.objects.filter(order=order2, item=intra_item).first()
    intra_agent = intra_oi.assigned_agent if intra_oi else None
    if intra_agent:
        iclient = Client(); iclient.force_login(intra_agent)
        iurl = f'/api/deliveries/agent/deliveries/{intra_oi.id}/update/'
        resp = patch(iclient, iurl, {'status': 'PICKED_UP'})
        resp = patch(iclient, iurl, {'status': 'DISPATCHED'})
        intra_oi.refresh_from_db()
        check('intra-city: PICKED_UP -> DISPATCHED still works',
              resp.status_code == 200 and intra_oi.status == 'DISPATCHED',
              f"status={resp.status_code} oi={intra_oi.status} agent={intra_agent.username}")
        resp = patch(iclient, iurl, {'status': 'DELIVERED', 'otp': order2.delivery_otp})
        intra_oi.refresh_from_db()
        check('intra-city: DELIVERED from DISPATCHED (same agent, OTP)',
              resp.status_code == 200 and intra_oi.status == 'DELIVERED',
              f"status={resp.status_code}")
    else:
        check('intra-city regression setup', False,
              f"oi={intra_oi} agent={intra_agent}")

    # ============= LEGACY TOLERANCE: PRE-HUB DISPATCHED ITEM ==============
    legacy_item = make_item(seller, 'HubTest Legacy', 'Pune')
    cart_is_only(buyer, legacy_item)
    resp = checkout_as(client, '500045')
    order3 = Order.objects.filter(user=buyer).order_by('-id').first()
    legacy_oi = OrderItem.objects.filter(order=order3, item=legacy_item).first()
    legacy_oi.status = 'DISPATCHED'
    legacy_oi.delivery_agent = User.objects.filter(profile__is_delivery_agent=True,
                                                   profile__is_verified=True,
                                                   profile__city__iexact='Hyderabad').first()
    legacy_oi.save()
    resp = patch(admin_client, f'/api/deliveries/admin/deliveries/{legacy_oi.id}/status/',
                 {'status': 'AT_DESTINATION_HUB'})
    legacy_oi.refresh_from_db()
    check('legacy DISPATCHED intercity -> admin AT_DESTINATION_HUB accepted',
          resp.status_code == 200 and legacy_oi.status == 'AT_DESTINATION_HUB',
          f"status={resp.status_code}")
    lclient = Client(); lclient.force_login(legacy_oi.delivery_agent)
    resp = patch(lclient, f'/api/deliveries/agent/deliveries/{legacy_oi.id}/update/',
                 {'status': 'DELIVERED', 'otp': order3.delivery_otp})
    legacy_oi.refresh_from_db()
    check('legacy tolerance: DELIVERED from DISPATCHED (pre-hub item)',
          resp.status_code == 200 and legacy_oi.status == 'DELIVERED',
          f"status={resp.status_code}")

    transaction.savepoint_rollback(sid)

print()
print('post-rollback residue: orders for mohan123 =', Order.objects.filter(user=buyer).count(),
      '| HubTest items =', Item.objects.filter(title__startswith='HubTest').count())
fails = [r for r in RESULTS if not r[1]]
print(f"== {len(RESULTS) - len(fails)}/{len(RESULTS)} scenarios passed ==")
