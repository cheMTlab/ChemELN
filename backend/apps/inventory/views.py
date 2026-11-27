from dataclasses import asdict

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.chemistry.models import Compound
from apps.chemistry.views import SEARCH_PARAMS, apply_structure_search
from apps.locations.models import Location
from apps.orgs.models import ResearchGroup
from apps.orgs.permissions import writable_group_ids

from . import importer, labels, services
from .models import Container, ContainerEvent, EventKind
from .serializers import (
    AdjustSerializer,
    ContainerEventSerializer,
    ContainerSerializer,
    MoveSerializer,
    StatusSerializer,
    UseSerializer,
)


def visible_containers(user):
    qs = Container.objects.select_related("compound", "group", "owner", "location")
    if settings.CHEMTLAB["INVENTORY_VISIBILITY"] == "group" and not user.is_staff:
        qs = qs.filter(group__memberships__user=user).distinct()
    return qs


CONTAINER_PARAMS = [
    *SEARCH_PARAMS,
    OpenApiParameter("barcode", str, description="Exact barcode (scanner input)"),
    OpenApiParameter("location", str, description="Location id (includes sub-locations)"),
    OpenApiParameter("group", str),
    OpenApiParameter("status", str, description="Comma-separated; default hides disposed"),
    OpenApiParameter("hazard", str, description="GHS pictogram, e.g. GHS02"),
    OpenApiParameter("compound", str),
    OpenApiParameter("mine", bool),
]


