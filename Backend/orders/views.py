from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderItemSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_list_api(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail_api(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    serializer = OrderSerializer(order)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seller_sales_api(request):
    sales = OrderItem.objects.filter(seller=request.user).select_related('order', 'item').order_by('-order__created_at')
    serializer = OrderItemSerializer(sales, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_order_item_status_api(request, pk):
    order_item = get_object_or_404(OrderItem, pk=pk)
    
    if order_item.seller != request.user and not request.user.is_staff:
        return Response({"detail": "You do not have permission to modify this order status."}, status=status.HTTP_403_FORBIDDEN)

    new_status = request.data.get('status')
    valid_statuses = [choice[0] for choice in OrderItem.ORDER_STATUS_CHOICES]

    if new_status not in valid_statuses:
        return Response({"detail": f"Invalid status choice. Must be one of: {valid_statuses}"}, status=status.HTTP_400_BAD_REQUEST)

    order_item.status = new_status
    order_item.save()

    serializer = OrderItemSerializer(order_item)
    return Response({"detail": "Order status updated successfully.", "order_item": serializer.data}, status=status.HTTP_200_OK)