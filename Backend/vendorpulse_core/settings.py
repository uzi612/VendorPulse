import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_list(name, default=''):
    """Read a comma-separated env var into a clean list."""
    return [v.strip() for v in os.environ.get(name, default).split(',') if v.strip()]


# Fail closed: an accidental production run without .env must not expose
# Django debug pages. Local dev sets DEBUG=True in Backend/.env.
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-key'
    else:
        raise ImproperlyConfigured(
            'SECRET_KEY is required when DEBUG=False. Set it in Backend/.env.'
        )

# Managed MySQL providers (TiDB Cloud, PlanetScale, Aiven, ...) require TLS.
#   DB_SSL_MODE=REQUIRED        encrypt without verifying the certificate
#   DB_SSL_MODE=VERIFY_IDENTITY + DB_SSL_CA=/path/to/ca.pem   verify the chain
_db_options = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
}
if os.environ.get('DB_SSL_MODE'):
    _db_options['ssl_mode'] = os.environ['DB_SSL_MODE']
if os.environ.get('DB_SSL_CA'):
    _db_options['ssl'] = {'ca': os.environ['DB_SSL_CA']}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'vendorpulse_db'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''), 
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': _db_options,
    }
}

# Comma-separated in .env, e.g. "vendorpulse.example.com,www.vendorpulse.example.com"
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'products',
    'orders',
    'deliveries',
    'notifications',
    'locations',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'corsheaders',
]

REST_FRAMEWORK = {
    # drf-spectacular introspects the views to build /api/schema/; no view
    # carries schema decorators. The subclass only pins a couple of
    # operationIds (see api_docs.OPERATION_IDS).
    'DEFAULT_SCHEMA_CLASS': 'vendorpulse_core.api_docs.VendorPulseAutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',  # kept temporarily during the localStorage -> session migration
    ],
    # Throttling: a global per-identity baseline (IP for anonymous, user id
    # for logged-in) plus stricter named rates for sensitive endpoints.
    # Sensitive views opt in via @throttle_classes with the custom classes
    # in vendorpulse_core.throttles. Exceeding a limit returns 429.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/min',            # anonymous browsing baseline
        'user': '120/min',           # logged-in baseline (bell polls 3/min)
        'login': '5/min',            # login + portal-login brute-force guard
        'register': '10/hour',       # account-creation spam guard
        'otp_verify': '5/min',       # DELIVERED attempts (OTP guessing guard)
        'checkout': '10/min',
        'rating': '20/min',
        'cancel': '10/min',
        'dispute': '10/min',
        'listing_create': '2/hour', 
    },
}

# ---------------------------------------------------------------------------
# Marketplace money model (see vendorpulse_core/pricing.py)
# ---------------------------------------------------------------------------
# Amounts are in INR and snapshot onto each order item at checkout, so tuning
# these only affects orders placed afterwards.
DELIVERY_FEE_INTRA = '39.00'        # buyer pays, same-city delivery
DELIVERY_FEE_INTERCITY = '89.00'    # buyer pays, cross-city hub delivery
AGENT_PAY_INTRA = '25.00'           # one agent handles pickup + delivery
AGENT_PAY_PICKUP = '20.00'          # intercity leg 1: seller -> origin hub
AGENT_PAY_DELIVERY = '30.00'        # intercity leg 2: destination hub -> buyer
PLATFORM_COMMISSION_PERCENT = '5.00'  # deducted from the seller's payout

# Buyers may request a return for this many hours after delivery.
RETURN_WINDOW_HOURS = 24

# OpenAPI 3.1 document for the whole API surface.
#   /api/schema/  raw YAML (or ?format=json)
#   /api/docs/    Swagger UI
#   /api/redoc/   ReDoc
# Regenerate/inspect from the CLI: manage.py spectacular --validate
SPECTACULAR_SETTINGS = {
    'TITLE': 'VendorPulse API',
    'DESCRIPTION': (
        'VendorPulse is a C2C marketplace with courier fulfillment. Buyers '
        'browse approved listings, check out with a pincode (the pincode '
        'resolves both the delivery zone and the city), and follow each order '
        'item through the fulfillment ladder.\n\n'
        'Fulfillment ladders:\n'
        '  intra-city: PICKUP_SCHEDULED -> PICKED_UP -> DISPATCHED -> DELIVERED\n'
        '  intercity : PICKUP_SCHEDULED -> PICKED_UP -> DROPPED_AT_ORIGIN_HUB\n'
        '              -> IN_TRANSIT (admin line-haul) -> AT_DESTINATION_HUB\n'
        '              -> DELIVERED (delivery agent in the buyer city)\n\n'
        'Authentication is session-cookie based: call POST /api/accounts/me/ '
        'first to obtain the csrftoken cookie, log in through '
        'POST /api/accounts/portal-login/ (or /api/accounts/login/), then send '
        'both cookies with every request. A legacy DRF token header is still '
        'accepted while the frontend finishes migrating.\n\n'
        'Every domain is also mounted without the /api prefix for backwards '
        'compatibility; this document lists the canonical /api paths only.'
    ),
    'VERSION': '1.0.0',
    # Serve the schema view + its security scheme in the UI itself.
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    # Only the /api-mounted routes belong in the public contract.
    'SERVE_URLCONF': 'vendorpulse_core.schema_urls',
    # Schema-only annotations (no view decorators) live in api_docs.py.
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
        'vendorpulse_core.api_docs.apply_endpoint_docs',
    ],
    'TAGS': [
        {'name': 'Accounts',
         'description': 'Session bootstrap, registration, login and the buyer/seller profile.'},
        {'name': 'Listings & Cart',
         'description': 'Marketplace feed, seller listings, cart and pincode-first checkout.'},
        {'name': 'Orders',
         'description': 'Buyer order confirmation, tracking, ratings, cancellations and disputes.'},
        {'name': 'Fulfillment',
         'description': 'Agent pickup/delivery ladder, admin line-haul, staff and agent administration.'},
        {'name': 'Zones & Hubs',
         'description': 'Pincode-to-zone resolution, zone administration and delivery hubs.'},
        {'name': 'Notifications',
         'description': 'In-app notification inbox for every role.'},
    ],
}

