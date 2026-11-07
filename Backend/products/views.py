from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q

from .models import Item, Cart, CartItem
from orders.models import Order, OrderItem
from .serializers import ItemSerializer, CartSerializer, CartItemSerializer


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def item_list_create_api(request):
    """
    GET: Retrieve available products, with optional category filtering (?category=ELECTRONICS).
    POST: Create a new product listing (requires authentication).
    """
    if request.method == 'GET':
        category = request.GET.get('category')
        condition = request.GET.get('condition')
        city = request.GET.get('city')
        search_query = request.GET.get('search')

        items = Item.objects.filter(status='AVAILABLE').order_by('-created_at')

        if category:
            items = items.filter(category=category)
        if condition:
            items = items.filter(condition=condition)
        if city:
            items = items.filter(city__icontains=city)
        if search_query:
            items = items.filter(
                Q(title__icontains=search_query) | Q(description__icontains=search_query)
            )

        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            # Automatically assign current user as seller and set status to AVAILABLE
            serializer.save(seller=request.user, status='AVAILABLE')
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([AllowAny])
def item_detail_api(request, pk):
    item = get_object_or_404(Item, pk=pk)

    if request.method == 'GET':
        serializer = ItemSerializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)

    if item.seller != request.user:
        return Response({"detail": "You do not have permission to modify this listing."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'PUT':
        serializer = ItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        item.delete()
        return Response({"detail": "Listing deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart_detail_api(request):
    """Retrieve the authenticated user's cart and items."""
    user_cart, _ = Cart.objects.get_or_create(user=request.user)
    serializer = CartSerializer(user_cart)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart_api(request, item_id):
    item = get_object_or_404(Item, id=item_id, status='AVAILABLE')
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, item=item)

    if not created:
        return Response({"detail": "Item is already in your cart."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = CartItemSerializer(cart_item)
    return Response({"detail": "Item added successfully.", "cart_item": serializer.data}, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_cart_api(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    cart_item.delete()
    return Response({"detail": "Item removed from cart."}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def checkout_api(request):
    cart_items = CartItem.objects.filter(cart__user=request.user).select_related('item', 'item__seller')

    if not cart_items.exists():
        return Response({"detail": "Your cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    address = request.data.get('address')
    phone = request.data.get('phone')

    if not address or not phone:
        return Response({"detail": "Shipping address and phone number are required."}, status=status.HTTP_400_BAD_REQUEST)

    total_price = sum(item.item.price for item in cart_items)

    # 1. Create Order
    order = Order.objects.create(
        user=request.user,
        total_price=total_price,
        shipping_address=address,
        phone=phone
    )

    # 2. Create OrderItems & mark products as RESERVED
    for cart_item in cart_items:
        OrderItem.objects.create(
            order=order,
            item=cart_item.item,
            seller=cart_item.item.seller,
            item_title=cart_item.item.title,
            item_price=cart_item.item.price,
            status='ORDER_PLACED'
        )
        cart_item.item.status = 'RESERVED'
        cart_item.item.save()

    # 3. Clear Cart
    cart_items.delete()

    return Response({
        "detail": "Order placed successfully!",
        "order_id": order.id,
        "total_price": float(total_price)
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_listings_api(request):
    items = Item.objects.filter(seller=request.user).order_by('-created_at')
    serializer = ItemSerializer(items, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)