from django.db import models
from django.contrib.auth.models import User
from products.models import Item

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    shipping_address = models.TextField(default="", blank=True, null=True)
    phone = models.CharField(max_length=15, default="", blank=True, null=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

class OrderItem(models.Model):
    ORDER_STATUS_CHOICES = [
        ('ORDER_PLACED', 'Order Placed'),
        ('PICKUP_SCHEDULED', 'VendorPulse Pickup Scheduled'),
        ('PICKED_UP', 'Picked Up from Seller'),
        ('DISPATCHED', 'In Transit / Dispatched'),
        ('DELIVERED', 'Delivered to Buyer'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    item_title = models.CharField(max_length=200)
    item_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, choices=ORDER_STATUS_CHOICES, default='ORDER_PLACED')
    
    def __str__(self):
        return f"{self.item_title} (Seller: {self.seller.username})"