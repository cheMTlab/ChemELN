from django.db.models import Count
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.orgs.permissions import IsContributorOrReadOnly

from . import pubchem, rdkit_utils, search
from .models import Compound, SafetyDataSheet
from .serializers import CompoundSerializer, SafetyDataSheetSerializer

SEARCH_PARAMS = [
    OpenApiParameter("q", str, description="Name, synonym, CAS, formula or InChIKey"),
    OpenApiParameter("substructure", str, description="SMILES, SMARTS or molfile"),
    OpenApiParameter("similar", str, description="SMILES or molfile"),
    OpenApiParameter("threshold", float, description="Tanimoto threshold (default 0.5)"),
]


def apply_structure_search(qs, params, context: dict):
    """Shared by compound and container search. Returns a filtered Compound queryset."""
    try:
        if q := params.get("q"):
            qs = search.text_filter(qs, q)
        if sub := params.get("substructure"):
            qs = search.substructure_filter(qs, sub)
        if sim := params.get("similar"):
            scores = search.similarity_scores(qs, sim, _threshold(params))
            context["similarity"] = scores
            qs = qs.filter(id__in=list(scores))
    except rdkit_utils.InvalidStructure as exc:
        raise ValidationError({"structure": str(exc)}) from exc
    return qs


def _threshold(params) -> float:
    try:
        value = float(params.get("threshold", 0.5))
    except ValueError:
        value = -1
    if not 0 <= value <= 1:
        raise ValidationError({"threshold": "Must be a number between 0 and 1"})
    return value


@extend_schema(parameters=SEARCH_PARAMS)
class CompoundViewSet(viewsets.ModelViewSet):
    serializer_class = CompoundSerializer
    permission_classes = [IsContributorOrReadOnly]
    _search_context: dict

    def get_queryset(self):
        self._search_context = {}
        qs = Compound.objects.prefetch_related("sds").annotate(container_count=Count("containers"))
        if self.action == "list":
            qs = apply_structure_search(qs, self.request.query_params, self._search_context)
        return qs.order_by("name", "id")

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        scores = self._search_context.get("similarity")
        if scores:  # best match first, unpaginated (already capped)
            items = sorted(qs, key=lambda c: -scores[c.id])
            data = self.get_serializer(items, many=True).data
            return Response({"count": len(data), "next": None, "previous": None, "results": data})
        return super().list(request, *args, **kwargs)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx.update(getattr(self, "_search_context", {}))
        return ctx

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied("Only administrators can delete compounds.")
        if instance.containers.exists():
            raise ValidationError("This compound still has containers.")
        instance.delete()

    @extend_schema(responses={(200, "image/svg+xml"): str})
    @action(detail=True, methods=["get"])
    def depict(self, request, pk=None):
        compound = self.get_object()
        if not compound.smiles:
            return HttpResponse(status=204)
        svg = rdkit_utils.to_svg(compound.molfile or compound.smiles)
        res = HttpResponse(svg, content_type="image/svg+xml")
        res["Cache-Control"] = "private, max-age=3600"
        return res

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str, required=True),
            OpenApiParameter("kind", str, enum=["auto", "name", "cas", "smiles"]),
        ]
    )
    @action(detail=False, methods=["get"])
    def lookup(self, request):
        """Pre-fill data from PubChem (only when the administrator enabled external lookups)."""
        q = request.query_params.get("q", "").strip()
        if not q:
            raise ValidationError({"q": "Required"})
        try:
            data = pubchem.lookup(q, request.query_params.get("kind", "auto"))
        except pubchem.LookupDisabled:
            return Response(
                {"detail": "External lookups are disabled on this instance."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except pubchem.NotFound:
            return Response({"detail": "Not found in PubChem."}, status=404)
        except OSError:
            return Response({"detail": "PubChem could not be reached."}, status=502)
        existing = None
        if data.get("inchikey"):
            existing = Compound.objects.filter(inchikey=data["inchikey"]).first()
        data["existing_id"] = str(existing.id) if existing else None
        return Response(data)


class SafetyDataSheetViewSet(viewsets.ModelViewSet):
    queryset = SafetyDataSheet.objects.all()
    serializer_class = SafetyDataSheetSerializer
    permission_classes = [IsContributorOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]


class StructureInput(serializers.Serializer):
    structure = serializers.CharField()


@extend_schema(
    request=StructureInput,
    responses=serializers.DictField(),
    description="Calculate formula, MW, InChIKey and an SVG drawing (for live form previews).",
)
@api_view(["POST"])
def analyse_structure(request):
    ser = StructureInput(data=request.data)
    ser.is_valid(raise_exception=True)
    try:
        info = rdkit_utils.analyse(ser.validated_data["structure"])
    except rdkit_utils.InvalidStructure as exc:
        raise ValidationError({"structure": str(exc)}) from exc
    existing = Compound.objects.filter(inchikey=info.inchikey).first() if info.inchikey else None
    return Response(
        {
            "smiles": info.smiles,
            "inchikey": info.inchikey,
            "formula": info.formula,
            "mw": info.mw,
            "exact_mass": info.exact_mass,
            "svg": rdkit_utils.to_svg(info.molfile),
            "existing_id": str(existing.id) if existing else None,
        }
    )
