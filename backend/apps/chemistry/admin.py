from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Compound, SafetyDataSheet


class SdsInline(admin.TabularInline):
    model = SafetyDataSheet
    extra = 0


@admin.register(Compound)
class CompoundAdmin(SimpleHistoryAdmin):
    list_display = ["name", "cas", "formula", "signal_word", "storage_class"]
    list_filter = ["storage_class", "signal_word", "is_peroxide_former", "is_controlled"]
    search_fields = ["name", "cas", "inchikey", "formula"]
    readonly_fields = ["smiles", "inchi", "inchikey", "formula", "mw", "exact_mass"]
    inlines = [SdsInline]
