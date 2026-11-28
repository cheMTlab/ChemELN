from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import CostCentre, Order, OrderEvent, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "customer_number", "is_active"]
    search_fields = ["name"]


@admin.register(CostCentre)
class CostCentreAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "group", "budget", "is_active"]
    list_filter = ["group", "is_active"]


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ["user", "from_status", "to_status", "note", "created_at"]


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ["number", "item_name", "group", "status", "requested_by", "created_at"]
    list_filter = ["status", "group"]
    search_fields = ["number", "item_name", "cas", "catalog_number", "po_number"]
    inlines = [OrderEventInline]
