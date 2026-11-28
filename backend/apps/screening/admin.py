from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Campaign, Response, Run, Variable


class VariableInline(admin.TabularInline):
    model = Variable
    extra = 0


class ResponseInline(admin.TabularInline):
    model = Response
    extra = 0


@admin.register(Campaign)
class CampaignAdmin(SimpleHistoryAdmin):
    list_display = ["title", "group", "equipment", "status", "created_at"]
    list_filter = ["group", "equipment", "status"]
    inlines = [VariableInline, ResponseInline]


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ["campaign", "index", "well", "status"]
    list_filter = ["status"]
