from django.urls import path
from .views import *

urlpatterns = [
    # Buyer order endpoints
    path('', order_list_api, name='api_order_list'),
    path('<int:pk>/', order_detail_api, name='api_order_detail'),

    # Seller sales endpoints
    path('sales/', seller_sales_api, name='api_seller_sales'),
    path('sales/item/<int:pk>/status/', update_order_item_status_api, name='api_update_order_item_status'),
]