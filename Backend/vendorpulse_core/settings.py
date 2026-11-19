import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback-insecure-key')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'vendorpulse_db'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''), 
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

ALLOWED_HOSTS = []


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

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]



# Session (cookie) auth requires CORS to allow credentials and the frontend
# origin to be trusted for CSRF origin checks.
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

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

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Session cookie behavior
SESSION_EXPIRE_AT_BROWSER_CLOSE = True   
SESSION_COOKIE_AGE = 60 * 60 * 8        