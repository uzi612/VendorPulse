from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.db import models

from .models import Item, Cart, CartItem
from orders.models import Order, OrderItem
from .serializers import ItemSerializer, CartSerializer, CartItemSerializer


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def item_list_create_api(request):
    if request.method == 'GET':
        items = Item.objects.filter(status='AVAILABLE').order_by('-created_at')
        
        # Optional filters
        category = request.GET.get('category')
        condition = request.GET.get('condition')
        location_query = request.GET.get('city') or request.GET.get('location') 
        search_query = request.GET.get('search') or request.GET.get('q')

        if category:
            items = items.filter(category=category)
        if condition:
            items = items.filter(condition=condition)
        if location_query:
            items = items.filter(location__icontains=location_query) 
        if search_query:
            items = items.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))

        serializer = ItemSerializer(items, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = ItemSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
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
    user_cart, _ = Cart.objects.get_or_create(user=request.user)
    serializer = CartSerializer(user_cart)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart_api(request, item_id):
    try:
        item = Item.objects.get(pk=item_id)
    except Item.DoesNotExist:
        return Response({"error": "Item not found."}, status=status.HTTP_404_NOT_FOUND)

    if item.seller == request.user:
        return Response({"error": "You cannot add your own item to the cart."}, status=status.HTTP_400_BAD_REQUEST)

    if item.status != 'AVAILABLE':
        return Response({"error": "This item is no longer available."}, status=status.HTTP_400_BAD_REQUEST)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    
    cart_item, created = CartItem.objects.get_or_create(cart=cart, item=item)

    if not created:
        return Response({"message": "Item is already in your cart."}, status=status.HTTP_200_OK)

    return Response({"message": "Item added to cart successfully!"}, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_cart_api(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    cart_item.delete()
    return Response({"detail": "Item removed from cart."}, status=status.HTTP_204_NO_CONTENT)


from django.db import transaction

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def checkout_api(request):
    user = request.user
    
    # 1. Fetch user's cart
    try:
        cart = Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    cart_items = cart.items.all()
    if not cart_items.exists():
        return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Extract and validate shipping details from request payload
    shipping_address = request.data.get('address') or request.data.get('shipping_address', '')
    phone = request.data.get('phone', '')

    if not shipping_address.strip() or not phone.strip():
        return Response({"error": "Shipping address and phone number are required."}, status=status.HTTP_400_BAD_REQUEST)

    # 3. Calculate total price and validate item availability
    total_price = 0
    for cart_item in cart_items:
        item = cart_item.item
        if item.status != 'AVAILABLE':
            return Response({"error": f"Item '{item.title}' is no longer available."}, status=status.HTTP_400_BAD_REQUEST)
        total_price += item.price

    # 4. Create the Order record
    order = Order.objects.create(
        user=user,
        total_price=total_price,
        shipping_address=shipping_address,
        phone=phone
    )

    # 5. Create OrderItem snapshots and reserve marketplace items
    for cart_item in cart_items:
        item = cart_item.item
        
        OrderItem.objects.create(
            order=order,
            item=item,
            seller=item.seller,
            item_title=item.title,
            item_price=item.price,
            status='ORDER_PLACED'
        )

        # Mark item as reserved so other buyers can't purchase it
        item.status = 'RESERVED'
        item.save()

    # 6. Empty/clear the user's cart
    cart_items.delete()

    return Response({
        "message": "Checkout successful!",
        "order_id": order.id,
        "total_price": str(total_price)
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_listings_api(request):
    items = Item.objects.filter(seller=request.user).order_by('-created_at')
    serializer = ItemSerializer(items, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkout_api(request):
    cart_items = CartItem.objects.filter(cart__user=request.user)
    if not cart_items.exists():
        return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

    total_price = sum(item.item.price for item in cart_items)
    address = request.data.get('address')
    phone = request.data.get('phone')

    order = Order.objects.create(
        user=request.user,
        total_price=total_price,
        shipping_address=address,
        phone=phone
    )

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

    cart_items.delete()
    return Response({"message": "Order placed successfully", "order_id": order.id}, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail_api(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items_data = [{
        "item_title": oi.item_title,
        "item_price": oi.item_price,
        "status": oi.status
    } for oi in order.items.all()]

    return Response({
        "id": order.id,
        "total_price": order.total_price,
        "shipping_address": order.shipping_address,
        "phone": order.phone,
        "created_at": order.created_at,
        "items": items_data
    })

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def item_edit_delete_api(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if item.seller != request.user:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
    if request.method == 'GET':
        return Response({
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "price": item.price,
            "location": item.location,
            "category": item.category,
            "condition": item.condition
        })
        
    elif request.method == 'PUT':
        item.title = request.data.get('title', item.title)
        item.description = request.data.get('description', item.description)
        item.price = request.data.get('price', item.price)
        item.location = request.data.get('location', item.location)
        item.save()
        return Response({"message": "Item updated successfully"})
        
    elif request.method == 'DELETE':
        item.delete()
        return Response({"message": "Item deleted successfully"})

from django.db.models import Sum

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seller_dashboard_api(request):
    user = request.user
    
    # Fetch all items listed by this seller
    seller_items = Item.objects.filter(seller=user)
    
    # Active item count
    active_listings_count = seller_items.filter(status='AVAILABLE').count()
    
    # Fetch all order items where this user is the seller
    sold_order_items = OrderItem.objects.filter(seller=user)
    
    # Use the count of sold order items so it accurately matches the sales table count
    sold_items_count = sold_order_items.count()
    
    # Calculate Total Revenue (Completed & Reserved Orders)
    total_revenue_dict = sold_order_items.filter(
        status__in=['ORDER_PLACED', 'PICKED_UP', 'DISPATCHED', 'DELIVERED']
    ).aggregate(total=Sum('item_price'))
    
    total_revenue = total_revenue_dict['total'] or 0.00
    
    # Calculate Pending Payouts vs Completed Payouts
    pending_payouts_dict = sold_order_items.exclude(
        status='DELIVERED'
    ).aggregate(total=Sum('item_price'))
    
    completed_payouts_dict = sold_order_items.filter(
        status='DELIVERED'
    ).aggregate(total=Sum('item_price'))

    pending_payouts = pending_payouts_dict['total'] or 0.00
    completed_payouts = completed_payouts_dict['total'] or 0.00

    # Recent Sales Table (latest 10)
    recent_sales = [{
        "order_id": sale.order.id,
        "item_title": sale.item_title,
        "item_price": sale.item_price,
        "status": sale.status,
        "buyer": sale.order.user.username,
        "shipping_address": sale.order.shipping_address
    } for sale in sold_order_items.select_related('order', 'item').order_by('-id')[:10]]

    return Response({
        "total_revenue": total_revenue,
        "completed_payouts": completed_payouts,
        "pending_payouts": pending_payouts,
        "active_listings_count": active_listings_count,
        "sold_items_count": sold_items_count,
        "recent_sales": recent_sales
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_success_api(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
    
    order_items = [{
        "item_title": item.item.title if item.item else item.item_title,
        "item_price": item.item_price,
        "quantity": item.quantity
    } for item in order.items.all()]

    return Response({
        "order_id": order.id,
        "total_amount": order.total_amount,
        "shipping_address": order.shipping_address,
        "created_at": order.created_at,
        "items": order_items
    })