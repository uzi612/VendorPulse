from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Notification


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list_api(request):
    notifications = Notification.objects.filter(recipient=request.user).select_related('order_item')[:20]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    data = [{
        "id": n.id,
        "notification_type": n.notification_type,
        "message": n.message,
        "order_item_id": n.order_item_id,
        "tracking_number": n.order_item.tracking_number if n.order_item else None,
        "is_read": n.is_read,
        "created_at": n.created_at.strftime("%d %b %Y, %I:%M %p"),
    } for n in notifications]

    return Response({"unread_count": unread_count, "notifications": data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_mark_read_api(request, pk):
    try:
        notification = Notification.objects.get(pk=pk, recipient=request.user)
    except Notification.DoesNotExist:
        return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)

    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_read_all_api(request):
    updated = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return Response({"message": f"{updated} notifications marked as read."}, status=status.HTTP_200_OK)
