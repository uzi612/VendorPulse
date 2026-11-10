from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from .serializers import RegisterSerializer, UserSerializer
from .models import Profile
from orders.models import Order, OrderItem

@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "message": "User registered successfully",
            "token": token.key,
            "user": UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({"error": "Please provide both username and password"}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "message": "Login successful",
            "token": token.key,
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        request.user.auth_token.delete()
    except (AttributeError, Token.DoesNotExist):
        pass
    return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile_api(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    
    if request.method == 'PUT':
        profile.phone = request.data.get('phone', profile.phone)
        profile.city = request.data.get('city', profile.city)
        profile.save()
        
    # Serialize orders for the profile page view
    orders = [{
        "id": o.id,
        "total_price": o.total_price,
        "created_at": o.created_at.strftime("%d %b %Y, %I:%M %p"),
        "status": o.items.first().status if o.items.exists() else "ORDER_PLACED",
        "items": [{"item_title": i.item_title, "item_price": i.item_price} for i in o.items.all()]
    } for o in Order.objects.filter(user=user).order_by('-created_at')]

    # Serialize sales for the seller items sold view
    sales = [{
        "id": s.id,
        "item_title": s.item_title,
        "item_price": s.item_price,
        "status": s.status,
        "buyer": s.order.user.username,
        "shipping_address": s.order.shipping_address,
        "created_at": s.order.created_at.strftime("%d %b %Y, %I:%M %p")
    } for s in OrderItem.objects.filter(seller=user).select_related('order', 'order__user').order_by('-order__created_at')]

    return Response({
        "username": user.username,
        "email": user.email,
        "date_joined": user.date_joined.strftime("%b %Y"),
        "profile": {
            "phone": profile.phone or "",
            "city": profile.city or "",
        },
        "orders": orders,
        "sales": sales
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def role_login_api(request):
    username = request.data.get('username')
    password = request.data.get('password')
    expected_role = request.data.get('role')  # 'admin' or 'agent'

    user = authenticate(username=username, password=password)
    if not user:
        return Response({"error": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)

    # Determine user's actual role
    is_admin = user.is_staff or user.is_superuser
    is_agent = user.groups.filter(name='DeliveryAgent').exists()

    # Enforce portal-specific access
    if expected_role == 'admin' and not is_admin:
        return Response({"error": "Access denied. Admin privileges required."}, status=status.HTTP_403_FORBIDDEN)

    if expected_role == 'agent' and not is_agent:
        return Response({"error": "Access denied. Registered Delivery Agent account required."}, status=status.HTTP_403_FORBIDDEN)

    token, _ = Token.objects.get_or_create(user=user)
    role = 'admin' if is_admin else ('agent' if is_agent else 'customer')

    return Response({
        "token": token.key,
        "user_id": user.id,
        "username": user.username,
        "role": role
    }, status=status.HTTP_200_OK)