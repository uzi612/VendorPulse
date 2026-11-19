from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)

def health(request):
    return JsonResponse({"status": "ok"})


APP_URL_INCLUDES = [
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('orders/', include('orders.urls')),
    path('deliveries/', include('deliveries.urls')),
    path('notifications/', include('notifications.urls')),
]

urlpatterns = [
    path('health/', health),
    path('admin/', admin.site.urls),
    # API documentation (see SPECTACULAR_SETTINGS in settings.py).
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='api-schema'),name='api-docs'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='api-schema'),name='api-redoc'),
    *APP_URL_INCLUDES,
    path('api/', include(APP_URL_INCLUDES)),
    path('locations/', include('locations.urls')),
    path('api/locations/', include('locations.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)