"""
Schema-only annotations for the OpenAPI document.

Views keep containing nothing but request/response logic - no schema
decorators - so everything documentation-related lives here instead. The
module is registered as a drf-spectacular POSTPROCESSING_HOOK (see
SPECTACULAR_SETTINGS) and is keyed by (METHOD, path). It adds:

  * a short summary + description per endpoint (docstrings still win when the
    view has one, because the hook only overrides when told to),
  * query parameters (page/page_size/all + endpoint-specific filters),
  * request bodies,
  * response schemas (reusable components declared below),
  * domain tags, de-duplicated security entries, and a generic JSON-object
    fallback instead of drf-spectacular's "No response body".

Drift is surfaced, not swallowed: any DOCS entry that matches no generated
operation is reported as a drf-spectacular warning during
`manage.py spectacular --validate`.

Paths here are the /api-mounted ones from vendorpulse_core.schema_urls; the
bare mounts are deliberately left out of the public contract.
"""
from drf_spectacular.drainage import warn
from drf_spectacular.openapi import AutoSchema

# ---------------------------------------------------------------------------
# Tiny schema builders
# ---------------------------------------------------------------------------


def S(desc=None, enum=None, fmt=None):
    schema = {'type': 'string'}
    if enum:
        schema['enum'] = enum
    if fmt:
        schema['format'] = fmt
    if desc:
        schema['description'] = desc
    return schema


def I(desc=None):
    schema = {'type': 'integer'}
    if desc:
        schema['description'] = desc
    return schema


def N(desc=None):
    schema = {'type': 'number'}
    if desc:
        schema['description'] = desc
    return schema


def B(desc=None):
    schema = {'type': 'boolean'}
    if desc:
        schema['description'] = desc
    return schema


def A(items, desc=None):
    schema = {'type': 'array', 'items': items}
    if desc:
        schema['description'] = desc
    return schema


def O(props, required=None, desc=None, freeform=False):
    schema = {'type': 'object'}
    if freeform:
        schema['additionalProperties'] = True
    else:
        schema['properties'] = props
    if required:
        schema['required'] = required
    if desc:
        schema['description'] = desc
    return schema


def NULL(schema):
    """Same schema, but nullable (OpenAPI 3.0 nullability)."""
    return {**schema, 'nullable': True}


def R(name):
    return {'$ref': f'#/components/schemas/{name}'}


def body(schema, required=True):
    return {'required': required, 'schema': schema}


def ok(schema, description='Successful response'):
    return {'description': description,
            'content': {'application/json': {'schema': schema}}}


def no_content(description='No content'):
    return {'description': description}


def q(name, schema, desc, required=False):
    return {'name': name, 'in': 'query', 'required': required,
            'schema': schema, 'description': desc}


def page(item_schema, extra_props=None):
    props = {
        'count': I('Total matching rows.'),
        'total_pages': I('Pages at the current page_size.'),
        'page': I('1-based current page.'),
        'page_size': I('Rows per page.'),
        'results': A(item_schema),
    }
    if extra_props:
        props.update(extra_props)
    return O(props, required=['count', 'results'])


PAGE_PARAMS = [
    q('page', I(), '1-based page number (default 1).'),
    q('page_size', I(), 'Rows per page (default varies, max 100).'),
    q('all', S(enum=['1']),
      'Pass 1 to bypass pagination and receive a flat JSON array.'),
]

FREE = O({}, freeform=True,
         desc='Free-form object (shape is stable but not modelled in detail).')


# ---------------------------------------------------------------------------
# Reusable components
# ---------------------------------------------------------------------------

