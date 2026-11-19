"""
URLConf used ONLY to generate the OpenAPI schema.

The project mounts every domain twice (bare `/accounts/...` and
`/api/accounts/...`) so older frontend builds keep working. Documenting both
would double the 43 endpoints and confuse API consumers, so the schema is
generated against this canonical surface instead:

    manage.py spectacular --urlconf vendorpulse_core.schema_urls --validate

`SPECTACULAR_SETTINGS['SERVE_URLCONF']` points here as well, so the live
`/api/schema/` view stays in sync.

Keep this list in step with vendorpulse_core.urls.APP_URL_INCLUDES: it is
reused directly for the five core apps, with locations added separately
because urls.py mounts it at its own prefixes.
"""
from django.urls import include, path

from vendorpulse_core.urls import APP_URL_INCLUDES
from locations import urls as locations_urls

urlpatterns = [
    path('api/', include(APP_URL_INCLUDES)),
    path('api/locations/', include(locations_urls)),
]
