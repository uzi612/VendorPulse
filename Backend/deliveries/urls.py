from django.urls import path
from . import views

urlpatterns = [
    path('admin/deliveries/', views.admin_delivery_list, name='admin-delivery-list'),
    path('admin/deliveries/<int:pk>/assign/', views.admin_assign_delivery, name='admin-assign-delivery'),
    path('admin/deliveries/<int:pk>/status/', views.admin_fulfillment_status, name='admin-fulfillment-status'),
    path('admin/orders/<int:pk>/update/', views.admin_order_update, name='admin-order-update'),
    path('admin/staff/', views.admin_staff_management, name='admin-staff-management'),
    path('agent/deliveries/', views.agent_delivery_list, name='agent-delivery-list'),
    path('agent/deliveries/<int:pk>/update/', views.agent_update_status, name='agent-update-status'),
    path('agent/profile/', views.agent_profile_view, name='agent-profile'),
    path('agent/earnings/', views.agent_earnings, name='agent-earnings'),
    path('admin/staff/<int:pk>/update/', views.admin_update_staff, name='admin-update-staff'),
    path('admin/users/<int:user_id>/verify/', views.toggle_seller_verification, name='toggle_seller_verification'),
    path('admin/analytics/', views.admin_analytics, name='admin-analytics'),
    path('admin/disputes/', views.admin_dispute_list, name='admin-dispute-list'),
    path('admin/disputes/<int:dispute_id>/resolve/', views.admin_resolve_dispute, name='admin-resolve-dispute'),
    # Buyer return requests (24 h after delivery)
    path('admin/returns/', views.admin_return_list, name='admin-return-list'),
    path('admin/returns/<int:return_id>/resolve/', views.admin_resolve_return, name='admin-resolve-return'),
]