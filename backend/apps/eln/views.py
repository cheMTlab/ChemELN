from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.inventory.serializers import ContainerSerializer
from apps.locations.models import Location
from apps.orgs.permissions import GroupScopedPermission, visible_group_ids, writable_group_ids

from . import services
from .models import (
    Attachment,
    Comment,
    ComponentRole,
    Experiment,
    ExperimentTemplate,
    Project,
    ReactionComponent,
)
from .serializers import (
    AttachmentSerializer,
    CommentSerializer,
    ComponentSerializer,
    ExperimentListSerializer,
    ExperimentSerializer,
    ProjectSerializer,
    SignatureSerializer,
    TemplateSerializer,
)


def _err(fn):
    try:
        return fn()
    except services.ElnError as e:
        raise ValidationError({"detail": str(e)}) from e


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [GroupScopedPermission]

    def get_queryset(self):
        qs = Project.objects.select_related("group").annotate(experiment_count=Count("experiments"))
        if not self.request.user.is_staff:
            qs = qs.filter(group__in=visible_group_ids(self.request.user))
        if group := self.request.query_params.get("group"):
            qs = qs.filter(group=group)
        if status := self.request.query_params.get("status"):
            qs = qs.filter(status=status)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    permission_classes = [GroupScopedPermission]

    def object_group_id(self, obj):
        return obj.group_id

    def get_queryset(self):
        return ExperimentTemplate.objects.filter(
            Q(group__isnull=True) | Q(group__in=visible_group_ids(self.request.user))
        )


