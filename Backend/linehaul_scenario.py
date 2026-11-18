"""
Timed line-haul scenario test - the hub leg now runs on a schedule.

Everything runs inside one atomic transaction that is ROLLED BACK (no
residue), CSRF disabled, throttles lifted.

Flow under test:
  admin dispatches IN_TRANSIT  -> ETA stamped from the HubRoute duration
  settle before ETA            -> no arrival (item stays IN_TRANSIT)
  time-travel ETA into the past -> settle arrives the item at the
                                   destination hub + auto-assigns the
                                   buyer-city delivery agent (+ notifications)
  double settle                -> idempotent, no duplicate work
  admin "arrive early"         -> manual override still works
  legacy IN_TRANSIT row (no ETA) -> backfilled on first settle, then arrives
  buyer tracking endpoint      -> exposes the ETA / settled status
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vendorpulse_core.settings')
django.setup()

from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

import json
from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.test import Client
from django.contrib.auth.models import User

from rest_framework.settings import api_settings
api_settings.DEFAULT_THROTTLE_RATES = {
    **api_settings.DEFAULT_THROTTLE_RATES,
    'user': '100000/min', 'checkout': '100000/min', 'otp_verify': '100000/min',
}

from orders.models import Order, OrderItem
from products.models import Item, Cart
from locations.models import DeliveryHub
from notifications.models import Notification
from deliveries.linehaul import (
    settle_linehaul_arrivals, linehaul_eta_hours, DEFAULT_LINEHAUL_HOURS,
)

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
    cart, _ = Cart.objects.get_or_create(user=buyer)
    cart.items.all().delete()
    cart.items.create(item=item)


def run_intercity_ladder_to_origin_hub(buyer, seller, title, pickup_city, dest_pincode):
    """Checkout + pickup leg up to DROPPED_AT_ORIGIN_HUB. Returns (item, order_item)."""
    item = make_item(seller, title, pickup_city)
    cart_is_only(buyer, item)
    client = Client(); client.force_login(buyer)
    resp = checkout_as(client, dest_pincode)
    assert resp.status_code in (200, 201), f"checkout failed: {resp.status_code}"
    order = Order.objects.filter(user=buyer).order_by('-id').first()
    oi = OrderItem.objects.filter(order=order).first()
    pickup_agent = oi.assigned_agent
    aclient = Client(); aclient.force_login(pickup_agent)
    url = f'/api/deliveries/agent/deliveries/{oi.id}/update/'
    assert patch(aclient, url, {'status': 'PICKED_UP'}).status_code == 200
    assert patch(aclient, url, {'status': 'DROPPED_AT_ORIGIN_HUB'}).status_code == 200
    oi.refresh_from_db()
    return item, oi


counts_before = {m: m.objects.count() for m in [Order, OrderItem, Notification]}

with transaction.atomic():
    sid = transaction.savepoint()

    buyer = User.objects.get(username='mohan123')
    seller = User.objects.get(username='rohan123')
    admin = User.objects.filter(is_staff=True).first()
    admin_client = Client(); admin_client.force_login(admin)

    # ================= 1. DISPATCH STAMPS THE ETA =========================
    # Pune -> Hyderabad has an explicit seed override (18h).
    item, oi = run_intercity_ladder_to_origin_hub(
        buyer, seller, 'LinehaulTest A', 'Pune', '500001')
    admin_url = f'/api/deliveries/admin/deliveries/{oi.id}/status/'

    route_hours = linehaul_eta_hours('Pune', 'Hyderabad')
    resp = patch(admin_client, admin_url, {'status': 'IN_TRANSIT'})
    body = resp.json()
    oi.refresh_from_db()
    check('dispatch IN_TRANSIT -> 200 with transit_hours + eta in response',
          resp.status_code == 200 and body.get('transit_hours') == route_hours
          and bool(body.get('linehaul_eta_at')),
          f"hours={body.get('transit_hours')} eta={body.get('linehaul_eta_at')}")
    check('OrderItem stamped: departed_at + eta_at = departed + route hours',
          oi.status == 'IN_TRANSIT' and oi.linehaul_departed_at is not None
          and oi.linehaul_eta_at is not None
          and abs((oi.linehaul_eta_at - oi.linehaul_departed_at
                   - timedelta(hours=route_hours)).total_seconds()) < 5,
          f"route_hours={route_hours}")

    # ================= 2. SETTLE BEFORE ETA: NO-OP ========================
    arrived = settle_linehaul_arrivals()
    oi.refresh_from_db()
    check('settle before ETA: nothing arrives', arrived == 0 and oi.status == 'IN_TRANSIT',
          f"arrived={arrived} status={oi.status}")

    # ================= 3. TIME-TRAVEL -> AUTO ARRIVAL =====================
    eta_seen = oi.linehaul_eta_at
    OrderItem.objects.filter(pk=oi.pk).update(
        linehaul_eta_at=timezone.now() - timedelta(minutes=1))
    arrived = settle_linehaul_arrivals()
    oi.refresh_from_db()
    delivery_agent = oi.delivery_agent
    check('eta elapsed -> settle arrives item at destination hub',
          arrived == 1 and oi.status == 'AT_DESTINATION_HUB',
          f"arrived={arrived} status={oi.status}")
    check('auto-arrival assigned the buyer-city delivery agent',
          delivery_agent is not None
          and delivery_agent.profile.city.lower() == 'hyderabad',
          f"agent={delivery_agent.username if delivery_agent else None}")

    agent_task = Notification.objects.filter(
        recipient=delivery_agent, notification_type='NEW_TASK').order_by('-id').first()
    check('arrival notified the delivery agent (collect-from-hub task)',
          agent_task is not None and 'collect' in agent_task.message.lower()
          and 'Central Hub' in agent_task.message,
          f"msg={agent_task.message[:70] if agent_task else None}...")

    # ================= 4. IDEMPOTENCE / NO DOUBLE-FIRE ====================
    arrived_again = settle_linehaul_arrivals()
    oi.refresh_from_db()
    check('second settle is a no-op (no duplicate transition)',
          arrived_again == 0 and oi.status == 'AT_DESTINATION_HUB',
          f"arrived={arrived_again}")

    # ================= 5. ADMIN "ARRIVE EARLY" OVERRIDE ===================
    item2, oi2 = run_intercity_ladder_to_origin_hub(
        buyer, seller, 'LinehaulTest B', 'Mumbai', '110001')   # -> Delhi
    resp = patch(admin_client, f'/api/deliveries/admin/deliveries/{oi2.id}/status/',
                 {'status': 'IN_TRANSIT'})
    check('override item dispatched (Mumbai -> Delhi)',
          resp.status_code == 200, f"status={resp.status_code}")
    resp = patch(admin_client, f'/api/deliveries/admin/deliveries/{oi2.id}/status/',
                 {'status': 'AT_DESTINATION_HUB'})
    oi2.refresh_from_db()
    check('manual AT_DESTINATION_HUB still works before the ETA (arrive early)',
          resp.status_code == 200 and oi2.status == 'AT_DESTINATION_HUB'
          and oi2.delivery_agent is not None
          and oi2.delivery_agent.profile.city.lower() == 'delhi',
          f"status={resp.status_code} agent={oi2.delivery_agent.username if oi2.delivery_agent else None}")

    # ================= 6. LEGACY ROW: BACKFILL THEN ARRIVE ================
    item3, oi3 = run_intercity_ladder_to_origin_hub(
        buyer, seller, 'LinehaulTest C', 'Mumbai', '700001')   # -> Kolkata
    # Simulate a pre-feature row: IN_TRANSIT with no timestamps (bypasses
    # the dispatch endpoint; update() fires no signals).
    OrderItem.objects.filter(pk=oi3.pk).update(
        status='IN_TRANSIT', linehaul_departed_at=None, linehaul_eta_at=None)
    oi3.refresh_from_db()
    arrived = settle_linehaul_arrivals()
    oi3.refresh_from_db()
    check('legacy IN_TRANSIT row: backfilled with a future ETA (not insta-arrived)',
          oi3.status == 'IN_TRANSIT' and oi3.linehaul_eta_at is not None
          and oi3.linehaul_eta_at > timezone.now(),
          f"eta={oi3.linehaul_eta_at}")
    OrderItem.objects.filter(pk=oi3.pk).update(
        linehaul_eta_at=timezone.now() - timedelta(minutes=1))
    arrived = settle_linehaul_arrivals()
    oi3.refresh_from_db()
    check('backfilled legacy row arrives once its ETA passes',
          arrived >= 1 and oi3.status == 'AT_DESTINATION_HUB'
          and oi3.delivery_agent.profile.city.lower() == 'kolkata',
          f"arrived={arrived} agent={oi3.delivery_agent.username}")

    # ================= 7. BUYER TRACKING EXPOSES THE ETA ==================
    item4, oi4 = run_intercity_ladder_to_origin_hub(
        buyer, seller, 'LinehaulTest D', 'Pune', '560001')     # -> Bengaluru
    patch(admin_client, f'/api/deliveries/admin/deliveries/{oi4.id}/status/',
          {'status': 'IN_TRANSIT'})
    oi4.refresh_from_db()
    track = Client(); track.force_login(buyer)
    resp = track.get(f'/api/orders/track/{oi4.tracking_number}/')
    body = resp.json()
    check('tracking endpoint shows IN_TRANSIT + ETA while in flight',
          resp.status_code == 200 and body.get('status') == 'IN_TRANSIT'
          and bool(body.get('linehaul_eta_at')),
          f"eta={body.get('linehaul_eta_at')}")
    OrderItem.objects.filter(pk=oi4.pk).update(
        linehaul_eta_at=timezone.now() - timedelta(minutes=1))
    resp = track.get(f'/api/orders/track/{oi4.tracking_number}/')
    body = resp.json()
    oi4.refresh_from_db()
    check('tracking settle-on-read: buyer sees AT_DESTINATION_HUB without admin click',
          resp.status_code == 200 and body.get('status') == 'AT_DESTINATION_HUB'
          and oi4.status == 'AT_DESTINATION_HUB',
          f"status={body.get('status')}")

    # ================= 8. ADMIN LIST CARRIES THE ETA ======================
    item5, oi5 = run_intercity_ladder_to_origin_hub(
        buyer, seller, 'LinehaulTest E', 'Delhi', '600001')    # -> Chennai
    patch(admin_client, f'/api/deliveries/admin/deliveries/{oi5.id}/status/',
          {'status': 'IN_TRANSIT'})
    resp = admin_client.get('/api/deliveries/admin/deliveries/?all=1')
    row = next((r for r in resp.json() if r['id'] == oi5.id), None)
    check('admin deliveries list carries linehaul_eta_at for in-transit rows',
          row is not None and row.get('linehaul_eta_at') is not None,
          f"eta={row.get('linehaul_eta_at') if row else None}")

    # ================= 9. DEFAULT ROUTE DURATION ==========================
    check('unseeded pair falls back to 24h default',
          DEFAULT_LINEHAUL_HOURS == 24
          and linehaul_eta_hours('Chandigarh', 'Indore') == 24,
          f"Chandigarh->Indore={linehaul_eta_hours('Chandigarh', 'Indore')}h")

    transaction.savepoint_rollback(sid)

print()
failed = [r for r in RESULTS if not r[1]]
print(f"===== LINEHAUL SCENARIO: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed =====")
residue = {m.__name__: (m.objects.count() - counts_before[m]) for m in counts_before}
print("Residue after rollback (should all be 0):", residue)
