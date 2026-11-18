from django.core.management.base import BaseCommand

from locations.models import DeliveryHub, HubRoute

# Intercity road-ish durations for nearby city pairs (hours); every other
# pair falls back to the DEFAULT_LINEHAUL_HOURS = 24 used by linehaul.py.
# Keys are frozensets so either direction shares one duration.
TRANSIT_OVERRIDES = {
    frozenset(('Mumbai', 'Pune')): 8,
    frozenset(('Mumbai', 'Ahmedabad')): 16,
    frozenset(('Delhi', 'Jaipur')): 10,
    frozenset(('Delhi', 'Chandigarh')): 10,
    frozenset(('Bengaluru', 'Chennai')): 12,
    frozenset(('Hyderabad', 'Bengaluru')): 16,
    frozenset(('Hyderabad', 'Pune')): 18,
    frozenset(('Kolkata', 'Lucknow')): 22,
}

DEFAULT_HOURS = 24


class Command(BaseCommand):
    help = ("Seed HubRoute durations for every active hub pair "
            "(explicit nearby-pair overrides, 24h default elsewhere).")

    def handle(self, *args, **options):
        hubs = list(DeliveryHub.objects.filter(is_active=True))
        if len(hubs) < 2:
            self.stdout.write(self.style.WARNING(
                "Fewer than 2 active hubs - run seed_hubs first."))
            return

        created, updated, existing = 0, 0, 0
        for origin in hubs:
            for destination in hubs:
                if origin.city == destination.city:
                    continue   # intra-city: no line-haul leg
                hours = TRANSIT_OVERRIDES.get(
                    frozenset((origin.city, destination.city)), DEFAULT_HOURS)
                route, was_created = HubRoute.objects.get_or_create(
                    from_hub=origin,
                    to_hub=destination,
                    defaults={'transit_hours': hours, 'is_active': True},
                )
                if was_created:
                    created += 1
                elif route.transit_hours != hours:
                    route.transit_hours = hours
                    route.is_active = True
                    route.save(update_fields=['transit_hours', 'is_active', 'updated_at'])
                    updated += 1
                else:
                    existing += 1

        self.stdout.write(self.style.SUCCESS(
            f"Hub routes seeded: {created} created, {updated} updated, "
            f"{existing} existing left untouched."))
