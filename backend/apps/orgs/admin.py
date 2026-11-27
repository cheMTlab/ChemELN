from django.contrib import admin

from .models import Department, Institution, Membership, ResearchGroup


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["name", "short_name", "country", "ror_id"]
    search_fields = ["name", "short_name"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "institution"]
    list_filter = ["institution"]
    search_fields = ["name"]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1
    autocomplete_fields = ["user"]


@admin.register(ResearchGroup)
class ResearchGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "department"]
    list_filter = ["department__institution", "department"]
    search_fields = ["name"]
    inlines = [MembershipInline]
