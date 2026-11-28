import csv
import io
import random

from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response as R

from apps.orgs.permissions import GroupScopedPermission, visible_group_ids, writable_group_ids

from . import analysis, design
from .models import Campaign, Response, Run, RunStatus, Variable
from .serializers import (
    CampaignSerializer,
    GenerateSerializer,
    ResponseSerializer,
    RunSerializer,
    VariableSerializer,
)


def _vars(campaign):
    return [
        {
            "id": str(v.id),
            "name": v.name,
            "kind": v.kind,
            "unit": v.unit,
            "low": v.low,
            "high": v.high,
            "levels": v.levels,
        }
        for v in campaign.variables.all()
    ]


def _resps(campaign):
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "unit": r.unit,
            "goal": r.goal,
            "target": r.target,
            "weight": r.weight,
        }
        for r in campaign.responses.all()
    ]


def _runs(campaign):
    return [
        {"factors": r.factors, "results": r.results, "status": r.status}
        for r in campaign.runs.all()
    ]


class CampaignViewSet(viewsets.ModelViewSet):
    """Optimization campaigns: variables, responses, designed runs, analysis, suggestions."""

    serializer_class = CampaignSerializer
    permission_classes = [GroupScopedPermission]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = (
            Campaign.objects.select_related("group", "owner")
            .prefetch_related("variables", "responses")
            .annotate(
                run_count=Count("runs", distinct=True),
                done_count=Count("runs", filter=Q(runs__status=RunStatus.DONE), distinct=True),
            )
        )
        if not self.request.user.is_staff:
            qs = qs.filter(group__in=visible_group_ids(self.request.user))
        for f in ("group", "status", "project", "equipment"):
            if v := self.request.query_params.get(f):
                qs = qs.filter(**{f: v})
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def _writable(self):
        c = self.get_object()
        if c.group_id not in writable_group_ids(self.request.user):
            raise PermissionDenied("You cannot change this campaign.")
        return c

    @extend_schema(request=GenerateSerializer, responses=RunSerializer(many=True))
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def generate(self, request, pk=None):
        """Create planned runs from a design (full factorial, LHS, random, centre, OFAT)."""
        campaign = self._writable()
        s = GenerateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            points = design.generate(d["design"], _vars(campaign), d["n"], d["levels"], d["seed"])
        except ValueError as e:
            raise ValidationError({"detail": str(e)}) from e
        if d["replace"]:
            campaign.runs.filter(status=RunStatus.PLANNED).delete()
        if d["randomize_order"]:
            random.Random(d["seed"]).shuffle(points)  # noqa: S311 - run order, not security
        start = (campaign.runs.aggregate(m=Max("index"))["m"] or 0) + 1
        wells = design.assign_wells(start - 1 + len(points), campaign.plate_format)
        runs = []
        for i, f in enumerate(points):
            idx = start + i
            plate, well = wells[idx - 1] if campaign.equipment == "hte_plate" else (None, "")
            runs.append(
                Run(
                    campaign=campaign,
                    index=idx,
                    factors=f,
                    plate=plate,
                    well=well,
                    source=d["design"],
                )
            )
        Run.objects.bulk_create(runs)
        if campaign.status == "design":
            campaign.status = "running"
            campaign.save(update_fields=["status", "updated_at"])
        return R(RunSerializer(campaign.runs.all(), many=True).data, status=201)

    @action(detail=True, methods=["get"])
    def analysis(self, request, pk=None):
        """Per-response model, main effects and plain-language findings."""
        c = self.get_object()
        variables, runs = _vars(c), _runs(c)
        return R(
            {
                "responses": [analysis.analyse(variables, resp, runs) for resp in _resps(c)],
                "counts": {s: sum(1 for r in runs if r["status"] == s) for s in RunStatus.values},
            }
        )

    @action(detail=True, methods=["post"])
    def predict(self, request, pk=None):
        """Body: {"response": id, "factors": {var_id: value}}. Flags extrapolation."""
        c = self.get_object()
        resp = next((r for r in _resps(c) if r["id"] == str(request.data.get("response"))), None)
        if not resp:
            raise ValidationError({"response": "Unknown response."})
        try:
            return R(analysis.predict(_vars(c), resp, _runs(c), request.data.get("factors") or {}))
        except ValueError as e:
            raise ValidationError({"detail": str(e)}) from e

    @action(detail=True, methods=["post"])
    def suggest(self, request, pk=None):
        """Next runs to try. Body: {"k": 4, "explore": true, "add": false}"""
        c = self.get_object()
        k = max(1, min(24, int(request.data.get("k", 4))))
        try:
            out = analysis.suggest(
                _vars(c), _resps(c), _runs(c), k=k, explore=bool(request.data.get("explore", True))
            )
        except ValueError as e:
            raise ValidationError({"detail": str(e)}) from e
        if request.data.get("add"):
            if c.group_id not in writable_group_ids(request.user):
                raise PermissionDenied("You cannot change this campaign.")
            start = (c.runs.aggregate(m=Max("index"))["m"] or 0) + 1
            for i, sug in enumerate(out["suggestions"]):
                Run.objects.create(
                    campaign=c,
                    index=start + i,
                    factors=sug["factors"],
                    source="suggestion",
                    notes=("Extrapolation: " + "; ".join(sug["warnings"]))[:500]
                    if sug["extrapolation"]
                    else sug["purpose"],
                )
        return R(out)

    @action(detail=True, methods=["get"], url_path="export")
    def export_csv(self, request, pk=None):
        """Runs as CSV (one column per variable and response): for robots, Excel, Python."""
        c = self.get_object()
        variables, responses = list(c.variables.all()), list(c.responses.all())
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            ["run", "plate", "well", "status"]
            + [f"{v.name} ({v.unit})" if v.unit else v.name for v in variables]
            + [f"{r.name} ({r.unit})" if r.unit else r.name for r in responses]
            + ["notes"]
        )
        for run in c.runs.all():
            w.writerow(
                [run.index, run.plate or "", run.well, run.status]
                + [run.factors.get(str(v.id), "") for v in variables]
                + [run.results.get(str(r.id), "") for r in responses]
                + [run.notes]
            )
        resp = HttpResponse(buf.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="campaign-{c.id}.csv"'
        return resp

    @extend_schema(request=serializers.Serializer)
    @action(detail=True, methods=["post"], url_path="import-results")
    @transaction.atomic
    def import_results(self, request, pk=None):
        """CSV with a 'run' (or 'well') column and one column per response name."""
        c = self._writable()
        f = request.FILES.get("file")
        text = f.read().decode("utf-8-sig") if f else request.data.get("csv", "")
        if not text.strip():
            raise ValidationError({"detail": "Empty file."})
        reader = csv.DictReader(io.StringIO(text), dialect=csv.Sniffer().sniff(text[:2000]))
        resp_by_name = {}
        for r in c.responses.all():
            resp_by_name[r.name.lower()] = r
            if r.unit:
                resp_by_name[f"{r.name} ({r.unit})".lower()] = r
        runs_by_index = {str(r.index): r for r in c.runs.all()}
        runs_by_well = {f"{r.plate or 1}:{r.well}".upper(): r for r in c.runs.all() if r.well}
        updated, errors = 0, []
        for line, row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            run = runs_by_index.get(row.get("run", ""))
            if run is None and row.get("well"):
                run = runs_by_well.get(f"{row.get('plate') or 1}:{row['well']}".upper())
            if run is None:
                errors.append(f"Line {line}: no matching run")
                continue
            changed = False
            for col, val in row.items():
                if col in resp_by_name and val != "":
                    try:
                        run.results[str(resp_by_name[col].id)] = float(val.replace(",", "."))
                        changed = True
                    except ValueError:
                        errors.append(f"Line {line}: {col}={val!r} is not a number")
            if changed:
                run.status = RunStatus.DONE
                run.performed_at = run.performed_at or timezone.now()
                run.save()
                updated += 1
        return R({"updated": updated, "errors": errors})


class _ChildViewSet(viewsets.ModelViewSet):
    permission_classes = [GroupScopedPermission]
    model = None

    def object_group_id(self, obj):
        return obj.campaign.group_id

    def get_queryset(self):
        qs = self.model.objects.select_related("campaign")
        if not self.request.user.is_staff:
            qs = qs.filter(campaign__group__in=visible_group_ids(self.request.user))
        if c := self.request.query_params.get("campaign"):
            qs = qs.filter(campaign=c)
        return qs

    def _check(self, campaign):
        if campaign.group_id not in writable_group_ids(self.request.user):
            raise PermissionDenied("You cannot change this campaign.")

    def perform_create(self, serializer):
        self._check(serializer.validated_data["campaign"])
        serializer.save()

    def perform_update(self, serializer):
        self._check(serializer.instance.campaign)
        serializer.save()

    def perform_destroy(self, instance):
        self._check(instance.campaign)
        instance.delete()


class VariableViewSet(_ChildViewSet):
    serializer_class = VariableSerializer
    model = Variable


class ResponseViewSet(_ChildViewSet):
    serializer_class = ResponseSerializer
    model = Response


class RunViewSet(_ChildViewSet):
    serializer_class = RunSerializer
    model = Run

    def perform_create(self, serializer):
        campaign = serializer.validated_data["campaign"]
        self._check(campaign)
        idx = serializer.validated_data.get("index") or (
            (campaign.runs.aggregate(m=Max("index"))["m"] or 0) + 1
        )
        serializer.save(index=idx, source=serializer.validated_data.get("source", "manual"))

    def perform_update(self, serializer):
        self._check(serializer.instance.campaign)
        run = serializer.save()
        if run.results and run.status in (RunStatus.PLANNED, RunStatus.RUNNING):
            run.status = RunStatus.DONE
        if run.status == RunStatus.DONE and not run.performed_at:
            run.performed_at = timezone.now()
        run.save()
