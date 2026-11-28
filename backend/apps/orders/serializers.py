from rest_framework import serializers

from apps.chemistry.serializers import CompoundSummarySerializer
from apps.orgs.permissions import writable_group_ids

from . import services
from .models import CostCentre, Order, OrderEvent, OrderStatus, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "website",
            "customer_number",
            "contact_email",
            "phone",
            "notes",
            "is_active",
        ]


class CostCentreSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    committed = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, allow_null=True
    )

    class Meta:
        model = CostCentre
        fields = [
            "id",
            "group",
            "group_name",
            "code",
            "name",
            "budget",
            "currency",
            "valid_until",
            "is_active",
            "committed",
            "remaining",
        ]


class OrderEventSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True, default="")

    class Meta:
        model = OrderEvent
        fields = ["id", "user_name", "from_status", "to_status", "note", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    compound_detail = CompoundSummarySerializer(source="compound", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.display_name", read_only=True)
    decided_by_name = serializers.CharField(
        source="decided_by.display_name", read_only=True, default=""
    )
    supplier_display = serializers.SerializerMethodField()
    cost_centre_code = serializers.CharField(source="cost_centre.code", read_only=True, default="")
    total_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, allow_null=True
    )
    display_name = serializers.CharField(read_only=True)
    allowed_actions = serializers.SerializerMethodField()
    container_barcodes = serializers.SlugRelatedField(
        source="containers", many=True, read_only=True, slug_field="barcode"
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "number",
            "group",
            "group_name",
            "requested_by",
            "requested_by_name",
            "status",
            "urgency",
            "compound",
            "compound_detail",
            "item_name",
            "display_name",
            "cas",
            "grade",
            "purity",
            "supplier",
            "supplier_name",
            "supplier_display",
            "catalog_number",
            "package_amount",
            "package_unit",
            "quantity",
            "unit_price",
            "currency",
            "total_price",
            "cost_centre",
            "cost_centre_code",
            "justification",
            "delivery_location",
            "submitted_at",
            "decided_by_name",
            "decided_at",
            "rejection_reason",
            "ordered_at",
            "po_number",
            "expected_date",
            "received_quantity",
            "received_at",
            "container_barcodes",
            "allowed_actions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "requested_by",
            "status",
            "submitted_at",
            "decided_at",
            "rejection_reason",
            "ordered_at",
            "received_quantity",
            "received_at",
        ]

    def get_supplier_display(self, order) -> str:
        return order.supplier.name if order.supplier else order.supplier_name

    def get_allowed_actions(self, order) -> list[str]:
        return services.allowed_actions(self.context["request"].user, order)

    def validate_group(self, group):
        if group.id not in writable_group_ids(self.context["request"].user):
            raise serializers.ValidationError("You can only order for groups you are a member of.")
        return group

    def validate(self, attrs):
        if self.instance and self.instance.status not in (OrderStatus.DRAFT, OrderStatus.REJECTED):
            # After submission only purchasing details may change (via the workflow actions),
            # except linking the compound, which receiving needs.
            allowed = {"compound", "po_number", "expected_date", "delivery_location"}
            changed = set(attrs) - allowed
            if changed:
                raise serializers.ValidationError(
                    f"Submitted orders cannot be edited ({', '.join(sorted(changed))})."
                )
        compound = attrs.get("compound", getattr(self.instance, "compound", None))
        item = attrs.get("item_name", getattr(self.instance, "item_name", ""))
        if not compound and not item:
            raise serializers.ValidationError("Choose a compound or describe the item.")
        cc = attrs.get("cost_centre")
        group = attrs.get("group", getattr(self.instance, "group", None))
        if cc and group and cc.group_id != group.id:
            raise serializers.ValidationError({"cost_centre": "Belongs to another group."})
        return attrs


class TransitionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=list(services.TRANSITIONS))
    note = serializers.CharField(required=False, allow_blank=True, default="")
    po_number = serializers.CharField(required=False, allow_blank=True)
    expected_date = serializers.DateField(required=False, allow_null=True)
    override_budget = serializers.BooleanField(required=False, default=False)


class ReceiveSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    location = serializers.UUIDField(required=False, allow_null=True)
    lot_number = serializers.CharField(required=False, allow_blank=True, default="")
    expiry_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")
