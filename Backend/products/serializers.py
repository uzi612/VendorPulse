from rest_framework import serializers
from .models import Item, Cart, CartItem

class ItemSerializer(serializers.ModelSerializer):
    seller_username = serializers.ReadOnlyField(source='seller.username')

    class Meta:
        model = Item
        fields = ['id', 'seller', 'seller_username', 'category', 'title', 'description', 'price', 
            'condition', 'status', 'image', 'location', 'created_at', 'updated_at'
        ]
        read_only_fields = ['seller', 'created_at', 'updated_at']

class CartItemSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)
    item_id = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.all(), source='item', write_only=True
    )

    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'item', 'item_id', 'added_at']
        read_only_fields = ['cart', 'added_at']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'created_at']
        read_only_fields = ['user', 'created_at']