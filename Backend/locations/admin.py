from django.contrib import admin

from .models import Zone, DeliveryHub


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
