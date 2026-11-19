from django.urls import path
from .views import *

urlpatterns = [
    # Buyer order endpoints
    path('success/<int:order_id>/', order_success_api, name='order_success'),
    path('track/<str:tracking_number>/', track_order_item_api, name='track_order_item'),
    # Buyer rates the seller / delivery agent for one delivered item
    path('items/<int:order_item_id>/rate/', rate_order_item_api, name='rate_order_item'),
    # Buyer cancels before pickup / opens a dispute after delivery
    path('items/<int:order_item_id>/cancel/', cancel_order_item_api, name='cancel_order_item'),
    path('items/<int:order_item_id>/dispute/', open_dispute_api, name='open_dispute'),
    # Buyer requests a return within 24 h of delivery
    path('items/<int:order_item_id>/return/', request_return_api, name='request_return'),
]