from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Assay, BioSample, Oligo, Plasmid, Plate, Strain


@admin.register(Plasmid)
class PlasmidAdmin(SimpleHistoryAdmin):
    list_display = ["code", "name", "group", "backbone", "size_bp", "verified"]
    search_fields = ["code", "name", "insert"]
    list_filter = ["group", "verified"]


@admin.register(Strain)
class StrainAdmin(SimpleHistoryAdmin):
    list_display = ["code", "name", "kind", "organism", "biosafety_level", "group"]
    list_filter = ["kind", "biosafety_level", "group"]
    search_fields = ["code", "name"]


@admin.register(Oligo)
class OligoAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "sequence", "tm", "group"]
    search_fields = ["code", "name", "sequence"]


@admin.register(BioSample)
class BioSampleAdmin(SimpleHistoryAdmin):
    list_display = ["barcode", "name", "kind", "group", "location"]
    list_filter = ["kind", "group"]


@admin.register(Plate)
class PlateAdmin(SimpleHistoryAdmin):
    list_display = ["barcode", "name", "format", "kind", "group"]
    list_filter = ["kind", "format", "group"]


admin.site.register(Assay)
