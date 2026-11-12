from .models import Notification


def notify(recipient, notification_type, message, order_item=None):
    if recipient is None or not getattr(recipient, 'pk', None):
        return None
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        message=message,
        order_item=order_item,
    )