@extend_schema(parameters=CONTAINER_PARAMS)
class ContainerViewSet(viewsets.ModelViewSet):
    """Containers. Everyone signed in can find them (unless the instance restricts visibility
    to groups); only members of the owning group can change them."""

    serializer_class = ContainerSerializer
    _search_context: dict

    def get_queryset(self):
        self._search_context = {}
        qs = visible_containers(self.request.user)
        if self.action != "list":
            return qs
        p = self.request.query_params
        if barcode := p.get("barcode"):
            return qs.filter(barcode=barcode)
        if any(p.get(k) for k in ("q", "substructure", "similar")):
            compounds = apply_structure_search(Compound.objects.all(), p, self._search_context)
            qs = qs.filter(compound__in=compounds)
        if loc := p.get("location"):
            qs = qs.filter(location__in=get_object_or_404(Location, pk=loc).descendant_ids())
        if group := p.get("group"):
            qs = qs.filter(group=group)
        if compound := p.get("compound"):
            qs = qs.filter(compound=compound)
        if hazard := p.get("hazard"):
            qs = qs.filter(compound__ghs_pictograms__icontains=hazard)
        if p.get("mine") in ("1", "true"):
            qs = qs.filter(owner=self.request.user)
        statuses = p.get("status")
        qs = (
            qs.filter(status__in=statuses.split(",")) if statuses else qs.exclude(status="disposed")
        )
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx.update(getattr(self, "_search_context", {}))
        return ctx

    def _check_write(self, container: Container):
        if container.group_id not in writable_group_ids(self.request.user):
            raise PermissionDenied("Only members of the owning group can change this container.")

    def perform_create(self, serializer):
        container = serializer.save(
            owner=serializer.validated_data.get("owner") or self.request.user
        )
        ContainerEvent.objects.create(
            container=container,
            user=self.request.user,
            kind=EventKind.CREATED,
            to_location=container.location,
        )

    def perform_update(self, serializer):
        self._check_write(serializer.instance)
        old_location = serializer.instance.location
        container = serializer.save()
        if container.location != old_location:
            ContainerEvent.objects.create(
                container=container,
                user=self.request.user,
                kind=EventKind.MOVED,
                from_location=old_location,
                to_location=container.location,
            )

    def perform_destroy(self, instance):
        self._check_write(instance)
        if not self.request.user.is_staff:
            raise PermissionDenied("Mark the container as disposed instead of deleting it.")
        instance.delete()

    def _action(self, request, ser_class, fn):
        container = self.get_object()
        self._check_write(container)
        ser = ser_class(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            container = fn(container, ser.validated_data)
        except services.InventoryError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(ContainerSerializer(container, context={"request": request}).data)

    @extend_schema(request=MoveSerializer, responses=ContainerSerializer)
    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        return self._action(
            request,
            MoveSerializer,
            lambda c, d: services.move(c, d["location"], request.user, d.get("note", "")),
        )

    @extend_schema(request=UseSerializer, responses=ContainerSerializer)
    @action(detail=True, methods=["post"])
    def use(self, request, pk=None):
        return self._action(
            request,
            UseSerializer,
            lambda c, d: services.use(c, d["amount"], d["unit"], request.user, d.get("note", "")),
        )

    @extend_schema(request=AdjustSerializer, responses=ContainerSerializer)
    @action(detail=True, methods=["post"])
    def adjust(self, request, pk=None):
        return self._action(
            request,
            AdjustSerializer,
            lambda c, d: services.adjust(c, d["amount"], request.user, d.get("note", "")),
        )

    @extend_schema(request=StatusSerializer, responses=ContainerSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        return self._action(
            request,
            StatusSerializer,
            lambda c, d: services.set_status(c, d["status"], request.user, d.get("note", "")),
        )

    @extend_schema(responses=ContainerEventSerializer(many=True))
    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        events = self.get_object().events.select_related("user", "from_location", "to_location")
        return Response(ContainerEventSerializer(events, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("ids", str, required=True, description="Comma-separated ids"),
            OpenApiParameter("layout", str, enum=list(labels.LAYOUTS)),
        ],
        responses={(200, "application/pdf"): bytes},
    )
    @action(detail=False, methods=["get"])
    def labels(self, request):
        ids = [i for i in request.query_params.get("ids", "").split(",") if i]
        layout = request.query_params.get("layout", "roll-62x29")
        if not ids or layout not in labels.LAYOUTS:
            raise ValidationError("Give ids=... and a valid layout.")
        try:
            containers = list(visible_containers(request.user).filter(id__in=ids))
        except Exception as exc:  # malformed UUIDs
            raise ValidationError("Invalid container id.") from exc
        pdf = labels.render_labels(containers, layout)
        res = HttpResponse(pdf, content_type="application/pdf")
        res["Content-Disposition"] = 'inline; filename="chemtlab-labels.pdf"'
        return res

    @extend_schema(responses=serializers.DictField())
    @action(detail=False, methods=["get"])
    def alerts(self, request):
        """Expired, expiring, peroxide re-test, low stock and storage conflicts in my groups."""
        qs = Container.objects.select_related("compound", "group", "owner", "location")
        if not request.user.is_staff:
            qs = qs.filter(group__memberships__user=request.user).distinct()
        out = {}
        for key, items in services.alerts(qs).items():
            items = list(items)
            out[key] = {
                "count": len(items),
                "items": ContainerSerializer(
                    items[:20], many=True, context={"request": request}
                ).data,
            }
        return Response(out)


class ImportUpload(serializers.Serializer):
    file = serializers.FileField()
    group = serializers.PrimaryKeyRelatedField(queryset=ResearchGroup.objects.all())
    dry_run = serializers.BooleanField(default=True)


@extend_schema(request={"multipart/form-data": ImportUpload}, responses=serializers.DictField())
@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def import_containers(request):
    """Import a CSV or SDF file. Use dry_run=true first to see problems without saving."""
    ser = ImportUpload(data=request.data)
    ser.is_valid(raise_exception=True)
    group = ser.validated_data["group"]
    if group.id not in writable_group_ids(request.user):
        raise PermissionDenied("You are not a member of this group.")
    upload = ser.validated_data["file"]
    if upload.size > 20 * 1024 * 1024:
        raise ValidationError("File too large (max 20 MB).")
    content = upload.read()
    name = upload.name.lower()
    rows = (
        importer.rows_from_sdf(content)
        if name.endswith((".sdf", ".sd"))
        else importer.rows_from_csv(content)
    )
    result = importer.import_rows(rows, group, request.user, ser.validated_data["dry_run"])
    return Response(asdict(result))
