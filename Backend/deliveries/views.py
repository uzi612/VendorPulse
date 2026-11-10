from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User, Group
from orders.models import OrderItem
from accounts.models import Profile

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_delivery_list(request):
    order_items = OrderItem.objects.all().order_by('-id')
    
    data = []
    for item in order_items:
        # Fetch seller's city/address from their Profile model safely
        seller_city = getattr(item.seller, 'profile', None) and getattr(item.seller.profile, 'city', '') or 'N/A'
        
        data.append({
            "id": item.id,
            "order_id": item.order.id,
            "shipping_address": item.order.shipping_address or 'N/A',
            "phone": item.order.phone or 'N/A',
            "item_title": item.item_title,
            "item_price": str(item.item_price),
            "seller_username": item.seller.username,
            "seller_address": seller_city if seller_city else 'N/A', # Added seller address
            "status": item.status,
            "tracking_number": item.tracking_number or '',
            "agent_username": item.assigned_agent.username if item.assigned_agent else None,
            "assigned_agent": item.assigned_agent.id if item.assigned_agent else None,
        })

    return Response(data, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_assign_delivery(request, pk):
    try:
        item = OrderItem.objects.get(pk=pk)
    except OrderItem.DoesNotExist:
        return Response({"error": "Order item not found."}, status=status.HTTP_404_NOT_FOUND)

    agent_id = request.data.get('assigned_agent')
    tracking_number = request.data.get('tracking_number')

    if agent_id:
        try:
            agent = User.objects.get(pk=agent_id)
            item.assigned_agent = agent
        except User.DoesNotExist:
            return Response({"error": "Agent not found."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        item.assigned_agent = None

    if tracking_number is not None:
        item.tracking_number = tracking_number

    item.save()
    return Response({"message": "Delivery assignment updated successfully!"}, status=status.HTTP_200_OK)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_staff_management(request):
    if request.method == 'GET':
        staff_users = User.objects.filter(is_staff=True) | User.objects.filter(groups__name='DeliveryAgent') | User.objects.filter(profile__is_delivery_agent=True)
        data = []
        for u in staff_users.distinct():
            city = getattr(u, 'profile', None) and getattr(u.profile, 'city', '') or 'N/A'
            is_agent = (getattr(u, 'profile', None) and u.profile.is_delivery_agent) or u.groups.filter(name='DeliveryAgent').exists()
            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "address": city if city else 'N/A',
                "is_staff": u.is_staff,
                "is_agent": is_agent
            })
        return Response(data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email', '')
        city = request.data.get('address', '')
        role = request.data.get('role', 'agent')

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password, email=email)
        
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.city = city
        if role == 'agent':
            profile.is_delivery_agent = True
            group, _ = Group.objects.get_or_create(name='DeliveryAgent')
            user.groups.add(group)
        profile.save()

        if role == 'admin':
            user.is_staff = True
            user.save()

        return Response({"message": "Staff/Agent created successfully!"}, status=status.HTTP_201_CREATED)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_update_staff(request, pk):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({"error": "Staff member not found."}, status=status.HTTP_404_NOT_FOUND)

    email = request.data.get('email')
    city = request.data.get('address')
    role = request.data.get('role')

    if email is not None:
        user.email = email
    
    if role == 'admin':
        user.is_staff = True
        group = Group.objects.filter(name='DeliveryAgent').first()
        if group:
            user.groups.remove(group)
        if hasattr(user, 'profile'):
            user.profile.is_delivery_agent = False
            user.profile.save()
    elif role == 'agent':
        user.is_staff = False
        group, _ = Group.objects.get_or_create(name='DeliveryAgent')
        user.groups.add(group)
        if hasattr(user, 'profile'):
            user.profile.is_delivery_agent = True
            user.profile.save()

    user.save()

    if city is not None:
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.city = city
        profile.save()

    return Response({"message": "Staff profile updated successfully!"}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_delivery_list(request):
    order_items = OrderItem.objects.filter(assigned_agent=request.user).order_by('-id')
    
    data = []
    for item in order_items:
        seller_city = getattr(item.seller, 'profile', None) and getattr(item.seller.profile, 'city', '') or 'N/A'
        
        data.append({
            "id": item.id,
            "order_id": item.order.id,
            "shipping_address": item.order.shipping_address or 'N/A',
            "phone": item.order.phone or 'N/A',
            "item_title": item.item_title,
            "seller_username": item.seller.username,
            "seller_address": seller_city if seller_city else 'N/A', # Added seller address for agents
            "status": item.status,
            "tracking_number": item.tracking_number or '',
        })
    return Response(data, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def agent_update_status(request, pk):
    try:
        order_item = OrderItem.objects.get(pk=pk, assigned_agent=request.user)
    except OrderItem.DoesNotExist:
        return Response({"error": "Order item not found or not assigned to you."}, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get('status')
    valid_statuses = ['ORDER_PLACED', 'PICKUP_SCHEDULED', 'PICKED_UP', 'DISPATCHED', 'DELIVERED']

    if new_status not in valid_statuses:
        return Response({"error": "Invalid status choice."}, status=status.HTTP_400_BAD_REQUEST)

    order_item.status = new_status
    order_item.save()

    if new_status == 'DELIVERED' and order_item.item:
        order_item.item.status = 'SOLD'
        order_item.item.save()

    return Response({
        "message": "Status updated successfully!",
        "id": order_item.id,
        "status": order_item.status
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_profile_view(request):
    user = request.user
    city = getattr(user, 'profile', None) and getattr(user.profile, 'city', '') or 'N/A'
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email or 'N/A',
        "address": city if city else 'N/A'
    }, status=status.HTTP_200_OK)