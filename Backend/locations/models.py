from django.db import models

from products.models import CITY_CHOICES


class Zone(models.Model):
    """
    A delivery zone inside one city. Cities are big - "Mumbai" alone says
    nothing about WHERE an agent should go - so every city is split into
    numbered zones, each owning a contiguous pincode range.

    Pincode-first UX: the buyer types their 6-digit pincode at checkout and
    the system resolves (city, zone) from these ranges. Zone names are
    deliberately generic ("Zone 1".."Zone N") and admin-renamable later;
    renaming never changes the pincode ranges, which are the real locator.

    Ranges are per city: city pincode bases (e.g. Mumbai=400) are distinct
    3-digit prefixes, so ranges never overlap across cities.
    """
    city = models.CharField(max_length=30, choices=CITY_CHOICES, db_index=True)
    name = models.CharField(max_length=100)                     # "Zone 1"
    pincode_from = models.PositiveIntegerField()                # inclusive, 6 digits
    pincode_to = models.PositiveIntegerField()                  # inclusive, 6 digits
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['city', 'pincode_from']
        constraints = [
            models.UniqueConstraint(fields=['city', 'name'], name='zone_name_unique_per_city'),
            models.CheckConstraint(
                check=models.Q(pincode_from__gte=100000, pincode_to__lte=999999,
                               pincode_from__lte=models.F('pincode_to')),
                name='zone_pincode_range_valid',
            ),
        ]

    def __str__(self):
        return f"{self.city} / {self.name} ({self.pincode_from}-{self.pincode_to})"


class DeliveryHub(models.Model):
    """
    A physical sorting/collection point in one city. Intercity orders travel
    seller -> origin-city hub -> (line-haul) -> destination-city hub -> buyer,
    so agents never carry items across cities:

      - the PICKUP agent's final step is dropping the item at their city's hub
      - admin/ops runs the hub-to-hub line-haul (IN_TRANSIT)
      - the DELIVERY agent's first step is collecting from the buyer's
        city hub, then delivering to the buyer with the OTP

    zone is nullable: a hub without a zone serves its whole city.
    """
    city = models.CharField(max_length=30, choices=CITY_CHOICES, db_index=True)
    name = models.CharField(max_length=100)                 # "Central Hub"
    address = models.CharField(max_length=255)
    zone = models.ForeignKey('Zone', on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='hubs')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['city', 'name']
        constraints = [
            models.UniqueConstraint(fields=['city', 'name'], name='hub_name_unique_per_city'),
        ]

    def __str__(self):
        return f"{self.city} / {self.name}"


class HubRoute(models.Model):
    """
    Hub-to-hub line-haul duration (the "shipping time" between two cities).

    When an intercity item is dispatched (IN_TRANSIT), the admin endpoint
    looks up the origin->destination route and stamps an ETA on the OrderItem
    (linehaul_eta_at). When that ETA elapses, settle_linehaul_arrivals()
    marks the item arrived at the destination hub and auto-assigns the
    buyer-city delivery agent - no manual "arrived" click needed.

    transit_hours = 24 is the fallback for pairs without an explicit route,
    so a missing seed row can never stall an order.
    """
    from_hub = models.ForeignKey(DeliveryHub, on_delete=models.CASCADE,
                                 related_name='routes_from')
    to_hub = models.ForeignKey(DeliveryHub, on_delete=models.CASCADE,
                               related_name='routes_to')
    transit_hours = models.PositiveIntegerField(default=24)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['from_hub__city', 'to_hub__city']
        constraints = [
            models.UniqueConstraint(fields=['from_hub', 'to_hub'],
                                    name='hub_route_pair_unique'),
            models.CheckConstraint(
                check=models.Q(transit_hours__gte=1, transit_hours__lte=720),
                name='hub_route_transit_hours_valid',
            ),
        ]

    def __str__(self):
        return f"{self.from_hub.city} -> {self.to_hub.city}: {self.transit_hours}h"
