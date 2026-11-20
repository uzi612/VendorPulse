from django.urls import path
from .views import *

urlpatterns = [
    path('items/', item_list_create_api, name='api_item_list_create'),
    path('items/<int:pk>/', item_detail_api, name='api_item_detail'),
    path('my-listings/', user_listings_api, name='api_user_listings'),
    path('cart/', cart_detail_api, name='api_cart_detail'),
    path('cart/add/<int:item_id>/', add_to_cart_api, name='api_add_to_cart'),
    path('cart/remove/<int:cart_item_id>/', remove_from_cart_api, name='api_remove_from_cart'),
    path('checkout/quote/', checkout_quote_api, name='api_checkout_quote'),
    path('checkout/', checkout_api, name='api_checkout'),
    path('seller-dashboard/', seller_dashboard_api, name='api_seller_dashboard'),
    path('admin/moderation/', admin_moderation_queue, name='api_admin_moderation'),
    path('admin/moderation/<int:item_id>/review/', admin_review_listing, name='api_admin_review_listing'),
]