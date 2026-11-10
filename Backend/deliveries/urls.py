from django.urls import path
from . import views

urlpatterns = [
    path('admin/deliveries/', views.admin_delivery_list, name='admin-delivery-list'),
    path('admin/deliveries/<int:pk>/assign/', views.admin_assign_delivery, name='admin-assign-delivery'),
    path('admin/staff/', views.admin_staff_management, name='admin-staff-management'),
    path('agent/deliveries/', views.agent_delivery_list, name='agent-delivery-list'),
    path('agent/deliveries/<int:pk>/update/', views.agent_update_status, name='agent-update-status'),
    path('agent/profile/', views.agent_profile_view, name='agent-profile'),
    path('admin/staff/<int:pk>/update/', views.admin_update_staff, name='admin-update-staff'),
]