from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Location


@admin.register(Location)
class LocationAdmin(SimpleHistoryAdmin):
    list_display = ["path", "kind", "group", "barcode", "temperature"]
    list_filter = ["kind", "group"]
    search_fields = ["path", "barcode"]
    autocomplete_fields = ["parent"]
