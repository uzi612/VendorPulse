from django.db import models
from django.contrib.auth.models import User


class Notification(models.Model):
    TYPE_CHOICES = [
        ('AGENT_ASSIGNED', 'Agent assigned to your order'),
        ('NEW_TASK', 'New delivery task'),
        ('STATUS_UPDATE', 'Delivery status updated'),
        ('ORDER_UPDATED', 'Order details updated'),
        ('NEW_SALE', 'New sale'),
        ('VERIFICATION', 'Account verification updated'),
        ('ASSIGNMENT_NEEDED', 'Order needs manual assignment'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='STATUS_UPDATE')
    message = models.TextField()
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"To {self.recipient.username}: {self.message[:40]}"
