from rest_framework import serializers
from .models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    seller_username = serializers.ReadOnlyField(source='seller.username')

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'item', 'seller', 'seller_username', 'item_title', 'item_price', 'status']
        read_only_fields = ['order', 'seller', 'item_title', 'item_price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Order
        fields = ['id', 'user', 'user_username', 'total_price', 'created_at', 'shipping_address', 'phone', 'estimated_delivery', 'items']
        read_only_fields = ['user', 'total_price', 'created_at']