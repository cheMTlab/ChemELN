from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.models import Capability
from apps.chemistry.models import Compound
from apps.orgs.permissions import GroupScopedPermission, visible_group_ids, writable_group_ids

from . import plates, sequence
from .models import Assay, BioSample, Oligo, Plasmid, Plate, Strain, Well
from .serializers import (
    AssaySerializer,
    BioSampleSerializer,
    OligoSerializer,
    PlasmidListSerializer,
    PlasmidSerializer,
    PlateSerializer,
    StrainSerializer,
    WellSerializer,
)


def _visible(qs, user, biosafety=False):
    if user.is_staff or (biosafety and user.has_capability(Capability.BIOSAFETY_OFFICER)):
        return qs
    return qs.filter(group__in=visible_group_ids(user))


class _GroupViewSet(viewsets.ModelViewSet):
    permission_classes = [GroupScopedPermission]
    model = None
    search_fields: tuple = ()
    biosafety = True

    def get_queryset(self):
        qs = _visible(self.model.objects.select_related("group"), self.request.user, self.biosafety)
        p = self.request.query_params
        if q := p.get("q"):
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f"{f}__icontains": q})
            qs = qs.filter(cond)
        if g := p.get("group"):
            qs = qs.filter(group=g)
        return qs

    def perform_create(self, serializer):
        kwargs = {}
        if any(f.name == "created_by" for f in self.model._meta.fields):
            kwargs["created_by"] = self.request.user
        serializer.save(**kwargs)


class PlasmidViewSet(_GroupViewSet):
    model = Plasmid
    search_fields = (
        "code",
        "name",
        "alias",
        "backbone",
        "insert",
        "promoter",
        "tags",
        "resistance",
    )
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_serializer_class(self):
        return PlasmidListSerializer if self.action == "list" else PlasmidSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if r := self.request.query_params.get("resistance"):
            qs = qs.filter(resistance__icontains=r)
        if seq := self.request.query_params.get("sequence"):
            try:
                s = sequence.clean(seq)
            except ValueError as e:
                raise ValidationError({"sequence": str(e)}) from e
            rc = sequence.reverse_complement(s)
            qs = qs.filter(Q(sequence__contains=s) | Q(sequence__contains=rc))
        return qs

    @extend_schema(request=serializers.Serializer)
    @action(detail=False, methods=["post"], url_path="parse-genbank")
    def parse_genbank(self, request):
        """Read a GenBank file (upload 'file' or text 'genbank') without saving."""
        f = request.FILES.get("file")
        text = f.read().decode("utf-8", "replace") if f else request.data.get("genbank", "")
        try:
            return Response(sequence.parse_genbank(text))
        except ValueError as e:
            raise ValidationError({"detail": str(e)}) from e

    @action(detail=True, methods=["get"])
    def fasta(self, request, pk=None):
        p = self.get_object()
        resp = HttpResponse(
            sequence.to_fasta(f"{p.code} {p.name}", p.sequence), content_type="text/plain"
        )
        resp["Content-Disposition"] = f'attachment; filename="{p.code}.fasta"'
        return resp


class StrainViewSet(_GroupViewSet):
    model = Strain
    serializer_class = StrainSerializer
    search_fields = ("code", "name", "organism", "genotype", "source", "tissue")

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("plasmids")
        if k := self.request.query_params.get("kind"):
            qs = qs.filter(kind=k)
        if p := self.request.query_params.get("plasmid"):
            qs = qs.filter(plasmids=p)
        return qs


class OligoViewSet(_GroupViewSet):
    model = Oligo
    serializer_class = OligoSerializer
    search_fields = ("code", "name", "sequence", "target", "purpose")
    biosafety = False


class BioSampleViewSet(_GroupViewSet):
    model = BioSample
    serializer_class = BioSampleSerializer
    search_fields = ("barcode", "name", "notes", "box_position")

    def get_queryset(self):
        qs = super().get_queryset().select_related("plasmid", "strain", "location")
        for f in ("kind", "plasmid", "strain", "location"):
            if v := self.request.query_params.get(f):
                qs = qs.filter(**{f: v})
        if b := self.request.query_params.get("barcode"):
            qs = qs.filter(barcode=b)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            prepared_by=serializer.validated_data.get("prepared_by") or self.request.user
        )


class AssayViewSet(_GroupViewSet):
    model = Assay
    serializer_class = AssaySerializer
    search_fields = ("name", "target", "readout")
    biosafety = False


