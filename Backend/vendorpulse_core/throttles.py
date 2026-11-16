"""
Custom DRF throttle classes shared across apps.

Plain scoped limits (login, register) use DRF's built-in throttles keyed by
IP (AnonRateThrottle). These subclasses add method awareness so a throttle
only counts the request that actually consumes the protected resource.

All rates come from settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].
Counters live in the default cache backend — see CACHES in settings.py.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginThrottle(AnonRateThrottle):
    """
    Brute-force guard for credential endpoints (login, portal-login).
    Auth requests are always unauthenticated at this point, so DRF's
    AnonRateThrottle keys attempts by source IP. Rate: settings ('login').
    """
    scope = 'login'


class RegisterThrottle(AnonRateThrottle):
    """
    Spam guard for account creation — keyed by source IP.
    Rate: settings ('register').
    """
    scope = 'register'


class OtpVerifyThrottle(UserRateThrottle):
    """
    Brute-force guard for the buyer's 4-digit delivery OTP.

    Only requests that submit status='DELIVERED' (the only path that checks
    the OTP) are counted, so an agent working through their queue —
    scheduling pickups, picking up, dispatching — is never throttled, but
    OTP guessing dies at the rate in settings ('otp_verify').

    Without this guard the OTP space (10,000 codes) could be exhausted by
    unlimited retry attempts.
    """
    scope = 'otp_verify'

    def allow_request(self, request, view):
        if request.data.get('status') != 'DELIVERED':
            return True  # not an OTP-bearing request — don't count it
        return super().allow_request(request, view)


class ListingCreateThrottle(UserRateThrottle):
    """
    Spam guard for new listings. The item list view is GET+POST, so this
    counts only POSTs (creating a listing); browsing (GET) is left to the
    global anon/user baseline. Rate: settings ('listing_create').
    """
    scope = 'listing_create'

    def allow_request(self, request, view):
        if request.method != 'POST':
            return True  # GETs (browsing/filtering) are not counted here
        return super().allow_request(request, view)


class CheckoutThrottle(UserRateThrottle):
    """
    Guards against runaway checkout calls (double-click loops, scripted
    abuse). Rate: settings ('checkout').
    """
    scope = 'checkout'


class RatingThrottle(UserRateThrottle):
    """
    Guards against rating spam. Rate: settings ('rating').
    """
    scope = 'rating'


class CancelThrottle(UserRateThrottle):
    """
    Guards against rapid-fire cancellations. Rate: settings ('cancel').
    """
    scope = 'cancel'


class DisputeThrottle(UserRateThrottle):
    """
    Guards against dispute spam. Rate: settings ('dispute').
    """
    scope = 'dispute'
