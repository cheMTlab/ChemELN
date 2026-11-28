from rest_framework import serializers

from apps.orgs.permissions import writable_group_ids

from .models import (
    Attachment,
    Comment,
    Experiment,
    ExperimentTemplate,
    Project,
    ReactionComponent,
    Signature,
)


class GroupWritableMixin:
    def validate_group(self, group):
        if group.id not in writable_group_ids(self.context["request"].user):
            raise serializers.ValidationError("You are not a member of this group.")
        return group


class ProjectSerializer(GroupWritableMixin, serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    experiment_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Project
        fields = [
            "id",
            "group",
            "group_name",
            "name",
            "code",
            "description",
            "status",
            "experiment_count",
            "created_at",
        ]


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentTemplate
        fields = ["id", "group", "name", "kind", "aim", "procedure", "components"]


class ComponentSerializer(serializers.ModelSerializer):
    container_barcode = serializers.CharField(
        source="container.barcode", read_only=True, default=""
    )
    container_left = serializers.SerializerMethodField()
    registered_barcode = serializers.CharField(
        source="registered_container.barcode", read_only=True, default=""
    )

    class Meta:
        model = ReactionComponent
        fields = [
            "id",
            "experiment",
            "role",
            "position",
            "compound",
            "container",
            "container_barcode",
            "container_left",
            "name",
            "smiles",
            "mw",
            "density",
            "purity",
            "molarity",
            "equivalents",
            "is_limiting",
            "mmol",
            "mass_mg",
            "volume_ml",
            "actual_mass_mg",
            "product_purity",
            "yield_percent",
            "registered_container",
            "registered_barcode",
            "consumed",
            "notes",
        ]
        read_only_fields = ["yield_percent", "registered_container", "consumed"]

    def get_container_left(self, c) -> str:
        return f"{c.container.amount.normalize()} {c.container.unit}" if c.container else ""


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.display_name", read_only=True, default=""
    )

    class Meta:
        model = Attachment
        fields = [
            "id",
            "experiment",
            "file",
            "name",
            "kind",
            "description",
            "size",
            "sha256",
            "uploaded_by_name",
            "created_at",
        ]
        read_only_fields = ["size", "sha256", "name"]


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "experiment", "author_name", "text", "is_addendum", "created_at"]
        read_only_fields = ["is_addendum"]


class SignatureSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = Signature
        fields = ["id", "kind", "user_name", "meaning", "content_hash", "hash", "seq", "created_at"]


class ExperimentListSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True, default="")
    group_name = serializers.CharField(source="group.name", read_only=True)
    is_locked = serializers.BooleanField(read_only=True)
    best_yield = serializers.FloatField(read_only=True, default=None)

    class Meta:
        model = Experiment
        fields = [
            "id",
            "code",
            "title",
            "kind",
            "status",
            "tags",
            "group",
            "group_name",
            "project",
            "project_name",
            "owner",
            "owner_name",
            "reaction_smiles",
            "started_on",
            "completed_on",
            "is_locked",
            "signed_at",
            "witnessed_at",
            "best_yield",
            "created_at",
            "updated_at",
        ]


LOCK_EXEMPT = {"status", "tags", "completed_on", "project"}


class ExperimentSerializer(GroupWritableMixin, serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True, default="")
    group_name = serializers.CharField(source="group.name", read_only=True)
    signed_by_name = serializers.CharField(
        source="signed_by.display_name", read_only=True, default=""
    )
    witnessed_by_name = serializers.CharField(
        source="witnessed_by.display_name", read_only=True, default=""
    )
    is_locked = serializers.BooleanField(read_only=True)
    components = ComponentSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    signatures = SignatureSerializer(many=True, read_only=True)

    class Meta:
        model = Experiment
        fields = [
            "id",
            "code",
            "title",
            "kind",
            "status",
            "tags",
            "group",
            "group_name",
            "project",
            "project_name",
            "owner",
            "owner_name",
            "template",
            "aim",
            "procedure",
            "observations",
            "conclusion",
            "reaction_rxn",
            "reaction_smiles",
            "temperature",
            "duration",
            "atmosphere",
            "solvent",
            "workup",
            "started_on",
            "completed_on",
            "inventory_deducted",
            "is_locked",
            "signed_by_name",
            "signed_at",
            "witnessed_by_name",
            "witnessed_at",
            "components",
            "attachments",
            "comments",
            "signatures",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "code",
            "owner",
            "inventory_deducted",
            "signed_at",
            "witnessed_at",
        ]

    def validate(self, attrs):
        if self.instance and self.instance.is_locked:
            blocked = set(attrs) - LOCK_EXEMPT
            if blocked:
                raise serializers.ValidationError(
                    "Signed experiments cannot be changed. Add a comment (addendum) instead."
                )
        project = attrs.get("project")
        group = attrs.get("group", getattr(self.instance, "group", None))
        if project and group and project.group_id != group.id:
            raise serializers.ValidationError({"project": "Belongs to another group."})
        return attrs
