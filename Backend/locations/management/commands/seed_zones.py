from django.core.management.base import BaseCommand

from locations.models import Zone
from products.models import CITY_CHOICES

# Real 3-digit PIN prefixes per city (India Post). Each city owns the range
# base*1000 .. base*1000+999, so ranges never overlap across cities and ANY
# real pincode of these cities resolves to exactly one zone.
CITY_PIN_BASES = {
    'Mumbai': 400,
    'Delhi': 110,
    'Bengaluru': 560,
    'Hyderabad': 500,
    'Chennai': 600,
    'Kolkata': 700,
    'Pune': 411,
    'Ahmedabad': 380,
    'Jaipur': 302,
    'Lucknow': 226,
    'Indore': 452,
    'Chandigarh': 160,
}

# Metros get more zones; smaller cities fewer. 12 cities, 49 zones total.
CITY_ZONE_COUNTS = {
    'Mumbai': 5, 'Delhi': 5,
    'Bengaluru': 4, 'Hyderabad': 4, 'Chennai': 4, 'Kolkata': 4, 'Pune': 4,
    'Ahmedabad': 3, 'Jaipur': 3, 'Lucknow': 3, 'Indore': 3, 'Chandigarh': 3,
}


class Command(BaseCommand):
    help = "Seed numbered delivery zones (Zone 1..N) with real per-city pincode ranges."

    def handle(self, *args, **options):
        created, updated = 0, 0
        for city, _ in CITY_CHOICES:
            base = CITY_PIN_BASES[city]
            n_zones = CITY_ZONE_COUNTS[city]
            size = 1000 // n_zones
            for i in range(n_zones):
                pincode_from = base * 1000 + i * size
                # last zone absorbs the remainder so ranges tile the full 000-999 span
                pincode_to = (base * 1000 + 999) if i == n_zones - 1 else pincode_from + size - 1
                name = f"Zone {i + 1}"
                obj, was_created = Zone.objects.get_or_create(
                    city=city, name=name,
                    defaults={'pincode_from': pincode_from, 'pincode_to': pincode_to,
                              'is_active': True},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"Zones seeded: {created} created, {updated} existing left untouched."))