COMPONENTS = {
    'Error': O({'error': S('Human-readable failure reason.')},
               required=['error']),
    'Message': O({'message': S()}, required=['message']),
    'UserProfile': O({
        'city': NULL(S()),
        'phone': NULL(S()),
        'is_delivery_agent': B(),
    }),
    'User': O({
        'id': I(),
        'username': S(),
        'email': S(),
        'profile': R('UserProfile'),
    }),
    'Item': O({
        'id': I(),
        'seller': I('Seller user id.'),
        'seller_username': S(),
        'is_seller_verified': B(),
        'seller_rating': NULL(N('Average seller rating, one decimal.')),
        'seller_rating_count': NULL(I()),
        'category': S(enum=['CLOTHING', 'ELECTRONICS', 'FURNITURE',
                            'BOOKS', 'VEHICLES', 'OTHER']),
        'title': S(),
        'description': S(),
        'price': S('Decimal serialized as a string, e.g. "499.00".'),
        'condition': S(enum=['NEW', 'LIKE_NEW', 'GOOD', 'FAIR']),
        'status': S(enum=['AVAILABLE', 'RESERVED', 'SOLD']),
        'approval_status': S(enum=['PENDING', 'APPROVED', 'REJECTED']),
        'rejection_reason': NULL(S()),
        'image': NULL(S(fmt='uri')),
        'location': S('Pickup city.'),
        'zone_id': NULL(I()),
        'pickup_zone': NULL(S('Zone name inside the pickup city.')),
        'address': S(),
        'created_at': S(fmt='date-time'),
        'updated_at': S(fmt='date-time'),
    }, required=['id', 'title', 'price', 'condition', 'status',
                 'approval_status']),
    'ItemWrite': O({
        'category': S(enum=['CLOTHING', 'ELECTRONICS', 'FURNITURE',
                            'BOOKS', 'VEHICLES', 'OTHER']),
        'title': S(),
        'description': S(),
        'price': S('Decimal, e.g. "499.00".'),
        'condition': S(enum=['NEW', 'LIKE_NEW', 'GOOD', 'FAIR']),
        'image': NULL(S(fmt='binary')),
        'location': S('Pickup city; must be one of the supported cities.'),
        'address': S('Street address the pickup agent navigates to.'),
        'zone': I('Optional pickup zone id; must belong to `location`. '
                  'Defaults to the seller profile zone.'),
    }, desc='Writable listing fields. seller/status/approval_status are '
            'server-controlled.'),
    'CartItem': O({
        'id': I(),
        'cart': I(),
        'item': R('Item'),
        'added_at': S(fmt='date-time'),
    }),
    'Cart': O({
        'id': I(),
        'user': I(),
        'items': A(R('CartItem')),
        'created_at': S(fmt='date-time'),
    }),
    'Zone': O({
        'id': I(),
        'city': S(),
        'name': S(),
        'pincode_from': I(),
        'pincode_to': I(),
    }),
    'AdminZone': O({
        'id': I(),
        'city': S(),
        'name': S(),
        'pincode_from': I(),
        'pincode_to': I(),
        'is_active': B(),
        'agents': I('Active delivery agents assigned to this zone.'),
    }),
    'ZoneWrite': O({
        'city': S('Must be one of the supported cities.'),
        'name': S('Display name, e.g. "Zone 1".'),
        'pincode_from': I('6-digit lower bound (inclusive).'),
        'pincode_to': I('6-digit upper bound (inclusive).'),
    }, required=['city', 'name', 'pincode_from', 'pincode_to']),
    'Hub': O({
        'id': I(),
        'city': S(),
        'name': S(),
        'address': S(),
        'zone': NULL(I()),
        'zone_name': S(),
        'is_active': B(),
    }),
    'HubWrite': O({
        'city': S(),
        'name': S(),
        'address': S('Street address agents navigate to (<= 255 chars).'),
        'zone': NULL(I('Optional zone id; must belong to `city`.')),
    }, required=['city', 'name', 'address']),
    'DeliveryRow': O({
        'id': I('Order item id.'),
        'order_id': I(),
        'shipping_address': S(),
        'shipping_city': S(),
        'phone': S(),
        'item_title': S(),
        'item_price': S('Decimal as a string.'),
        'seller_username': S(),
        'seller_address': S(),
        'pickup_address': S(),
        'status': S('Current ladder status.'),
        'tracking_number': S('Format TRK-<order id>.'),
        'cancel_reason': NULL(S()),
        'cancel_note': NULL(S()),
        'agent_username': NULL(S('Pickup agent.')),
        'assigned_agent': NULL(I()),
        'delivery_agent': NULL(I('Leg-2 agent, intercity only.')),
        'delivery_agent_username': NULL(S()),
        'pickup_zone': S(),
        'shipping_zone': S(),
        'pincode': S(),
        'is_intercity': B(),
        'origin_hub': S(),
        'destination_hub': S(),
        'seller_id': I(),
        'is_seller_verified': B(),
        'linehaul_eta_at': NULL(S(fmt='date-time',
                                  desc='Expected destination-hub arrival '
                                       'while IN_TRANSIT.')),
        # Money snapshot (vendorpulse_core.pricing)
        'item_subtotal': S('Item price as a decimal string.'),
        'delivery_charge': S('Buyer delivery fee for this item.'),
        'platform_fee': S('5% commission on the item price.'),
        'seller_payout': S('Item price minus the platform fee.'),
        'agent_pay': S('Total agent pay across both legs.'),
        'platform_earnings': S('Commission + delivery fee - agent pay.'),
        'return_status': NULL(S(enum=['REQUESTED', 'APPROVED', 'REJECTED'])),
    }),
    'AgentTask': O({
        'id': I('Order item id.'),
        'order_id': I(),
        'shipping_address': S(),
        'shipping_city': S(),
        'shipping_zone': S(),
        'pincode': S(),
        'pickup_zone': S(),
        'is_intercity': B(),
        'origin_hub': NULL(O({'name': S(), 'address': S()})),
        'destination_hub': NULL(O({'name': S(), 'address': S()})),
        'phone': S(),
        'item_title': S(),
        'seller_username': S(),
        'seller_address': S(),
        'pickup_address': S(),
        'status': S(),
        'tracking_number': S(),
        'my_role': S(enum=['pickup', 'delivery'],
                     desc='Which leg this task is for the caller.'),
        'my_pay': S('What the caller earns for this task (pickup-leg or '
                    'delivery-leg fee from the checkout snapshot).'),
    }),
    'StaffRow': O({
        'id': I(),
        'username': S(),
        'email': S(),
        'address': S('City (stored on the profile).'),
        'zone': NULL(I()),
        'zone_name': S(),
        'is_staff': B(),
        'is_agent': B(),
        'is_verified': B(),
    }),
    'DisputeRow': O({
        'id': I(),
        'status': S(enum=['OPEN', 'RESOLVED', 'REJECTED']),
        'reason': S(enum=['DAMAGED', 'NOT_AS_DESCRIBED', 'NOT_RECEIVED',
                          'OTHER']),
        'description': S(),
        'item_title': S(),
        'item_price': S(),
        'order_id': I(),
        'tracking_number': S(),
        'buyer': S(),
        'seller': S(),
        'created_at': S(),
        'resolution_note': NULL(S()),
        'resolved_by': NULL(S()),
        'resolved_at': NULL(S()),
    }),
    'ReturnRow': O({
        'id': I(),
        'status': S(enum=['REQUESTED', 'APPROVED', 'REJECTED']),
        'reason': S(enum=['CHANGED_MIND', 'DAMAGED', 'NOT_AS_DESCRIBED',
                          'WRONG_ITEM', 'OTHER']),
        'note': NULL(S('Buyer free text.')),
        'item_title': S(),
        'item_price': S(),
        'delivery_charge': S('Delivery fee on this item.'),
        'refund_amount': S('Item price + delivery when approved.'),
        'order_id': I(),
        'tracking_number': S(),
        'buyer': S(),
        'seller': S(),
        'delivered_at': NULL(S()),
        'created_at': S(),
        'admin_note': NULL(S()),
        'resolved_by': NULL(S()),
        'resolved_at': NULL(S()),
    }),
    'ModerationRow': O({
        'id': I(),
        'title': S(),
        'description': S(),
        'price': S(),
        'category': S(),
        'condition': S(),
        'image': NULL(S(fmt='uri')),
        'location': S(),
        'approval_status': S(enum=['PENDING', 'APPROVED', 'REJECTED']),
        'rejection_reason': NULL(S()),
        'seller_username': S(),
        'is_seller_verified': B(),
        'created_at': S(),
        'reviewed_at': NULL(S()),
    }),
    'OrderConfirmation': O({
        'order_id': I(),
        'subtotal': S('Item prices (excluding delivery).'),
        'delivery_charge': S('Sum of the per-item delivery fees.'),
        'total_price': S('subtotal + delivery_charge.'),
        'shipping_address': S(),
        'shipping_city': S(),
        'shipping_zone': S('Zone name snapshot taken at checkout.'),
        'pincode': S(),
        'phone': S(),
        'delivery_otp': S('4-digit code the buyer gives the agent.'),
        'created_at': S(fmt='date-time'),
        'items': A(O({
            'item_title': S(),
            'item_price': S(),
            'status': S(),
            'tracking_number': S(),
        })),
    }),
    'TrackingState': O({
        'tracking_number': S(),
        'item_title': S(),
        'item_price': S(),
        'status': S(),
        'order_id': I(),
        'shipping_address': S(),
        'phone': S(),
        'created_at': S(fmt='date-time'),
        'is_intercity': B(),
        'origin_city': NULL(S()),
        'destination_city': S(),
        'origin_hub': NULL(S()),
        'destination_hub': NULL(S()),
        'linehaul_eta_at': NULL(S(fmt='date-time')),
    }),
    'Notification': O({
        'id': I(),
        'notification_type': S(),
        'message': S(),
        'order_item_id': NULL(I()),
        'tracking_number': NULL(S()),
        'is_read': B(),
        'created_at': S(),
    }),
}


