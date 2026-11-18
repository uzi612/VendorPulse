"""
Zones feature scenario test - runs against the real DB but wraps everything
in an atomic transaction that is ROLLED BACK at the end, so no test data
persists. Uses Django's test client (no dev server needed, CSRF disabled).

Scenarios:
  1. Buyer checkout with pincode 400001 -> zone + city derived, order saved.
  2. Intercity order (pickup city != buyer city) walks the hub ladder
     (PICKED_UP -> DROPPED_AT_ORIGIN_HUB -> admin IN_TRANSIT -> admin
     AT_DESTINATION_HUB) and the arrival auto-assigns a delivery_agent from
     the buyer's city/zone.
  3. Wrong-leg DELIVERED (pickup agent tries to deliver intercity item) -> 404.
  4. DELIVERED by the correct delivery agent: OTP enforced (wrong OTP -> 400,
     right OTP -> DELIVERED + item SOLD).
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vendorpulse_core.settings')
django.setup()

from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')  # Django test client default host

import json
from decimal import Decimal
from django.db import transaction
from django.test import Client
from django.contrib.auth.models import User

from orders.models import Order, OrderItem
from products.models import Item, Cart, CartItem
from accounts.models import Profile
from locations.models import Zone

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print(('PASS' if ok else 'FAIL'), '-', name, ('| ' + detail if detail else ''))


with transaction.atomic():
    sid = transaction.savepoint()

    buyer = User.objects.get(username='mohan123')
    agent_user = User.objects.filter(profile__is_delivery_agent=True,
                                     profile__is_verified=True).first()
    print(f"buyer={buyer.username}  test agent={agent_user.username if agent_user else None}")

    mumbai_zone1 = Zone.objects.get(city='Mumbai', name='Zone 1')

    # Find (or make) an intercity item: pickup city != Mumbai, owned by a
    # seller other than the buyer.
    seller = User.objects.filter(username='rohan123').first() or \
        User.objects.exclude(pk=buyer.pk).first()
    item = Item.objects.filter(approval_status='APPROVED').exclude(
        location='Mumbai').exclude(seller=buyer).first()
    created_item = None
    if item is None:
        created_item = Item.objects.create(
            seller=seller, title='ScenarioTest Item', description='temp',
            price=Decimal('499.00'), condition='GOOD', status='AVAILABLE',
            approval_status='APPROVED', location='Delhi')
        item = created_item

    pickup_city = item.location
    intercity = pickup_city != 'Mumbai'
    print(f"item #{item.id} '{item.title}' pickup_city={pickup_city} "
          f"(intercity vs Mumbai: {intercity})")

    cart, _ = Cart.objects.get_or_create(user=buyer)
    # get_or_create: a previous run that was killed before its rollback can
    # leave the item in the cart, and a plain create() then trips the
    # (cart, item) unique constraint. Everything below runs inside the
    # savepoint, so any pre-existing row is restored at the end.
    ci, _ = CartItem.objects.get_or_create(cart=cart, item=item)

    client = Client()
    client.force_login(buyer)

    # ---- 1. Pincode-first checkout -------------------------------------
    resp = client.post('/api/products/checkout/',
                       data=json.dumps({'pincode': '400001', 'phone': '9876543210',
                                        'address': 'Flat 12, Test Apartments'}),
                       content_type='application/json')
    check('checkout with pincode 400001 -> 201/200',
          resp.status_code in (200, 201), f"status={resp.status_code} body={resp.content[:200]}")

    # invalid pincode is rejected
    resp2 = client.post('/api/products/checkout/',
                        data=json.dumps({'pincode': '999999', 'phone': '9876543210'}),
                        content_type='application/json')
    check('unserviceable pincode 999999 rejected', resp2.status_code == 400,
          f"status={resp2.status_code}")

    order = Order.objects.filter(user=buyer).order_by('-id').first()
    ok = (order is not None and order.pincode == '400001'
          and order.shipping_city == 'Mumbai'
          and order.shipping_zone_id == mumbai_zone1.id
          and order.shipping_zone_name == 'Zone 1')
    check('order saved zone snapshot (pincode/city/zone)',
          ok, f"order={order.id if order else None} pincode={getattr(order, 'pincode', None)} "
              f"city={getattr(order, 'shipping_city', None)} zone={getattr(order, 'shipping_zone', None)}")

    oi = OrderItem.objects.filter(order=order, item=item).first() if order else None
    check('order item created + auto-assigned pickup agent',
          oi is not None and oi.assigned_agent is not None and oi.status == 'PICKUP_SCHEDULED',
          f"status={getattr(oi, 'status', None)} agent={getattr(oi, 'assigned_agent', None)}")

    if oi is None or oi.assigned_agent is None:
        print('!! cannot continue without an assigned pickup agent')
        transaction.savepoint_rollback(sid)
        raise SystemExit(0)

    pickup_agent = oi.assigned_agent
    # Force the pickup agent's city so they can be picked (script convenience):
    # keep as-is; authorization is user-based, not city-based.

    aclient = Client()
    aclient.force_login(pickup_agent)

    # ---- 2. PICKED_UP -> DISPATCHED (intercity handover) ---------------
    resp = aclient.patch(f'/api/deliveries/agent/deliveries/{oi.id}/update/',
                         data=json.dumps({'status': 'PICKED_UP'}),
                         content_type='application/json')
    check('pickup agent: PICKED_UP accepted', resp.status_code == 200,
          f"status={resp.status_code} body={resp.content[:160]}")

    if intercity:
        # Pickup leg ends at the origin hub - intercity items are never
        # DISPATCHED by the pickup agent (hub flow).
        resp = aclient.patch(f'/api/deliveries/agent/deliveries/{oi.id}/update/',
                             data=json.dumps({'status': 'DROPPED_AT_ORIGIN_HUB'}),
                             content_type='application/json')
        check('pickup agent: DROPPED_AT_ORIGIN_HUB accepted', resp.status_code == 200,
              f"status={resp.status_code} body={resp.content[:160]}")

        # Admin line-haul: departs the origin hub, then arrives at the
        # destination hub - which is where leg 2 is assigned.
        admin = (User.objects.filter(username='Admin123').first()
                 or User.objects.filter(is_superuser=True).first())
        mclient = Client()
        mclient.force_login(admin)

        resp = mclient.patch(f'/api/deliveries/admin/deliveries/{oi.id}/status/',
                             data=json.dumps({'status': 'IN_TRANSIT'}),
                             content_type='application/json')
        check('admin: IN_TRANSIT accepted', resp.status_code == 200,
              f"status={resp.status_code} body={resp.content[:160]}")

        resp = mclient.patch(f'/api/deliveries/admin/deliveries/{oi.id}/status/',
                             data=json.dumps({'status': 'AT_DESTINATION_HUB'}),
                             content_type='application/json')
        body = resp.json()
        oi.refresh_from_db()
        zone_match = (oi.delivery_agent is not None
                      and oi.delivery_agent.profile.zone_id == order.shipping_zone_id
                      and (oi.delivery_agent.profile.city or '').lower()
                          == (order.shipping_city or '').lower())
        check('arrival auto-assigns delivery_agent from buyer city/zone',
              resp.status_code == 200 and oi.delivery_agent is not None and zone_match,
              f"delivery_agent={body.get('delivery_agent')} "
              f"(city={getattr(oi.delivery_agent.profile, 'city', None) if oi.delivery_agent else None}, "
              f"zone={getattr(oi.delivery_agent.profile, 'zone', None) if oi.delivery_agent else None}, "
              f"expected={order.shipping_city}/{order.shipping_zone})")

        # ---- 3. Wrong-leg DELIVERED -> rejected ------------------------
        resp = aclient.patch(f'/api/deliveries/agent/deliveries/{oi.id}/update/',
                             data=json.dumps({'status': 'DELIVERED', 'otp': '0000'}),
                             content_type='application/json')
        check('wrong-leg DELIVERED (pickup agent) rejected',
              resp.status_code == 404, f"status={resp.status_code}")

        # ---- 4. Correct delivery agent + OTP enforcement ---------------
        dclient = Client()
        dclient.force_login(oi.delivery_agent)
        resp = dclient.patch(f'/api/deliveries/agent/deliveries/{oi.id}/update/',
                             data=json.dumps({'status': 'DELIVERED', 'otp': '0000'}),
                             content_type='application/json')
        check('wrong OTP rejected (400)', resp.status_code == 400,
              f"status={resp.status_code}")

        right_otp = order.delivery_otp
        resp = dclient.patch(f'/api/deliveries/agent/deliveries/{oi.id}/update/',
                             data=json.dumps({'status': 'DELIVERED', 'otp': right_otp}),
                             content_type='application/json')
        oi.refresh_from_db()
        item.refresh_from_db()
        check('correct OTP -> DELIVERED + item SOLD',
              resp.status_code == 200 and oi.status == 'DELIVERED' and item.status == 'SOLD',
              f"status={resp.status_code} oi={oi.status} item={item.status}")

    # cleanup in-transaction: remove the cart row we added
    ci.delete()

    transaction.savepoint_rollback(sid)

# Outside the transaction: verify the rollback left no residue
print()
print('post-rollback residue check: orders for mohan123 =',
      Order.objects.filter(user=buyer).count(),
      '| scenario item exists =', Item.objects.filter(title='ScenarioTest Item').exists())

fails = [r for r in RESULTS if not r[1]]
print()
print(f"== {len(RESULTS) - len(fails)}/{len(RESULTS)} scenarios passed ==")

