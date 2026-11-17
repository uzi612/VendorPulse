from django.urls import path

from . import views

urlpatterns = [
    path('zones/resolve/', views.resolve_zone_api, name='api_zone_resolve'),
    path('zones/', views.list_zones_api, name='api_zone_list'),
    path('admin/zones/', views.admin_zones_api, name='api_admin_zones'),
    path('admin/zones/<int:pk>/', views.admin_zone_detail_api, name='api_admin_zone_detail'),
    path('admin/hubs/', views.admin_hubs_api, name='api_admin_hubs'),
    path('admin/hubs/<int:pk>/', views.admin_hub_detail_api, name='api_admin_hub_detail'),
]