# ---------------------------------------------------------------------------
# Endpoint documentation (keyed by METHOD + generated OpenAPI path)
# ---------------------------------------------------------------------------

SUCCESS_200 = {'200': ok(FREE)}

DOCS = {
    # ----- Accounts ------------------------------------------------------
    ('POST', '/api/accounts/register/'): {
        'summary': 'Register a buyer/seller account',
        'description': 'Creates the user, signs them in (session cookie) and '
                       'returns the public user object. Throttled to '
                       '10 registrations/hour per IP.',
        'request': body(O({
            'username': S(),
            'email': S(),
            'password': S('Minimum 6 characters.'),
            'city': S(),
            'phone': S(),
        }, required=['username', 'email', 'password'])),
        'responses': {
            '201': ok(O({'message': S(), 'user': R('User')}), 'Created'),
            '400': ok(R('Error'), 'Validation failed'),
        },
    },
    ('POST', '/api/accounts/login/'): {
        'summary': 'Log in with username and password',
        'description': 'Creates the Django session and sets the sessionid '
                       'cookie. Throttled to 5 attempts/minute.',
        'request': body(O({'username': S(), 'password': S()},
                          required=['username', 'password'])),
        'responses': {
            '200': ok(O({'message': S(), 'user': R('User')})),
            '400': ok(R('Error'), 'Missing credentials'),
            '401': ok(R('Error'), 'Invalid credentials'),
        },
    },
    ('POST', '/api/accounts/logout/'): {
        'summary': 'Log out and destroy the session',
        'description': 'Flushes the server-side session, so the sessionid '
                       'cookie stops working immediately. Safe to call when '
                       'the visitor is already logged out.',
        'responses': {'200': ok(R('Message'))},
    },
    ('GET', '/api/accounts/me/'): {
        'summary': 'Session bootstrap (also sets the CSRF cookie)',
        'description': 'Public endpoint the SPA calls first: it always sets '
                       'the csrftoken cookie, then reports whether the visitor '
                       'has a session and which portal role it maps to. Call '
                       'it once before any POST/PATCH/PUT so the CSRF header '
                       'can be populated.',
        'responses': {
            '200': ok(O({
                'authenticated': B(),
                'role': S(enum=['admin', 'agent', 'customer'],
                          desc='Derived from is_staff/is_superuser and the '
                               'DeliveryAgent group.'),
                'id': I(),
                'username': S(),
                'email': S(),
                'profile': R('UserProfile'),
            }, desc='When authenticated is false only that flag is returned.')),
        },
    },
    ('POST', '/api/accounts/portal-login/'): {
        'summary': 'Role-gated login for the admin/agent portals',
        'description': 'Same credentials as /login/, but the requested '
                       '`role` is enforced: "admin" needs is_staff or '
                       'is_superuser, "agent" needs the DeliveryAgent group. '
                       'A valid account using the wrong portal gets 403 (the '
                       'session is not created).',
        'request': body(O({
            'username': S(),
            'password': S(),
            'role': S(enum=['admin', 'agent', 'customer']),
        }, required=['username', 'password', 'role'])),
        'responses': {
            '200': ok(O({'user_id': I(), 'username': S(),
                         'role': S(enum=['admin', 'agent', 'customer'])})),
            '401': ok(R('Error'), 'Invalid credentials'),
            '403': ok(R('Error'), 'Account lacks the requested portal role'),
        },
    },
    ('GET', '/api/accounts/profile/'): {
        'summary': 'Profile with buyer orders and seller sales',
        'description': 'One round trip for the account page: header data, '
                       'buyer orders (items nested with their rating, dispute '
                       'and return request / 24-hour return window) and the '
                       'seller sales list with the platform fee and net '
                       'payout per sale.',
        'responses': {
            '200': ok(O({
                'username': S(),
                'email': S(),
                'date_joined': S('Month and year, e.g. "Nov 2026".'),
                'profile': O({'phone': S(), 'city': S()}),
                'orders': A(FREE, 'Buyer orders with nested items.'),
                'sales': A(FREE, 'Order items sold by this user.'),
            })),
        },
    },
    ('PUT', '/api/accounts/profile/'): {
        'summary': 'Update phone and city',
        'description': 'Only these two profile fields are writable here.',
        'request': body(O({'phone': S(), 'city': S()}), required=False),
        'responses': {'200': ok(FREE, 'Updated profile payload (same shape '
                                       'as GET).')},
    },

    # ----- Listings & cart -----------------------------------------------
    ('GET', '/api/products/items/'): {
        'summary': 'Browse approved marketplace listings',
        'description': 'Returns AVAILABLE + APPROVED listings only, newest '
                       'first. Filters compose. Paginated at 24/page by '
                       'default; ?all=1 returns a flat array.',
        'parameters': [
            q('category', S(enum=['CLOTHING', 'ELECTRONICS', 'FURNITURE',
                                  'BOOKS', 'VEHICLES', 'OTHER']), 'Category.'),
            q('condition', S(enum=['NEW', 'LIKE_NEW', 'GOOD', 'FAIR']),
              'Item condition.'),
            q('city', S(), 'Case-insensitive pickup-city match.'),
            q('location', S(), 'Alias of `city`.'),
            q('search', S(), 'Case-insensitive title match.'),
            q('q', S(), 'Alias of `search`.'),
            *PAGE_PARAMS,
        ],
        'responses': {
            '200': ok(page(R('Item')), 'Paginated listings'),
        },
    },
    ('POST', '/api/products/items/'): {
        'summary': 'Create a listing (enters admin moderation)',
        'description': 'The listing is created with status AVAILABLE and '
                       'approval_status PENDING, so it is invisible on the '
                       'marketplace until an admin approves it. Throttled to '
                       '2 listings/hour. Send multipart/form-data when '
                       'uploading an image.',
        'request': body(R('ItemWrite')),
        'responses': {
            '201': ok(R('Item'), 'Created (pending review)'),
            '400': ok(R('Error'), 'Validation failed'),
            '401': ok(R('Error'), 'Authentication required'),
        },
    },
    ('GET', '/api/products/items/{id}/'): {
        'summary': 'Listing detail',
        'description': 'Unapproved listings are visible only to their owner '
                       'and admins; everyone else gets 404.',
        'responses': {'200': ok(R('Item')),
                      '404': ok(R('Error'), 'Not found or not visible')},
    },
    ('PUT', '/api/products/items/{id}/'): {
        'summary': 'Edit a listing (resubmits it for moderation)',
        'description': 'Owner only. Any edit sets approval_status back to '
                       'PENDING and removes the item from buyers\' carts.',
        'request': body(R('ItemWrite'), required=False),
        'responses': {
            '200': ok(R('Item')),
            '400': ok(R('Error'), 'Validation failed'),
            '401': ok(R('Error'), 'Authentication required'),
            '403': ok(R('Error'), 'Not the seller'),
        },
    },
    ('DELETE', '/api/products/items/{id}/'): {
        'summary': 'Delete a listing (owner only)',
        'description': 'Hard delete. Cart lines that still reference the '
                       'listing are removed with it.',
        'responses': {
            '204': no_content('Listing deleted'),
            '401': ok(R('Error')),
            '403': ok(R('Error')),
        },
    },
    ('GET', '/api/products/my-listings/'): {
        'summary': 'Every listing owned by the caller (all statuses)',
        'description': 'Seller inventory view: PENDING and REJECTED listings '
                       '(with rejection_reason) appear next to live ones, '
                       'newest first. Unpaginated.',
        'responses': {'200': ok(A(R('Item')))},
    },
    ('GET', '/api/products/seller-dashboard/'): {
        'summary': 'Seller KPIs: revenue split, fees, payouts and activity',
        'description': 'Gross revenue, the 5% platform fee and the net payout '
                       'are a single reconciliation. Cleared (delivered) and '
                       'pending (in-escrow) payouts only include non-cancelled, '
                       'non-refunded items; approved returns are excluded and '
                       'reported separately in refunded_amount.',
        'responses': {
            '200': ok(O({
                'total_revenue': N('Alias of gross_revenue.'),
                'gross_revenue': N('Item sales, before the platform fee.'),
                'platform_fees': N('5% commission deducted from gross.'),
                'net_payout': N('gross_revenue - platform_fees.'),
                'completed_payouts': N('Delivered items (net payout).'),
                'pending_payouts': N('In-escrow items (net payout).'),
                'refunded_amount': N('Item + delivery refunded on approved '
                                     'returns.'),
                'active_listings_count': I(),
                'pending_review_count': I(),
                'rejected_count': I(),
                'sold_items_count': I('Non-cancelled sales.'),
                'avg_rating': NULL(N()),
                'rating_count': I(),
                'recent_ratings': A(FREE),
                'recent_sales': A(FREE),
            })),
        },
    },
    ('GET', '/api/products/cart/'): {
        'summary': 'Current cart (creates an empty one on first read)',
        'description': 'Cart lines are serialized with the full listing, so '
                       'the cart page renders without follow-up requests.',
        'responses': {'200': ok(R('Cart'))},
    },
    ('POST', '/api/products/cart/add/{item_id}/'): {
        'summary': 'Add a listing to the cart',
        'description': 'Idempotent: adding an item already in the cart '
                       'returns 200 instead of creating a duplicate line.',
        'responses': {
            '201': ok(R('Message'), 'Added'),
            '200': ok(R('Message'), 'Already in cart'),
            '400': ok(R('Error'), 'Own listing or no longer available'),
            '404': ok(R('Error'), 'Listing not found'),
        },
    },
    ('DELETE', '/api/products/cart/remove/{cart_item_id}/'): {
        'summary': 'Remove a cart line',
        'description': 'Scoped to the caller\'s own cart: a cart-line id '
                       'belonging to someone else returns 404 rather than '
                       'leaking its existence.',
        'responses': {
            '204': no_content('Removed'),
            '404': ok(R('Error')),
        },
    },
    ('GET', '/api/products/checkout/quote/'): {
        'summary': 'Live checkout price preview (pincode + cart)',
        'description': 'Resolves the pincode and prices the cart exactly as '
                       'checkout will, so the buyer sees the delivery charge '
                       'before placing the order. Each item is intra-city '
                       '(same-city delivery) or intercity (cross-city hub '
                       'delivery); the per-item fees are returned with the '
                       'totals.',
        'parameters': [q('pincode', S('Exactly 6 digits.'), 'Delivery pincode.',
                         required=True)],
        'responses': {
            '200': ok(O({
                'pincode': S(),
                'city': S(),
                'zone_id': I(),
                'zone_name': S(),
                'items': A(O({
                    'cart_item_id': I(),
                    'item_id': I(),
                    'title': S(),
                    'price': S(),
                    'is_intercity': B(),
                    'delivery_charge': S(),
                    'available': B(),
                })),
                'subtotal': S('Sum of item prices.'),
                'delivery_charge': S('Sum of per-item delivery fees.'),
                'total_price': S('subtotal + delivery_charge.'),
            })),
            '400': ok(R('Error'), 'Empty cart, bad pincode or unserviceable '
                                   'pincode'),
        },
    },
    ('POST', '/api/products/checkout/'): {
        'summary': 'Pincode-first checkout: cart -> order',
        'description': 'The 6-digit pincode is the only location input: it '
                       'resolves the delivery zone and the city server-side. '
                       'All cart items must still be AVAILABLE + APPROVED. '
                       'Prices each item with the route-based delivery fee and '
                       'the 5% platform commission, snapshots the money onto '
                       'the order/item rows, reserves the listings, triggers '
                       'pickup-agent assignment and returns the 4-digit '
                       'delivery OTP. Throttled to 10 checkouts/minute.',
        'request': body(O({
            'pincode': S('Exactly 6 digits; must fall in an active zone.'),
            'phone': S('Contact number for the delivery agent.'),
            'address': S('Optional flat/house detail (<= 255 chars).'),
        }, required=['pincode', 'phone'])),
        'responses': {
            '201': ok(O({
                'message': S(),
                'order_id': I(),
                'subtotal': S('Item prices (excluding delivery).'),
                'delivery_charge': S('Sum of the per-item delivery fees.'),
                'total_price': S('subtotal + delivery_charge.'),
                'delivery_otp': S('4 digits, shown to the buyer only.'),
            }), 'Order placed'),
            '400': ok(R('Error'), 'Empty cart, bad pincode, unserviceable '
                                   'pincode or stale item'),
        },
    },
    ('GET', '/api/products/admin/moderation/'): {
        'summary': 'Admin moderation queue',
        'parameters': [
            q('status', S(enum=['pending', 'approved', 'rejected']),
              'Which approval bucket to list (default: all).'),
            *PAGE_PARAMS,
        ],
        'responses': {
            '200': ok(page(R('ModerationRow'), {
                'pending_count': I(),
                'approved_count': I(),
                'rejected_count': I(),
            })),
        },
    },
    ('POST', '/api/products/admin/moderation/{item_id}/review/'): {
        'summary': 'Approve or reject a listing',
        'description': 'A rejection reason is mandatory and is shown to the '
                       'seller. Rejected items are dropped from carts. The '
                       'seller is notified either way.',
        'request': body(O({
            'decision': S(enum=['APPROVED', 'REJECTED']),
            'reason': S('Required when rejecting (<= 500 chars).'),
        }, required=['decision'])),
        'responses': {
            '200': ok(O({'message': S(),
                         'item': O({'id': I(),
                                    'approval_status': S()})})),
            '400': ok(R('Error'), 'Bad decision/reason or already decided'),
            '404': ok(R('Error')),
        },
    },

    # ----- Orders --------------------------------------------------------
    ('GET', '/api/orders/success/{order_id}/'): {
        'summary': 'Order confirmation payload',
        'description': 'Buyer-only confirmation page data: item subtotal, '
                       'delivery charge, total, address, OTP and each item '
                       'with its status and tracking id. Another user\'s order '
                       'returns 404.',
        'responses': {'200': ok(R('OrderConfirmation')),
                      '404': ok(R('Error'))},
    },
    ('GET', '/api/orders/track/{tracking_number}/'): {
        'summary': 'Track one order item by tracking id',
        'description': 'Buyer-only (the item must belong to the caller). '
                       'Includes route context so the UI can pick the right '
                       'ladder: is_intercity, both cities, hub names and the '
                       'line-haul ETA. Due hub arrivals are settled lazily on '
                       'this call.',
        'responses': {'200': ok(R('TrackingState')),
                      '404': ok(R('Error'), 'Unknown tracking id')},
    },
    ('POST', '/api/orders/items/{order_item_id}/cancel/'): {
        'summary': 'Cancel an order item before pickup',
        'description': 'Allowed only while ORDER_PLACED or PICKUP_SCHEDULED. '
                       'Restocks the listing, releases the pickup agent, '
                       'zeroes the item\'s money fields (no delivery charge, '
                       'commission, payout or agent pay), recalculates the '
                       'order totals and notifies the seller. After pickup use '
                       'the dispute or return flow instead. Throttled to '
                       '10/minute.',
        'request': body(O({
            'reason': S(enum=['CHANGED_MIND', 'WRONG_ADDRESS',
                              'FOUND_ELSEWHERE', 'OTHER']),
            'note': S('Optional free text (<= 500 chars).'),
        }, required=['reason'])),
        'responses': {
            '200': ok(O({'message': S(), 'item': O({
                'id': I(), 'status': S(), 'cancel_reason': S()})})),
            '400': ok(R('Error'), 'Too late, bad reason, already delivered'),
            '403': ok(R('Error'), 'Not the buyer'),
            '404': ok(R('Error')),
        },
    },
    ('POST', '/api/orders/items/{order_item_id}/dispute/'): {
        'summary': 'Open a dispute on a delivered item',
        'description': 'One dispute per order item. The admin queue picks it '
                       'up from /api/deliveries/admin/disputes/. Throttled to '
                       '10/minute.',
        'request': body(O({
            'reason': S(enum=['DAMAGED', 'NOT_AS_DESCRIBED',
                              'NOT_RECEIVED', 'OTHER']),
            'description': S('At least 10 characters (<= 1000).'),
        }, required=['reason', 'description'])),
        'responses': {
            '201': ok(O({'message': S(), 'dispute': O({
                'id': I(), 'status': S(), 'reason': S()})}), 'Filed'),
            '400': ok(R('Error'), 'Not delivered, duplicate, bad input'),
            '403': ok(R('Error'), 'Not the buyer'),
            '404': ok(R('Error')),
        },
    },
    ('POST', '/api/orders/items/{order_item_id}/return/'): {
        'summary': 'Request a return within 24 hours of delivery',
        'description': 'Buyer-only, one request per item, and only while the '
                       'return window is open (RETURN_WINDOW_HOURS, 24 h from '
                       'delivery). If an admin approves, the buyer is '
                       'refunded the item price plus that item\'s delivery '
                       'charge, the 5% commission is reversed (seller payout '
                       'becomes 0) and the listing is restocked. Agent pay is '
                       'not touched. Throttled to 10/minute.',
        'request': body(O({
            'reason': S(enum=['CHANGED_MIND', 'DAMAGED', 'NOT_AS_DESCRIBED',
                              'WRONG_ITEM', 'OTHER']),
            'note': S('Optional free text (<= 1000 chars).'),
        }, required=['reason'])),
        'responses': {
            '201': ok(O({'message': S(), 'return': O({
                'id': I(), 'status': S(), 'reason': S(),
                'refund_amount': S()})}), 'Return requested'),
            '400': ok(R('Error'), 'Not delivered, duplicate, window closed '
                                   'or invalid reason'),
            '403': ok(R('Error'), 'Not the buyer'),
            '404': ok(R('Error')),
        },
    },
    ('POST', '/api/orders/items/{order_item_id}/rate/'): {
        'summary': 'Rate the seller and/or the delivery agent',
        'description': 'Each sub-rating can be submitted once; at least one '
                       'stars field is required. agent_stars needs an agent '
                       'on the item. Throttled to 20/minute.',
        'request': body(O({
            'seller_stars': I('1-5.'),
            'seller_comment': S('<= 500 chars.'),
            'agent_stars': I('1-5.'),
            'agent_comment': S('<= 500 chars.'),
        })),
        'responses': {
            '201': ok(O({'message': S(), 'rating': O({
                'id': I(), 'seller_stars': NULL(I()),
                'seller_comment': NULL(S()), 'agent_stars': NULL(I()),
                'agent_comment': NULL(S())})}), 'Rated'),
            '400': ok(R('Error'), 'Duplicate sub-rating or invalid stars'),
            '403': ok(R('Error')),
            '404': ok(R('Error')),
        },
    },

    # ----- Fulfillment ---------------------------------------------------
    ('GET', '/api/deliveries/admin/deliveries/'): {
        'summary': 'Admin fulfillment board',
        'description': 'All order items, newest first, grouped by lifecycle: '
                       'active (everything not delivered/cancelled), '
                       'completed (delivered) or cancelled. `search` is '
                       'strictly a tracking-id match and composes with the '
                       'group before pagination. Due hub arrivals are settled '
                       'lazily on this call.',
        'parameters': [
            q('status_group', S(enum=['active', 'completed', 'cancelled']),
              'Lifecycle bucket (omit for all).'),
            q('search', S(), 'Partial tracking id, e.g. "TRK-13".'),
            *PAGE_PARAMS,
        ],
        'responses': {
            '200': ok(page(R('DeliveryRow'), {
                'active_count': I(),
                'completed_count': I(),
                'cancelled_count': I(),
            })),
        },
    },
    ('PATCH', '/api/deliveries/admin/deliveries/{id}/assign/'): {
        'summary': 'Override assignment and/or tracking number',
        'description': '`assigned_agent` is the pickup leg; '
                       '`delivery_agent` is the intercity delivery leg '
                       '(auto-assigned on hub arrival, overridable here). '
                       'Sending null clears the assignment.',
        'request': body(O({
            'assigned_agent': NULL(I('User id.')),
            'delivery_agent': NULL(I('User id.')),
            'tracking_number': NULL(S()),
        })),
        'responses': {'200': ok(R('Message')),
                      '400': ok(R('Error'), 'Agent not found'),
                      '404': ok(R('Error'))},
    },
    ('PATCH', '/api/deliveries/admin/deliveries/{id}/status/'): {
        'summary': 'Admin line-haul: depart or arrive the hub',
        'description': 'IN_TRANSIT requires DROPPED_AT_ORIGIN_HUB (or legacy '
                       'DISPATCHED) and stamps linehaul_eta_at from the '
                       'HubRoute duration. AT_DESTINATION_HUB is the early '
                       'arrival override and auto-assigns the delivery agent '
                       'in the buyer city/zone inside the same transaction. '
                       'Without an override a due ETA settles itself on the '
                       'next list/tracking read.',
        'request': body(O({
            'status': S(enum=['IN_TRANSIT', 'AT_DESTINATION_HUB']),
        }, required=['status'])),
        'responses': {
            '200': ok(O({
                'message': S(), 'id': I(), 'status': S(),
                'delivery_agent': NULL(I()),
                'transit_hours': I(),
                'linehaul_eta_at': NULL(S(fmt='date-time')),
            })),
            '400': ok(R('Error'), 'Out of sequence / not intercity'),
            '404': ok(R('Error')),
        },
    },
    ('GET', '/api/deliveries/admin/disputes/'): {
        'summary': 'Admin dispute queue',
        'parameters': [
            q('status', S(enum=['open', 'resolved', 'rejected']),
              'Queue bucket (omit for all).'),
            *PAGE_PARAMS,
        ],
        'responses': {
            '200': ok(page(R('DisputeRow'), {
                'open_count': I(),
                'resolved_count': I(),
                'rejected_count': I(),
            })),
        },
    },
    ('POST', '/api/deliveries/admin/disputes/{dispute_id}/resolve/'): {
        'summary': 'Resolve or reject a dispute',
        'description': 'The note is mandatory and is shown to both buyer and '
                       'seller.',
        'request': body(O({
            'status': S(enum=['RESOLVED', 'REJECTED']),
            'note': S('Resolution note (<= 1000 chars).'),
        }, required=['status', 'note'])),
        'responses': {
            '200': ok(O({'message': S(), 'dispute': O({
                'id': I(), 'status': S(), 'resolution_note': S()})})),
            '400': ok(R('Error'), 'Already closed or missing note'),
            '404': ok(R('Error')),
        },
    },
    ('GET', '/api/deliveries/admin/returns/'): {
        'summary': 'Admin return-request queue',
        'description': 'Buyer return requests, newest first, paginated like '
                       'the other admin lists. The requested queue is the one '
                       'needing a decision.',
        'parameters': [
            q('status', S(enum=['requested', 'approved', 'rejected']),
              'Queue bucket (omit for all).'),
            *PAGE_PARAMS,
        ],
        'responses': {
            '200': ok(page(R('ReturnRow'), {
                'requested_count': I(),
                'approved_count': I(),
                'rejected_count': I(),
            })),
        },
    },
    ('POST', '/api/deliveries/admin/returns/{return_id}/resolve/'): {
        'summary': 'Approve or reject a return',
        'description': 'The note is mandatory and is shown to both buyer and '
                       'seller. Approval refunds item price + delivery, '
                       'reverses the 5% commission (seller payout -> 0) and '
                       'restocks the listing; agent pay is untouched. Rejection '
                       'leaves the sale intact.',
        'request': body(O({
            'status': S(enum=['APPROVED', 'REJECTED']),
            'note': S('Decision note (<= 1000 chars).'),
        }, required=['status', 'note'])),
        'responses': {
            '200': ok(O({'message': S(), 'return': O({
                'id': I(), 'status': S(), 'refund_amount': S(),
                'admin_note': S()})})),
            '400': ok(R('Error'), 'Already decided or missing note'),
            '404': ok(R('Error')),
        },
    },
    ('PATCH', '/api/deliveries/admin/orders/{id}/update/'): {
        'summary': 'Correct an order\'s shipping details',
        'description': 'Any subset may be sent; empty strings are rejected. '
                       'The buyer is notified.',
        'request': body(O({
            'shipping_city': S('Must be a supported city.'),
            'shipping_address': S(),
            'phone': S(),
        })),
        'responses': {
            '200': ok(O({'message': S(), 'order_id': I(),
                         'shipping_city': S(), 'shipping_address': S(),
                         'phone': S()})),
            '400': ok(R('Error'), 'Invalid city or empty value'),
            '404': ok(R('Error')),
        },
    },
    ('GET', '/api/deliveries/admin/staff/'): {
        'summary': 'Staff and delivery-agent directory',
        'description': 'Union of is_staff users and delivery agents, with '
                       'profile city, zone, role flags and verification. '
                       'Paginated; ?all=1 returns a flat array.',
        'parameters': PAGE_PARAMS,
        'responses': {'200': ok(page(R('StaffRow')))},
    },
    ('POST', '/api/deliveries/admin/staff/'): {
        'summary': 'Create a staff or delivery-agent account',
        'description': 'role="agent" adds the DeliveryAgent group and flags '
                       'the profile; role="admin" sets is_staff. A zone, when '
                       'given, must belong to the supplied city.',
        'request': body(O({
            'username': S(),
            'password': S(),
            'email': S(),
            'address': S('City (stored on the profile).'),
            'role': S(enum=['agent', 'admin']),
            'zone': NULL(I()),
        }, required=['username', 'password'])),
        'responses': {
            '201': ok(R('Message')),
            '400': ok(R('Error'), 'Duplicate username / unknown zone'),
        },
    },
    ('PATCH', '/api/deliveries/admin/staff/{id}/update/'): {
        'summary': 'Update a staff member (role, city, zone, email)',
        'description': 'Any subset may be sent. Changing the role rewrites the '
                       'DeliveryAgent group and the profile flag; zone is '
                       'nullable and must belong to the resulting city.',
        'request': body(O({
            'email': S(),
            'address': S('City.'),
            'role': S(enum=['agent', 'admin'],
                      desc='Switching to admin clears the agent group; '
                           'switching to agent adds it.'),
            'zone': NULL(I('Must belong to the profile city.')),
        })),
        'responses': {
            '200': ok(R('Message')),
            '400': ok(R('Error')),
            '404': ok(R('Error')),
        },
    },
    ('PATCH', '/api/deliveries/admin/users/{user_id}/verify/'): {
        'summary': 'Toggle (or set) seller verification',
        'description': 'Omit is_verified to flip the current value.',
        'request': body(O({'is_verified': B()}), required=False),
        'responses': {
            '200': ok(O({'status': S(), 'is_verified': B()})),
            '404': ok(R('Error')),
        },
    },
    ('GET', '/api/deliveries/agent/deliveries/'): {
        'summary': 'Agent task list for both legs',
        'description': 'Items to pick up (assigned_agent) plus intercity '
                       'items awaiting delivery in the agent\'s city '
                       '(delivery_agent). my_role tells the two apart. Due '
                       'hub arrivals are settled lazily on this call.',
        'responses': {'200': ok(A(R('AgentTask')))},
    },
    ('PATCH', '/api/deliveries/agent/deliveries/{id}/update/'): {
        'summary': 'Advance an assigned item along the agent ladder',
        'description': 'Intra-city: PICKED_UP -> DISPATCHED -> DELIVERED. '
                       'Intercity pickup leg: PICKED_UP -> '
                       'DROPPED_AT_ORIGIN_HUB (DISPATCHED is rejected). The '
                       'delivery agent finishes with DELIVERED from '
                       'AT_DESTINATION_HUB. DELIVERED requires the buyer\'s '
                       '4-digit OTP. Throttled to 5 OTP attempts/minute.',
        'request': body(O({
            'status': S(enum=['PICKED_UP', 'DROPPED_AT_ORIGIN_HUB',
                              'DISPATCHED', 'DELIVERED']),
            'otp': S('Required for DELIVERED.'),
        }, required=['status'])),
        'responses': {
            '200': ok(O({'message': S(), 'id': I(), 'status': S(),
                         'hub': NULL(S('Origin hub name on '
                                       'DROPPED_AT_ORIGIN_HUB.'))})),
            '400': ok(R('Error'), 'Out of sequence, bad OTP or intercity '
                                   'DISPATCHED'),
            '404': ok(R('Error'), 'Not found or not assigned to caller'),
        },
    },
    ('GET', '/api/deliveries/agent/profile/'): {
        'summary': 'Agent profile header',
        'description': 'Header data for the agent portal. The profile city is '
                       'returned in the `address` field (\'N/A\' when unset).',
        'responses': {'200': ok(O({
            'id': I(), 'username': S(), 'email': S(), 'address': S()}))},
    },
    ('GET', '/api/deliveries/agent/earnings/'): {
        'summary': 'Agent earnings across both delivery legs',
        'description': 'A leg is earned when it completes: an intercity '
                       'pickup leg on DROPPED_AT_ORIGIN_HUB, an intra-city '
                       'item or the intercity delivery leg on DELIVERED. '
                       'pending_total is what the agent\'s open tasks will add. '
                       'Rates come from the checkout snapshot on each item.',
        'responses': {
            '200': ok(O({
                'earned_total': S(),
                'pending_total': S(),
                'completed_tasks': I(),
                'recent': A(O({
                    'id': I(),
                    'item_title': S(),
                    'tracking_number': S(),
                    'role': S(enum=['pickup', 'delivery']),
                    'amount': S(),
                    'status': S(),
                })),
            })),
        },
    },
    ('GET', '/api/deliveries/admin/analytics/'): {
        'summary': 'Platform analytics for the admin dashboard',
        'description': 'Returns summary counters, per-city order counts, the '
                       'status breakdown, agent utilization, top sellers (by '
                       'net payout) and a revenue trend. The summary includes '
                       'the marketplace money roll-up taken from the per-item '
                       'checkout snapshots: gross sales, platform commission, '
                       'delivery revenue, seller and agent payouts, platform '
                       'earnings, refunds and the pending-return count.',
        'responses': {
            '200': ok(O({
                'summary': O({
                    'total_orders': I(),
                    'completed_revenue': N(),
                    'delivered_items': I(),
                    'in_transit_items': I(),
                    'awaiting_assignment': I(),
                    'active_listings': I(),
                    'pending_listings': I(),
                    'registered_users': I(),
                    'total_agents': I(),
                    'gross_sales': N(),
                    'platform_commission': N(),
                    'delivery_revenue': N(),
                    'seller_payouts': N(),
                    'agent_payouts': N(),
                    'platform_earnings': N(),
                    'refunds': N(),
                    'pending_returns': I(),
                }),
                'orders_per_city': A(FREE),
                'status_breakdown': A(FREE),
                'agents': A(FREE),
                'top_sellers': A(FREE),
                'revenue_trend': A(FREE),
            })),
        },
    },

    # ----- Zones & hubs --------------------------------------------------
    ('GET', '/api/locations/zones/'): {
        'summary': 'Active zones, optionally for one city',
        'description': 'Public zone picker for a known city. Unknown city '
                       'names are rejected.',
        'parameters': [q('city', S(), 'Supported city name.')],
        'responses': {
            '200': ok(O({'results': A(R('Zone'))})),
            '400': ok(R('Error'), 'Unknown city'),
        },
    },
    ('GET', '/api/locations/zones/resolve/'): {
        'summary': 'Resolve a pincode to its city and zone',
        'description': 'The same lookup checkout uses; live badge in the '
                       'pincode field.',
        'parameters': [q('pincode', S(), '6 digits.', required=True)],
        'responses': {
            '200': ok(O({'zone_id': I(), 'zone_name': S(), 'city': S(),
                         'pincode': S()})),
            '400': ok(R('Error'), 'Malformed pincode'),
            '404': ok(R('Error'), 'Not serviceable yet'),
        },
    },
    ('GET', '/api/locations/admin/zones/'): {
        'summary': 'Admin zone list with per-zone agent counts',
        'parameters': [q('city', S(), 'Filter by city.'), *PAGE_PARAMS],
        'responses': {'200': ok(page(R('AdminZone')))},
    },
    ('POST', '/api/locations/admin/zones/'): {
        'summary': 'Create a zone',
        'description': 'Ranges must not overlap another active zone in the '
                       'same city; bounds are inclusive 6-digit pincodes.',
        'request': body(R('ZoneWrite')),
        'responses': {
            '201': ok(O({'message': S(), 'zone': O({
                'id': I(), 'city': S(), 'name': S()})})),
            '400': ok(R('Error'), 'Duplicate name or overlapping range'),
        },
    },
    ('PUT', '/api/locations/admin/zones/{id}/'): {
        'summary': 'Update a zone',
        'description': 'Same validation as create. Orders keep their zone '
                       'name snapshot, so renames are safe.',
        'request': body(R('ZoneWrite'), required=False),
        'responses': {
            '200': ok(O({'message': S(), 'zone': O({
                'id': I(), 'city': S(), 'name': S()})})),
            '400': ok(R('Error')),
            '404': ok(R('Error')),
        },
    },
    ('DELETE', '/api/locations/admin/zones/{id}/'): {
        'summary': 'Deactivate a zone',
        'description': 'Soft delete: FKs may still reference the zone, so '
                       'is_active is flipped instead of removing the row.',
        'responses': {'200': ok(R('Message')),
                      '404': ok(R('Error'))},
    },
    ('GET', '/api/locations/admin/hubs/'): {
        'summary': 'Delivery hubs (optionally one city)',
        'description': 'Small dataset, returned unpaginated.',
        'parameters': [q('city', S(), 'Filter by city.')],
        'responses': {'200': ok(O({'results': A(R('Hub'))}))},
    },
    ('POST', '/api/locations/admin/hubs/'): {
        'summary': 'Create a delivery hub',
        'description': 'One name per city; an optional zone must belong to '
                       'that city.',
        'request': body(R('HubWrite')),
        'responses': {
            '201': ok(O({'message': S(), 'hub': O({
                'id': I(), 'city': S(), 'name': S()})})),
            '400': ok(R('Error')),
        },
    },
    ('PUT', '/api/locations/admin/hubs/{id}/'): {
        'summary': 'Update a delivery hub',
        'description': 'Same validation as create: one name per city, and an '
                       'optional zone must belong to that city.',
        'request': body(R('HubWrite'), required=False),
        'responses': {
            '200': ok(O({'message': S(), 'hub': O({
                'id': I(), 'city': S(), 'name': S()})})),
            '400': ok(R('Error')),
            '404': ok(R('Error')),
        },
    },
    ('DELETE', '/api/locations/admin/hubs/{id}/'): {
        'summary': 'Deactivate a delivery hub',
        'description': 'Soft delete: is_active is flipped so hub routes and '
                       'historical orders keep their hub reference.',
        'responses': {'200': ok(R('Message')),
                      '404': ok(R('Error'))},
    },

    # ----- Notifications -------------------------------------------------
    ('GET', '/api/notifications/'): {
        'summary': 'Latest 20 notifications plus the unread count',
        'description': 'Newest-first inbox for the caller, capped at 20 rows; '
                       'unread_count covers the full inbox and drives the bell '
                       'badge.',
        'responses': {
            '200': ok(O({
                'unread_count': I(),
                'notifications': A(R('Notification')),
            })),
        },
    },
    ('POST', '/api/notifications/{id}/read/'): {
        'summary': 'Mark one notification as read',
        'description': 'Only notifications addressed to the caller are '
                       'reachable; any other id returns 404.',
        'responses': {'200': ok(R('Message')),
                      '404': ok(R('Error'))},
    },
    ('POST', '/api/notifications/read-all/'): {
        'summary': 'Mark every notification as read',
        'description': 'Bulk update of the caller\'s unread notifications; '
                       'the message reports how many rows changed.',
        'responses': {'200': ok(R('Message'))},
    },
}


