from django.core.management.base import BaseCommand

from locations.models import DeliveryHub
from products.models import CITY_CHOICES


class Command(BaseCommand):
    help = "Seed one active DeliveryHub per city (generic 'Central Hub')."

    def handle(self, *args, **options):
        created, existing = 0, 0
        for city, _ in CITY_CHOICES:
            obj, was_created = DeliveryHub.objects.get_or_create(
                city=city, name='Central Hub',
                defaults={
                    'address': f'{city} Central Sorting Facility (contact ops for the exact gate)',
                    'zone': None,      # city-wide: any agent in the city can use it
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
            else:
                existing += 1
        self.stdout.write(self.style.SUCCESS(
            f"Hubs seeded: {created} created, {existing} existing left untouched."))