# drf-spectacular's system checks introspect the FULL URLconf, which mounts
# every domain twice (bare + /api) for backwards compatibility. That produces
# expected operationId collisions (W001) and "unable to guess serializer"
# notices (W002) for function-based views. The published contract is generated
# from vendorpulse_core.schema_urls and validated separately (0 warnings,
# 57 unique operationIds), so only these two known IDs are silenced.
SILENCED_SYSTEM_CHECKS = ['drf_spectacular.W001', 'drf_spectacular.W002']

# Throttle counters (and other cache users) live here. LocMemCache is
# per-process — fine for the dev server. For production with multiple
# workers, switch to Redis so limits are shared across processes:
#   'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#   'LOCATION': 'redis://127.0.0.1:6379/1',
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'vendorpulse-default',
    }
}

# With more than one Gunicorn worker, DRF throttle counters must be shared or
# each worker gets its own allowance. Set REDIS_URL in production.
REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Serves /static/ directly from Gunicorn (collectstatic output). On the VPS
    # Nginx handles this first; on Render/containers there is no proxy.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]



# Session (cookie) auth requires CORS to allow credentials and the frontend
# origin to be trusted for CSRF origin checks. Production is same-origin (the
# SPA and API share one domain), so CORS stays empty there; dev needs the Vite
# origins because the proxy forwards their Origin header to Django.
CORS_ALLOW_CREDENTIALS = True
_dev_origins = ('http://localhost:5173,http://127.0.0.1:5173' if DEBUG else '')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', _dev_origins)
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')

# Render sets this for every web service, so a free *.onrender.com deployment
# needs no host configuration in the dashboard.
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if _render_host:
    if _render_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_render_host)
    _render_origin = f'https://{_render_host}'
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)

# The URLconf mounts every domain twice (bare + /api) for backwards
# compatibility. A single-process host (Gunicorn, no Nginx) cannot tell a bare
# API path from an SPA route, and they collide on /accounts/login/,
# /accounts/profile/ and /orders/success/<id>/. The SPA calls /api/... only, so
# bare mounts stay on for local development and are off in production.
SERVE_BARE_API = os.environ.get(
    'SERVE_BARE_API', 'True' if DEBUG else 'False'
) == 'True'

# The Dockerfile copies frontend/dist here (Vite base=/static/ in production),
# so the SPA's own JS/CSS are collected and served like any other static file.
SPA_DIR = BASE_DIR / 'spa'

ROOT_URLCONF = 'vendorpulse_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'vendorpulse_core.wsgi.application'




# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
# The leading slash matters: a relative "static/" breaks admin assets under
# /django-admin/ (they would resolve to /django-admin/static/...).

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Vite builds with base=/static/ (see frontend/vite.config.js), so dist/ can be
# collected as ordinary static files. WhiteNoise then serves them from
# Gunicorn, which is what replaces Nginx on Render.
STATICFILES_DIRS = []
if SPA_DIR.is_dir():
    STATICFILES_DIRS.append(SPA_DIR)

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    # Manifest hashing is deliberately avoided: the SPA's index.html is copied
    # verbatim and must not be rewritten by collectstatic.
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
# Persist uploads outside the release directory in production:
#   MEDIA_ROOT=/var/www/vendorpulse/shared/media
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))

# Cloudflare R2 (S3-compatible) for user uploads. Render's filesystem is
# ephemeral, so a disk-less deployment needs object storage. Without R2_* set,
# uploads stay on the local disk (development and the VPS track).
R2_BUCKET = os.environ.get('R2_BUCKET')
if R2_BUCKET:
    _r2_public_host = os.environ.get('R2_PUBLIC_HOST', '').strip().strip('/')
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': R2_BUCKET,
            'endpoint_url': os.environ['R2_ENDPOINT_URL'],
            'access_key': os.environ['R2_ACCESS_KEY_ID'],
            'secret_key': os.environ['R2_SECRET_ACCESS_KEY'],
            'region_name': os.environ.get('R2_REGION', 'auto'),
            # Public bucket: no per-request signatures, long-lived URLs.
            'default_acl': None,
            'querystring_auth': False,
            'file_overwrite': False,
            'object_parameters': {'CacheControl': 'public, max-age=604800'},
        },
    }
    if _r2_public_host:
        # r2.dev hostname or a custom domain on the bucket.
        STORAGES['default']['OPTIONS']['custom_domain'] = _r2_public_host
        MEDIA_URL = f'https://{_r2_public_host}/'

# Session cookie behavior
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60 * 60 * 8


# ---------------------------------------------------------------------------
# Production hardening (active only when DEBUG=False)
# ---------------------------------------------------------------------------
if not DEBUG:
    # Nginx terminates TLS and forwards X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    # Keep the plain-HTTP health probe usable for the load balancer / uptime
    # monitor. Paths are matched without the leading slash.
    SECURE_REDIRECT_EXEMPT = [r'^health/$']

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 31536000          # 1 year; only after HTTPS works
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY' 