# ---------------------------------------------------------------------------
# Operation ids
# ---------------------------------------------------------------------------
# These are function-based views, so drf-spectacular gets no list/retrieve
# hint and every GET defaults to "..._retrieve". `/items/` and `/items/{id}/`
# then collide and the second one is renamed with a numeral suffix. Naming the
# collection explicitly keeps ids stable for generated clients and removes the
# only schema-generation warning. Keyed by (METHOD, canonical path).
OPERATION_IDS = {
    ('GET', '/api/products/items/'): 'products_items_list',
}


class VendorPulseAutoSchema(AutoSchema):
    """AutoSchema that applies OPERATION_IDS ahead of collision handling."""

    def get_operation_id(self):
        path = '/' + self.path.strip('/') + '/'
        override = OPERATION_IDS.get((self.method.upper(), path))
        if override:
            return override
        return super().get_operation_id()


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------

HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete'}

TAG_BY_SEGMENT = {
    'accounts': 'Accounts',
    'products': 'Listings & Cart',
    'orders': 'Orders',
    'deliveries': 'Fulfillment',
    'locations': 'Zones & Hubs',
    'notifications': 'Notifications',
}

GENERIC_JSON = O({}, freeform=True)


def _tag_for(path):
    segments = [p for p in path.split('/') if p and p != 'api']
    return TAG_BY_SEGMENT.get(segments[0] if segments else '') if segments else None


