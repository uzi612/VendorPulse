from rest_framework import serializers
from django.db.models import Avg, Count
from .models import Item, Cart, CartItem

class ItemSerializer(serializers.ModelSerializer):
    seller_username = serializers.ReadOnlyField(source='seller.username')
    is_seller_verified = serializers.BooleanField(source='seller.profile.is_verified', read_only=True)
    # Seller's average rating / rating count — populated via annotate() on the
    # queryset (Avg('seller__seller_ratings_received__seller_stars')). Uses
    # getattr so un-annotated callers get None instead of an AttributeError.
    seller_rating = serializers.SerializerMethodField()
    seller_rating_count = serializers.SerializerMethodField()

    def get_seller_rating(self, obj):
        value = getattr(obj, 'seller_rating_avg', None)
        return round(value, 1) if value is not None else None

    def get_seller_rating_count(self, obj):
        return getattr(obj, 'seller_rating_count', None)

    class Meta:
        model = Item
        fields = [
            'id', 'seller', 'seller_username', 'is_seller_verified', 'seller_rating', 'seller_rating_count', 'category',
            'title', 'description', 'price', 'condition', 'status', 'approval_status', 'rejection_reason', 'image',
            'location', 'address', 'created_at', 'updated_at'
        ]
        read_only_fields = ['seller', 'approval_status', 'rejection_reason', 'created_at', 'updated_at']

# Shared annotation for any Item queryset that serializes with ItemSerializer:
# one LEFT JOIN aggregation, zero per-row queries.
SELLER_RATING_ANNOTATIONS = {
    'seller_rating_avg': Avg('seller__seller_ratings_received__seller_stars'),
    'seller_rating_count': Count('seller__seller_ratings_received__seller_stars'),
}

class CartItemSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'item', 'added_at']
        read_only_fields = ['cart', 'added_at']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'created_at']
        read_only_fields = ['user', 'created_at']