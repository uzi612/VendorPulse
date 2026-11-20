from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, Http404, JsonResponse
from django.urls import include, path, re_path
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)

def health(request):
    return JsonResponse({"status": "ok"})


def spa_index(request):
    """Serve the built SPA shell for client-side routes on a single-process
    host (Render/Gunicorn). Nginx does this on the VPS track."""
    index = settings.STATIC_ROOT / 'index.html'
    if not index.is_file():
        raise Http404('SPA build not found; run collectstatic.')
    response = FileResponse(open(index, 'rb'), content_type='text/html')
    # The shell references hashed assets, so it must never be cached across a
    # deploy; the assets themselves are immutable and served by WhiteNoise.
    response['Cache-Control'] = 'no-cache'
    return response


APP_URL_INCLUDES = [
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('orders/', include('orders.urls')),
    path('deliveries/', include('deliveries.urls')),
    path('notifications/', include('notifications.urls')),
]

urlpatterns = [
    path('health/', health),
    # The React portal owns /admin/* (/admin/login/, /admin/returns/, ...),
    # so Django's own admin lives here instead.
    path('django-admin/', admin.site.urls),
    # API documentation (see SPECTACULAR_SETTINGS in settings.py).
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='api-schema'),name='api-docs'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='api-schema'),name='api-redoc'),
    # Canonical API surface.
    path('api/', include(APP_URL_INCLUDES)),
    path('api/locations/', include('locations.urls')),
]

# Historical bare mounts. They collide with SPA routes (/accounts/login/,
# /accounts/profile/, /orders/success/<id>/) on a host without Nginx, so they
# are development-only unless SERVE_BARE_API is explicitly enabled.
if settings.SERVE_BARE_API:
    urlpatterns += [
        *APP_URL_INCLUDES,
        path('locations/', include('locations.urls')),
    ]

# SPA fallback: everything that is not API, admin, static, media or health is a
# client-side route. Must stay last.
if not settings.DEBUG:
    urlpatterns += [
        re_path(
            r'^(?!api/|django-admin/|static/|media/|health/).*$',
            spa_index,
            name='spa-index',
        ),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
