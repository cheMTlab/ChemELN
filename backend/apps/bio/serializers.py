from rest_framework import serializers

from apps.orgs.permissions import writable_group_ids

from . import sequence
from .models import Assay, BioSample, Measurement, Oligo, Plasmid, Plate, Strain, Well


class GroupWritable(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)

    def validate_group(self, group):
        if group.id not in writable_group_ids(self.context["request"].user):
            raise serializers.ValidationError("You are not a member of this group.")
        return group


class SequenceField(serializers.CharField):
    def __init__(self, allow_n=True, **kw):
        self.allow_n = allow_n
        super().__init__(**kw)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return sequence.clean(value, allow_n=self.allow_n)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e


class PlasmidListSerializer(GroupWritable):
    class Meta:
        model = Plasmid
        fields = [
            "id",
            "code",
            "name",
            "alias",
            "group",
            "group_name",
            "backbone",
            "insert",
            "vector_type",
            "resistance",
            "promoter",
            "tags",
            "size_bp",
            "verified",
            "source",
            "addgene_id",
            "created_at",
        ]


class PlasmidSerializer(GroupWritable):
    sequence = SequenceField(required=False, allow_blank=True)
    strain_count = serializers.IntegerField(source="strains.count", read_only=True)
    sample_count = serializers.IntegerField(source="samples.count", read_only=True)
    parent_code = serializers.CharField(source="parent.code", read_only=True, default="")

    class Meta:
        model = Plasmid
        fields = [
            "id",
            "code",
            "name",
            "alias",
            "group",
            "group_name",
            "backbone",
            "insert",
            "insert_species",
            "vector_type",
            "resistance",
            "origin",
            "promoter",
            "tags",
            "copy_number",
            "growth_temperature",
            "sequence",
            "features",
            "circular",
            "size_bp",
            "gc_content",
            "source",
            "addgene_id",
            "parent",
            "parent_code",
            "verified",
            "notes",
            "strain_count",
            "sample_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["gc_content"]


class StrainSerializer(GroupWritable):
    plasmid_codes = serializers.SlugRelatedField(
        source="plasmids", many=True, read_only=True, slug_field="code"
    )

    class Meta:
        model = Strain
        fields = [
            "id",
            "code",
            "name",
            "kind",
            "group",
            "group_name",
            "organism",
            "genotype",
            "parent",
            "plasmids",
            "plasmid_codes",
            "resistance",
            "biosafety_level",
            "is_gmo",
            "growth_conditions",
            "tissue",
            "passage",
            "mycoplasma_tested_on",
            "source",
            "notes",
            "created_at",
        ]


class OligoSerializer(GroupWritable):
    sequence = SequenceField()
    reverse_complement = serializers.SerializerMethodField()

    class Meta:
        model = Oligo
        fields = [
            "id",
            "code",
            "name",
            "group",
            "group_name",
            "sequence",
            "reverse_complement",
            "purpose",
            "target",
            "modifications",
            "scale",
            "purification",
            "supplier",
            "tm",
            "gc_content",
            "plasmid",
            "notes",
            "created_at",
        ]
        read_only_fields = ["tm", "gc_content"]

    def get_reverse_complement(self, o) -> str:
        return sequence.reverse_complement(o.sequence)


class BioSampleSerializer(GroupWritable):
    location_path = serializers.CharField(source="location.path", read_only=True, default="")
    plasmid_code = serializers.CharField(source="plasmid.code", read_only=True, default="")
    strain_code = serializers.CharField(source="strain.code", read_only=True, default="")

    class Meta:
        model = BioSample
        fields = [
            "id",
            "barcode",
            "group",
            "group_name",
            "kind",
            "name",
            "plasmid",
            "plasmid_code",
            "strain",
            "strain_code",
            "location",
            "location_path",
            "box_position",
            "concentration",
            "concentration_unit",
            "volume_ul",
            "passage",
            "prepared_on",
            "prepared_by",
            "is_available",
            "notes",
            "created_at",
        ]
        extra_kwargs = {"barcode": {"required": False}}


class AssaySerializer(GroupWritable):
    class Meta:
        model = Assay
        fields = [
            "id",
            "group",
            "group_name",
            "name",
            "readout",
            "wavelength",
            "unit",
            "target",
            "higher_is_active",
            "protocol",
        ]


class WellSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    compound_name = serializers.CharField(source="compound.name", read_only=True, default="")
    strain_code = serializers.CharField(source="strain.code", read_only=True, default="")
    plasmid_code = serializers.CharField(source="plasmid.code", read_only=True, default="")

    class Meta:
        model = Well
        fields = [
            "id",
            "name",
            "row",
            "col",
            "role",
            "label",
            "compound",
            "compound_name",
            "strain",
            "strain_code",
            "plasmid",
            "plasmid_code",
            "sample",
            "concentration",
            "concentration_unit",
            "volume_ul",
            "replicate",
            "group_label",
            "excluded",
            "metadata",
        ]
        read_only_fields = ["row", "col"]


class PlateSerializer(GroupWritable):
    assay_name = serializers.CharField(source="assay.name", read_only=True, default="")
    experiment_code = serializers.CharField(source="experiment.code", read_only=True, default="")
    rows = serializers.SerializerMethodField()
    cols = serializers.SerializerMethodField()
    measurement_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Plate
        fields = [
            "id",
            "barcode",
            "group",
            "group_name",
            "name",
            "kind",
            "format",
            "assay",
            "assay_name",
            "experiment",
            "experiment_code",
            "location",
            "template",
            "notes",
            "rows",
            "cols",
            "measurement_count",
            "created_at",
        ]
        extra_kwargs = {"barcode": {"required": False}}

    def get_rows(self, p) -> int:
        return p.shape[0]

    def get_cols(self, p) -> int:
        return p.shape[1]

    def validate_format(self, v):
        from .models import PLATE_FORMATS

        if v not in PLATE_FORMATS:
            raise serializers.ValidationError(f"Choose one of {sorted(PLATE_FORMATS)}.")
        if self.instance and self.instance.format != v:
            raise serializers.ValidationError("The format of an existing plate cannot change.")
        return v


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measurement
        fields = ["id", "well", "channel", "timepoint", "value"]
