from django.contrib import admin

from .models import Zone, DeliveryHub, HubRoute


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('city', 'name', 'pincode_from', 'pincode_to', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name',)


@admin.register(DeliveryHub)
class DeliveryHubAdmin(admin.ModelAdmin):
    list_display = ('city', 'name', 'address', 'zone', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name', 'address')


@admin.register(HubRoute)
class HubRouteAdmin(admin.ModelAdmin):
    list_display = ('from_hub', 'to_hub', 'transit_hours', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('from_hub__city', 'to_hub__city')
