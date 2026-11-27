from rest_framework import serializers

from . import rdkit_utils
from .models import Compound, SafetyDataSheet
from .safety import GHS_PICTOGRAMS, suggest_storage_class


class SafetyDataSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetyDataSheet
        fields = [
            "id",
            "compound",
            "supplier",
            "language",
            "revision_date",
            "file",
            "url",
            "sha256",
        ]
        read_only_fields = ["sha256"]


class CompoundSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Compound
        fields = [
            "id",
            "name",
            "cas",
            "formula",
            "mw",
            "smiles",
            "signal_word",
            "ghs_pictograms",
            "storage_class",
        ]


class CompoundSerializer(serializers.ModelSerializer):
    structure = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="SMILES or MDL molfile. Formula, MW and InChIKey are calculated from it.",
    )
    similarity = serializers.SerializerMethodField()
    container_count = serializers.IntegerField(read_only=True, required=False)
    sds = SafetyDataSheetSerializer(many=True, read_only=True)

    class Meta:
        model = Compound
        fields = [
            "id",
            "name",
            "synonyms",
            "cas",
            "structure",
            "smiles",
            "molfile",
            "inchi",
            "inchikey",
            "formula",
            "mw",
            "exact_mass",
            "density",
            "signal_word",
            "ghs_pictograms",
            "h_statements",
            "p_statements",
            "storage_class",
            "is_peroxide_former",
            "is_controlled",
            "pubchem_cid",
            "notes",
            "similarity",
            "container_count",
            "sds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "smiles",
            "molfile",
            "inchi",
            "inchikey",
            "formula",
            "mw",
            "exact_mass",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"storage_class": {"required": False}}

    def get_similarity(self, obj) -> float | None:
        scores = self.context.get("similarity")
        return round(scores[obj.id], 3) if scores and obj.id in scores else None

    def validate_ghs_pictograms(self, value):
        unknown = [p for p in value if p not in GHS_PICTOGRAMS]
        if unknown:
            raise serializers.ValidationError(f"Unknown pictogram(s): {', '.join(unknown)}")
        return value

    def validate(self, attrs):
        structure = attrs.pop("structure", None)
        instance = self.instance or Compound()
        if structure is not None:
            try:
                instance.set_structure(structure)
            except rdkit_utils.InvalidStructure as exc:
                raise serializers.ValidationError({"structure": str(exc)}) from exc
            if instance.inchikey:
                dup = Compound.objects.filter(inchikey=instance.inchikey).exclude(pk=instance.pk)
                if existing := dup.first():
                    raise serializers.ValidationError(
                        {
                            "structure": f"This compound already exists: {existing.name}",
                            "existing_id": str(existing.id),
                        }
                    )
            for field in ("smiles", "molfile", "inchi", "inchikey", "formula", "mw", "exact_mass"):
                attrs[field] = getattr(instance, field)
        if "storage_class" not in attrs and not self.instance and attrs.get("h_statements"):
            attrs["storage_class"] = suggest_storage_class(attrs["h_statements"])
        return attrs
