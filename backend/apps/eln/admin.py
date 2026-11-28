from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Attachment,
    Experiment,
    ExperimentTemplate,
    Project,
    ReactionComponent,
    Signature,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "group", "status"]
    list_filter = ["group", "status"]


class ComponentInline(admin.TabularInline):
    model = ReactionComponent
    extra = 0


@admin.register(Experiment)
class ExperimentAdmin(SimpleHistoryAdmin):
    list_display = ["code", "title", "owner", "group", "status", "signed_at"]
    list_filter = ["group", "status", "kind"]
    search_fields = ["code", "title"]
    inlines = [ComponentInline]


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ["seq", "experiment", "kind", "user", "created_at"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(ExperimentTemplate)
admin.site.register(Attachment)
