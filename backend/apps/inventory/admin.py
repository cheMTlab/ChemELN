from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Container, ContainerEvent


class EventInline(admin.TabularInline):
    model = ContainerEvent
    extra = 0
    readonly_fields = [
        "kind",
        "user",
        "amount_change",
        "from_location",
        "to_location",
        "note",
        "created_at",
    ]
    can_delete = False


@admin.register(Container)
class ContainerAdmin(SimpleHistoryAdmin):
    list_display = [
        "barcode",
        "compound",
        "amount",
        "unit",
        "group",
        "location",
        "status",
        "expiry_date",
    ]
    list_filter = ["status", "group", "unit"]
    search_fields = ["barcode", "compound__name", "compound__cas", "lot_number"]
    autocomplete_fields = ["compound", "location", "owner"]
    inlines = [EventInline]
