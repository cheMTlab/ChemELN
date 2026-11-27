from decimal import Decimal

from rest_framework import serializers

from apps.chemistry.serializers import CompoundSummarySerializer
from apps.locations.models import Location
from apps.orgs.permissions import writable_group_ids

from .models import Container, ContainerEvent, ContainerStatus
from .units import Unit


class ContainerSerializer(serializers.ModelSerializer):
    compound_detail = CompoundSummarySerializer(source="compound", read_only=True)
    location_path = serializers.CharField(source="location.path", read_only=True, default="")
    group_name = serializers.CharField(source="group.name", read_only=True)
    owner_name = serializers.CharField(source="owner.display_name", read_only=True, default="")
    is_expired = serializers.BooleanField(read_only=True)
    fraction_remaining = serializers.FloatField(read_only=True)
    storage_warning = serializers.CharField(read_only=True)

    class Meta:
        model = Container
        fields = [
            "id",
            "barcode",
            "compound",
            "compound_detail",
            "group",
            "group_name",
            "owner",
            "owner_name",
            "location",
            "location_path",
            "status",
            "amount",
            "initial_amount",
            "unit",
            "purity",
            "concentration",
            "grade",
            "supplier",
            "catalog_number",
            "lot_number",
            "price",
            "currency",
            "received_date",
            "opened_date",
            "expiry_date",
            "notes",
            "is_expired",
            "fraction_remaining",
            "storage_warning",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "barcode": {"required": False},
            "initial_amount": {"required": False},
            "owner": {"required": False},
        }

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Amount cannot be negative.")
        return value

    def validate_group(self, group):
        if group.id not in writable_group_ids(self.context["request"].user):
            raise serializers.ValidationError("You are not a member of this group.")
        return group


class MoveSerializer(serializers.Serializer):
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(), allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class UseSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"))
    unit = serializers.ChoiceField(choices=Unit.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AdjustSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"))
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ContainerStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ContainerEventSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True, default="")
    from_path = serializers.CharField(source="from_location.path", read_only=True, default="")
    to_path = serializers.CharField(source="to_location.path", read_only=True, default="")

    class Meta:
        model = ContainerEvent
        fields = [
            "id",
            "kind",
            "user_name",
            "amount_change",
            "from_path",
            "to_path",
            "note",
            "created_at",
        ]
