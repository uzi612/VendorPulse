from django.db import models
from django.contrib.auth.models import User

CITY_CHOICES = [
    ('Mumbai', 'Mumbai'),
    ('Delhi', 'Delhi'),
    ('Bengaluru', 'Bengaluru'),
    ('Hyderabad', 'Hyderabad'),
    ('Chennai', 'Chennai'),
    ('Kolkata', 'Kolkata'),
    ('Pune', 'Pune'),
    ('Ahmedabad', 'Ahmedabad'),
    ('Jaipur', 'Jaipur'),
    ('Lucknow', 'Lucknow'),
    ('Indore', 'Indore'),
    ('Chandigarh', 'Chandigarh'),
]

class Item(models.Model):
    CONDITION_CHOICES = [
        ('NEW', 'Brand New'),
        ('LIKE_NEW', 'Like New'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
    ]
    
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved'),
        ('SOLD', 'Sold'),
    ]

    # Admin moderation: every new/edited listing waits for review before it
    # is visible on the marketplace. Separate from `status`, which tracks the
    # purchase lifecycle (AVAILABLE -> RESERVED -> SOLD).
    APPROVAL_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    CATEGORY_CHOICES = [
        ('CLOTHING', 'Clothing'),
        ('ELECTRONICS', 'Electronics'),
        ('FURNITURE', 'Furniture'),
        ('BOOKS', 'Books'),
        ('VEHICLES', 'Vehicles'),
        ('OTHER', 'Other'),
    ]

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listed_items')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='OTHER')
    title = models.CharField(max_length=255)
    description = models.TextField()  
    price = models.DecimalField(max_digits=10, decimal_places=2)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='GOOD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='PENDING')
    rejection_reason = models.CharField(max_length=500, blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='listings_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    image = models.ImageField(upload_to='items/', blank=True, null=True)
    location = models.CharField(max_length=150, choices=CITY_CHOICES, blank=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.price}"


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart ({self.user.username})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'item')

    def __str__(self):
        return f"{self.item.title} in {self.cart.user.username}'s cart"