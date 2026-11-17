from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from products.models import Item, CITY_CHOICES

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    shipping_address = models.TextField(default="", blank=True, null=True)
    shipping_city = models.CharField(max_length=100, choices=CITY_CHOICES, blank=True, null=True)
    # Pincode-first delivery: buyer's 6-digit pincode resolves the zone; the
    # zone FK + name snapshot work like OrderItem's item_title snapshot - the
    # FK tracks the live zone, the name preserves order history if a zone is
    # later renamed or deactivated.
    pincode = models.CharField(max_length=6, null=True, blank=True)
    shipping_zone = models.ForeignKey('locations.Zone', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='orders')
    shipping_zone_name = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=15, default="", blank=True, null=True)
    delivery_otp = models.CharField(max_length=4, null=True, blank=True)
    
    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

class OrderItem(models.Model):
    ORDER_STATUS_CHOICES = [
        ('ORDER_PLACED', 'Order Placed'),
        ('PICKUP_SCHEDULED', 'VendorPulse Pickup Scheduled'),
        ('PICKED_UP', 'Picked Up from Seller'),
        # --- intra-city ladder (assigned_agent delivers directly) ---
        ('DISPATCHED', 'In Transit / Dispatched'),
        # --- intercity ladder: hub-based handover across cities ---
        ('DROPPED_AT_ORIGIN_HUB', 'Dropped at Origin Hub'),
        ('IN_TRANSIT', 'In Transit (Hub to Hub)'),
        ('AT_DESTINATION_HUB', 'At Destination Hub'),
        # --- shared completion ---
        ('DELIVERED', 'Delivered to Buyer'),
        ('CANCELLED', 'Cancelled by Buyer'),
    ]
    # Why the buyer cancelled (only set on CANCELLED items; shown to the seller)
    CANCEL_REASON_CHOICES = [
        ('CHANGED_MIND', 'Changed my mind'),
        ('WRONG_ADDRESS', 'Wrong shipping address'),
        ('FOUND_ELSEWHERE', 'Found it elsewhere'),
        ('OTHER', 'Other'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    item_title = models.CharField(max_length=200)
    item_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, choices=ORDER_STATUS_CHOICES, default='ORDER_PLACED')
    assigned_agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_deliveries'
    )
    # Leg-2 agent for INTERCITY items (buyer's city/zone): performs the
    # DISPATCHED -> DELIVERED step with the buyer's OTP. NULL for intra-city
    # items, where assigned_agent delivers directly (zero behavior change).
    delivery_agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delivery_tasks'
    )
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    # Set when the buyer cancels (before pickup). Shown to the seller.
    cancel_reason = models.CharField(max_length=30, choices=CANCEL_REASON_CHOICES, null=True, blank=True)
    cancel_note = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.item_title} (Seller: {self.seller.username})"


class Rating(models.Model):
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name='rating')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_ratings_received')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_ratings_received')

    seller_stars = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    seller_comment = models.TextField(blank=True, null=True)
    agent_stars = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    agent_comment = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(seller_stars__isnull=False) | models.Q(agent_stars__isnull=False),
                name='rating_has_at_least_one_stars',
            )
        ]

    def __str__(self):
        return f"Rating for OrderItem #{self.order_item_id} by {self.buyer.username}"


class Dispute(models.Model):
    """
    Buyer's problem report for one DELIVERED item (returns/quality issues).

    One row per OrderItem (OneToOne, like Rating) — a buyer can escalate a
    delivery exactly once; the admin then resolves or rejects it with a
    written note. Disputes start where cancellation ends: items still in
    transit are handled through the tracking/assignment flow instead.
    """
    REASON_CHOICES = [
        ('DAMAGED', 'Item arrived damaged'),
        ('NOT_AS_DESCRIBED', 'Not as described'),
        ('NOT_RECEIVED', 'Never received the item'),
        ('OTHER', 'Other'),
    ]
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
    ]

    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name='dispute')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='disputes_filed')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='disputes_received')
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    resolution_note = models.TextField(blank=True, null=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputes_resolved')
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dispute #{self.id} on OrderItem #{self.order_item_id} ({self.status})"