class PlateViewSet(_GroupViewSet):
    model = Plate
    serializer_class = PlateSerializer
    search_fields = ("barcode", "name", "notes")
    biosafety = False
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("assay", "experiment")
            .annotate(measurement_count=Count("wells__measurements"))
        )
        for f in ("kind", "assay", "experiment", "format"):
            if v := self.request.query_params.get(f):
                qs = qs.filter(**{f: v})
        return qs

    def perform_create(self, serializer):
        plate = serializer.save(created_by=self.request.user)
        plates.create_wells(plate)
        if plate.template_id:
            try:
                plates.copy_layout(plate.template, plate)
            except ValueError as e:
                raise ValidationError({"template": str(e)}) from e

    def _writable(self):
        plate = self.get_object()
        if plate.group_id not in writable_group_ids(self.request.user):
            raise PermissionDenied("You cannot change this plate.")
        return plate

    def _run(self, fn):
        try:
            return fn()
        except (ValueError, KeyError) as e:
            raise ValidationError({"detail": str(e)}) from e

    @action(detail=True, methods=["get"])
    def wells(self, request, pk=None):
        plate = self.get_object()
        qs = plate.wells.select_related("compound", "strain", "plasmid")
        return Response(WellSerializer(qs, many=True).data)

    @extend_schema(request=serializers.Serializer)
    @action(detail=True, methods=["post"])
    def layout(self, request, pk=None):
        """Body: {"wells": ["A1","A2"], "values": {"role": "positive", ...}}"""
        plate = self._writable()
        n = self._run(
            lambda: plates.apply_layout(
                plate, request.data.get("wells") or [], request.data.get("values") or {}
            )
        )
        return Response({"updated": n})

    @extend_schema(request=serializers.Serializer)
    @action(detail=True, methods=["post"])
    def dilution(self, request, pk=None):
        """Serial dilution: start_well, direction (row|column), steps, top, factor, unit,
        label, compound, replicates."""
        plate = self._writable()
        d = request.data
        compound = get_object_or_404(Compound, pk=d["compound"]) if d.get("compound") else None
        n = self._run(
            lambda: plates.dilution_series(
                plate,
                start_well=d.get("start_well", "A1"),
                direction=d.get("direction", "row"),
                steps=int(d.get("steps", 8)),
                top=float(d.get("top", 100)),
                factor=float(d.get("factor", 3)),
                unit=d.get("unit", "µM"),
                label=d.get("label", ""),
                compound=compound,
                replicates=int(d.get("replicates", 1)),
            )
        )
        return Response({"updated": n})

    @extend_schema(request=serializers.Serializer)
    @action(detail=True, methods=["post"], url_path="import-readings")
    def import_readings(self, request, pk=None):
        """Plate-reader export (grid or long format): file upload or 'text'."""
        plate = self._writable()
        f = request.FILES.get("file")
        text = f.read().decode("utf-8-sig", "replace") if f else request.data.get("text", "")
        out = self._run(
            lambda: plates.import_readings(
                plate,
                text,
                channel=request.data.get("channel") or "signal",
                timepoint=float(request.data.get("timepoint") or 0),
                replace=str(request.data.get("replace", "true")).lower() != "false",
            )
        )
        return Response(out, status=201)

    @action(detail=True, methods=["get"])
    def analysis(self, request, pk=None):
        p = request.query_params
        tp = p.get("timepoint")
        return Response(
            plates.analyse_plate(
                self.get_object(),
                channel=p.get("channel", "signal"),
                timepoint=float(tp) if tp not in (None, "") else None,
            )
        )

    @action(detail=True, methods=["get"])
    def kinetics(self, request, pk=None):
        return Response(
            plates.kinetic_series(self.get_object(), request.query_params.get("channel", "signal"))
        )

    @action(detail=True, methods=["get"], url_path="export")
    def export_csv(self, request, pk=None):
        """Layout + all readings in long format."""
        import csv
        import io

        plate = self.get_object()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "well",
                "role",
                "label",
                "compound",
                "strain",
                "plasmid",
                "concentration",
                "unit",
                "group",
                "excluded",
                "channel",
                "time",
                "value",
            ]
        )
        for well in plate.wells.select_related("compound", "strain", "plasmid").prefetch_related(
            "measurements"
        ):
            base = [
                well.name,
                well.role,
                well.label,
                well.compound.name if well.compound else "",
                well.strain.code if well.strain else "",
                well.plasmid.code if well.plasmid else "",
                well.concentration or "",
                well.concentration_unit,
                well.group_label,
                well.excluded,
            ]
            ms = list(well.measurements.all())
            if not ms:
                w.writerow(base + ["", "", ""])
            for m in ms:
                w.writerow(base + [m.channel, m.timepoint, m.value])
        resp = HttpResponse(buf.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{plate.barcode}.csv"'
        return resp


class WellViewSet(viewsets.ModelViewSet):
    serializer_class = WellSerializer
    permission_classes = [GroupScopedPermission]
    http_method_names = ["get", "patch", "head", "options"]

    def object_group_id(self, obj):
        return obj.plate.group_id

    def get_queryset(self):
        qs = Well.objects.select_related("plate", "compound", "strain", "plasmid")
        if not self.request.user.is_staff:
            qs = qs.filter(plate__group__in=visible_group_ids(self.request.user))
        if p := self.request.query_params.get("plate"):
            qs = qs.filter(plate=p)
        return qs


@api_view(["POST"])
def oligo_tools(request):
    """Tm, GC and reverse complement for any sequence (no saving)."""
    try:
        s = sequence.clean(request.data.get("sequence", ""))
    except ValueError as e:
        raise ValidationError({"sequence": str(e)}) from e
    return Response(
        {
            "length": len(s),
            "gc_content": sequence.gc_content(s),
            "tm": sequence.melting_temperature(s),
            "reverse_complement": sequence.reverse_complement(s),
        }
    )
