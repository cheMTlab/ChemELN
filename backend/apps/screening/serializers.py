from rest_framework import serializers

from apps.orgs.permissions import writable_group_ids

from .design import GENERATORS
from .models import Campaign, Response, Run, Variable


class VariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variable
        fields = ["id", "campaign", "name", "kind", "unit", "low", "high", "levels", "position"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        low = attrs.get("low", getattr(self.instance, "low", None))
        high = attrs.get("high", getattr(self.instance, "high", None))
        levels = attrs.get("levels", getattr(self.instance, "levels", []))
        if kind == "continuous":
            if low is None or high is None or low >= high:
                raise serializers.ValidationError("Continuous variables need low < high.")
        elif not levels:
            raise serializers.ValidationError("Give at least one level.")
        elif kind == "discrete":
            try:
                [float(x["value"] if isinstance(x, dict) else x) for x in levels]
            except (TypeError, ValueError) as e:
                raise serializers.ValidationError("Discrete levels must be numbers.") from e
        return attrs


class ResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ["id", "campaign", "name", "unit", "goal", "target", "weight", "position"]


class RunSerializer(serializers.ModelSerializer):
    experiment_code = serializers.CharField(source="experiment.code", read_only=True, default="")

    class Meta:
        model = Run
        fields = [
            "id",
            "campaign",
            "index",
            "label",
            "plate",
            "well",
            "factors",
            "results",
            "status",
            "failure_reason",
            "source",
            "experiment",
            "experiment_code",
            "lots",
            "notes",
            "performed_at",
        ]
        extra_kwargs = {"index": {"required": False}}


class CampaignSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    variables = VariableSerializer(many=True, read_only=True)
    responses = ResponseSerializer(many=True, read_only=True)
    run_count = serializers.IntegerField(read_only=True, default=None)
    done_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "group",
            "group_name",
            "project",
            "owner",
            "owner_name",
            "title",
            "objective",
            "reaction_smiles",
            "reaction_rxn",
            "equipment",
            "plate_format",
            "status",
            "notes",
            "variables",
            "responses",
            "run_count",
            "done_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["owner"]

    def validate_group(self, group):
        if group.id not in writable_group_ids(self.context["request"].user):
            raise serializers.ValidationError("You are not a member of this group.")
        return group

    def validate_plate_format(self, value):
        from .design import PLATE_SHAPES

        if value not in PLATE_SHAPES:
            raise serializers.ValidationError(f"Choose one of {sorted(PLATE_SHAPES)}.")
        return value


class GenerateSerializer(serializers.Serializer):
    design = serializers.ChoiceField(choices=list(GENERATORS))
    n = serializers.IntegerField(required=False, default=12, min_value=1)
    levels = serializers.IntegerField(required=False, default=3, min_value=2, max_value=11)
    seed = serializers.IntegerField(required=False, allow_null=True, default=None)
    replace = serializers.BooleanField(required=False, default=False)
    randomize_order = serializers.BooleanField(required=False, default=True)
