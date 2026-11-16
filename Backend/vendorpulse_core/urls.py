from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

# Server-liveness probe. An external monitor pings this every ~30s; without
# this route Django logs a 404 for each ping. Kept at project level because it
# is infrastructure, not marketplace logic. No DB access, no auth.
def health(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path('health/', health),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('orders/', include('orders.urls')),
    path('deliveries/', include('deliveries.urls')),
    path('notifications/', include('notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)