@extend_schema(
    parameters=[
        OpenApiParameter("q", str, description="Code, title, tag or text"),
        OpenApiParameter("project", str),
        OpenApiParameter("group", str),
        OpenApiParameter("status", str),
        OpenApiParameter("kind", str),
        OpenApiParameter("mine", bool),
        OpenApiParameter("compound", str, description="Experiments using this compound"),
    ]
)
class ExperimentViewSet(viewsets.ModelViewSet):
    """Notebook entries. Group members write; viewers read. Signed entries are read-only."""

    permission_classes = [GroupScopedPermission]

    def get_serializer_class(self):
        return ExperimentListSerializer if self.action == "list" else ExperimentSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Experiment.objects.select_related(
            "owner", "project", "group", "signed_by", "witnessed_by"
        )
        if not user.is_staff:
            qs = qs.filter(group__in=visible_group_ids(user))
        if self.action == "list":
            p = self.request.query_params
            qs = qs.annotate(
                best_yield=Max(
                    "components__yield_percent",
                    filter=Q(components__role=ComponentRole.PRODUCT),
                )
            )
            if q := p.get("q"):
                qs = qs.filter(
                    Q(code__icontains=q)
                    | Q(title__icontains=q)
                    | Q(procedure__icontains=q)
                    | Q(observations__icontains=q)
                    | Q(tags__icontains=q)
                    | Q(components__name__icontains=q)
                ).distinct()
            for field in ("project", "group", "status", "kind"):
                if v := p.get(field):
                    qs = qs.filter(**{field: v})
            if p.get("mine") in ("1", "true"):
                qs = qs.filter(owner=user)
            if compound := p.get("compound"):
                qs = qs.filter(components__compound=compound).distinct()
            qs = qs.order_by("-created_at")
        else:
            qs = qs.prefetch_related(
                "components__container",
                "components__registered_container",
                "attachments__uploaded_by",
                "comments__author",
                "signatures__user",
            )
        return qs

    def perform_create(self, serializer):
        exp = serializer.save(owner=self.request.user)
        tpl = exp.template
        if tpl:
            exp.aim = exp.aim or tpl.aim
            exp.procedure = exp.procedure or tpl.procedure
            exp.save()
            for i, row in enumerate(tpl.components or []):
                ReactionComponent.objects.create(
                    experiment=exp,
                    position=i + 1,
                    **{
                        k: v
                        for k, v in row.items()
                        if k
                        in {"role", "name", "smiles", "mw", "density", "equivalents", "molarity"}
                    },
                )

    def perform_destroy(self, exp):
        if exp.is_locked:
            raise ValidationError("Signed experiments cannot be deleted.")
        if exp.owner_id != self.request.user.id and not self.request.user.is_staff:
            raise PermissionDenied("Only the author can delete a draft experiment.")
        exp.delete()

    def _writable(self) -> Experiment:
        exp = self.get_object()
        if exp.group_id not in writable_group_ids(self.request.user):
            raise PermissionDenied("You cannot change this experiment.")
        return exp

    def _unlocked(self) -> Experiment:
        exp = self._writable()
        if exp.is_locked:
            raise ValidationError({"detail": "Signed experiments cannot be changed."})
        return exp

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        exp = self._unlocked()
        services.recalculate(exp)
        return Response(ComponentSerializer(exp.components.all(), many=True).data)

    @extend_schema(request=serializers.Serializer)
    @action(detail=True, methods=["post"], url_path="import-reaction")
    def import_reaction(self, request, pk=None):
        """Body: {"reaction": "<RXN or reaction SMILES>", "replace": true}"""
        exp = self._unlocked()
        _err(
            lambda: services.import_reaction(
                exp, request.data.get("reaction", ""), bool(request.data.get("replace", True))
            )
        )
        services.recalculate(exp)
        exp.refresh_from_db()
        return Response(ExperimentSerializer(exp, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="deduct-inventory")
    def deduct_inventory(self, request, pk=None):
        exp = self._writable()
        used = _err(lambda: services.deduct_inventory(exp, request.user))
        return Response({"containers": used})

    @action(detail=True, methods=["post"])
    def sign(self, request, pk=None):
        exp = self._writable()
        sig = _err(lambda: services.sign(exp, request.user, request.data.get("meaning", "")))
        return Response(SignatureSerializer(sig).data, status=201)

    @action(detail=True, methods=["post"])
    def witness(self, request, pk=None):
        exp = self.get_object()
        sig = _err(lambda: services.witness(exp, request.user, request.data.get("meaning", "")))
        return Response(SignatureSerializer(sig).data, status=201)

    @action(detail=True, methods=["get"])
    def verify(self, request, pk=None):
        return Response(services.verify_experiment(self.get_object()))

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """New draft with the same reaction and procedure (repeat or scale-up)."""
        src = self.get_object()
        if src.group_id not in writable_group_ids(request.user):
            raise PermissionDenied("You are not a member of this group.")
        copy = Experiment.objects.create(
            group=src.group,
            project=src.project,
            owner=request.user,
            title=f"{src.title} (repeat)",
            kind=src.kind,
            aim=src.aim,
            procedure=src.procedure,
            reaction_rxn=src.reaction_rxn,
            reaction_smiles=src.reaction_smiles,
            temperature=src.temperature,
            duration=src.duration,
            atmosphere=src.atmosphere,
            solvent=src.solvent,
            workup=src.workup,
            tags=src.tags,
        )
        copy.references.add(src)
        for c in src.components.all():
            ReactionComponent.objects.create(
                experiment=copy,
                role=c.role,
                position=c.position,
                compound=c.compound,
                name=c.name,
                smiles=c.smiles,
                mw=c.mw,
                density=c.density,
                purity=c.purity,
                molarity=c.molarity,
                equivalents=c.equivalents,
                is_limiting=c.is_limiting,
                mmol=c.mmol if c.is_limiting else None,
                mass_mg=c.mass_mg if c.is_limiting else None,
            )
        services.recalculate(copy)
        return Response(ExperimentSerializer(copy, context={"request": request}).data, status=201)


class ComponentViewSet(viewsets.ModelViewSet):
    serializer_class = ComponentSerializer
    permission_classes = [GroupScopedPermission]

    def object_group_id(self, obj):
        return obj.experiment.group_id

    def get_queryset(self):
        qs = ReactionComponent.objects.select_related("experiment", "container", "compound")
        if not self.request.user.is_staff:
            qs = qs.filter(experiment__group__in=visible_group_ids(self.request.user))
        if exp := self.request.query_params.get("experiment"):
            qs = qs.filter(experiment=exp)
        return qs

    def _check(self, exp: Experiment):
        if exp.group_id not in writable_group_ids(self.request.user):
            raise PermissionDenied("You cannot change this experiment.")
        if exp.is_locked:
            raise ValidationError({"detail": "Signed experiments cannot be changed."})

    def _save(self, serializer):
        exp = serializer.validated_data.get("experiment") or serializer.instance.experiment
        self._check(exp)
        comp = serializer.save()
        services.fill_from_compound(comp)
        if comp.is_limiting:
            exp.components.exclude(pk=comp.pk).update(is_limiting=False)
        comp.save()
        services.recalculate(exp)

    perform_create = _save
    perform_update = _save

    def perform_destroy(self, comp):
        self._check(comp.experiment)
        exp = comp.experiment
        comp.delete()
        services.recalculate(exp)

    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        """Put the isolated product into the inventory as a new container."""
        comp = self.get_object()
        if comp.experiment.group_id not in writable_group_ids(request.user):
            raise PermissionDenied("You cannot change this experiment.")
        loc = request.data.get("location")
        location = get_object_or_404(Location, pk=loc) if loc else None
        container = _err(
            lambda: services.register_product(
                comp,
                request.user,
                name=request.data.get("name", ""),
                location=location,
                amount_mg=request.data.get("amount_mg"),
            )
        )
        return Response(ContainerSerializer(container).data, status=201)


class AttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = AttachmentSerializer
    permission_classes = [GroupScopedPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def object_group_id(self, obj):
        return obj.experiment.group_id

    def get_queryset(self):
        qs = Attachment.objects.select_related("experiment", "uploaded_by")
        if not self.request.user.is_staff:
            qs = qs.filter(experiment__group__in=visible_group_ids(self.request.user))
        if exp := self.request.query_params.get("experiment"):
            qs = qs.filter(experiment=exp)
        return qs

    def perform_create(self, serializer):
        exp = serializer.validated_data["experiment"]
        if exp.group_id not in writable_group_ids(self.request.user):
            raise PermissionDenied("You cannot change this experiment.")
        if exp.is_locked:
            raise ValidationError({"detail": "Signed experiments cannot get new attachments."})
        f = serializer.validated_data["file"]
        serializer.save(uploaded_by=self.request.user, name=f.name)

    def perform_destroy(self, att):
        if att.experiment.is_locked:
            raise ValidationError({"detail": "Attachments of signed experiments are permanent."})
        att.delete()


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [GroupScopedPermission]
    http_method_names = ["get", "post", "head", "options"]

    def object_group_id(self, obj):
        return obj.experiment.group_id

    def get_queryset(self):
        qs = Comment.objects.select_related("author")
        if not self.request.user.is_staff:
            qs = qs.filter(experiment__group__in=visible_group_ids(self.request.user))
        if exp := self.request.query_params.get("experiment"):
            qs = qs.filter(experiment=exp)
        return qs

    def perform_create(self, serializer):
        exp = serializer.validated_data["experiment"]
        if exp.group_id not in visible_group_ids(self.request.user):
            raise PermissionDenied("You cannot comment on this experiment.")
        serializer.save(author=self.request.user, is_addendum=exp.is_locked)


@api_view(["GET"])
def ledger_status(request):
    """Integrity check of the whole signature chain."""
    return Response(services.verify_ledger())