def _dedupe_security(operation):
    """Session auth appears twice (auto-detected + token fallback); keep one
    entry per requirement object, preserving the anonymous {} marker."""
    security = operation.get('security')
    if security:
        unique = []
        for requirement in security:
            if requirement not in unique:
                unique.append(requirement)
        operation['security'] = unique


def _ensure_response_body(operation):
    """drf-spectacular writes 'No response body' for our hand-built
    Responses. They all return JSON, so advertise an untyped object instead
    of claiming there is no body (204 is genuinely empty)."""
    for code, response in operation.get('responses', {}).items():
        if code == '204':
            continue
        if response.get('description') == 'No response body' and 'content' not in response:
            response['description'] = 'JSON object'
            response['content'] = {'application/json': {'schema': GENERIC_JSON}}


def apply_endpoint_docs(result, generator, request, public):
    """POSTPROCESSING_HOOK: enrich the generated document from DOCS."""
    schemas = result.setdefault('components', {}).setdefault('schemas', {})
    schemas.update(COMPONENTS)

    matched = set()
    for path, operations in result.get('paths', {}).items():
        tag = _tag_for(path)
        for method, operation in operations.items():
            if method.lower() not in HTTP_METHODS:
                continue
            if tag:
                operation['tags'] = [tag]
            _dedupe_security(operation)
            _ensure_response_body(operation)

            spec = DOCS.get((method.upper(), path))
            if not spec:
                continue
            matched.add((method.upper(), path))

            if spec.get('summary'):
                operation['summary'] = spec['summary']
            if spec.get('description'):
                operation['description'] = spec['description']

            if spec.get('parameters'):
                existing = {
                    (p.get('in'), p.get('name'))
                    for p in operation.get('parameters', [])
                }
                for parameter in spec['parameters']:
                    if (parameter['in'], parameter['name']) not in existing:
                        operation.setdefault('parameters', []).append(parameter)

            if spec.get('request'):
                operation['requestBody'] = {
                    'required': spec['request'].get('required', True),
                    'content': {'application/json': {
                        'schema': spec['request']['schema'],
                    }},
                }

            if spec.get('responses'):
                operation['responses'] = spec['responses']

    for key in DOCS:
        if key not in matched:
            warn(f'api_docs: DOCS entry {key[0]} {key[1]} matched no generated '
                 f'operation (path renamed or endpoint removed?).')

    return result
