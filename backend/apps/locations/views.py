from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.orgs.models import Role
from apps.orgs.permissions import has_group_role

from .models import Location
from .serializers import LocationSerializer


def can_manage(user, group) -> bool:
    """Shared locations: staff only. Group locations: that group's PI/admin (or staff)."""
    if user.is_staff:
        return True
    return group is not None and has_group_role(user, group, Role.PI)


@extend_schema(
    parameters=[
        OpenApiParameter("parent", str, description="Children of this location ('root' for top)"),
        OpenApiParameter("q", str, description="Search name, path or barcode"),
    ]
)
class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer

    def get_queryset(self):
        qs = Location.objects.annotate(
            container_count=Count("containers", filter=~Q(containers__status="disposed"))
        )
        params = self.request.query_params
        if parent := params.get("parent"):
            qs = qs.filter(parent__isnull=True) if parent == "root" else qs.filter(parent=parent)
        if q := params.get("q"):
            qs = qs.filter(Q(path__icontains=q) | Q(barcode=q))
        return qs

    def perform_create(self, serializer):
        group = serializer.validated_data.get("group")
        if not can_manage(self.request.user, group):
            raise PermissionDenied("You cannot create locations here.")
        serializer.save()

    def perform_update(self, serializer):
        new_group = serializer.validated_data.get("group", serializer.instance.group)
        if not (
            can_manage(self.request.user, serializer.instance.group)
            and can_manage(self.request.user, new_group)
        ):
            raise PermissionDenied("You cannot change this location.")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage(self.request.user, instance.group):
            raise PermissionDenied("You cannot delete this location.")
        if instance.children.exists() or instance.containers.exists():
            raise ValidationError("Move its sub-locations and containers first.")
        instance.delete()
