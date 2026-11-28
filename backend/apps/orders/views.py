from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import Capability
from apps.inventory.models import Container
from apps.inventory.serializers import ContainerSerializer
from apps.locations.models import Location
from apps.orgs.models import Role
from apps.orgs.permissions import group_ids_with_role, has_group_role, visible_group_ids

from . import services
from .models import CostCentre, Order, OrderStatus, Supplier
from .serializers import (
    CostCentreSerializer,
    OrderEventSerializer,
    OrderSerializer,
    ReceiveSerializer,
    SupplierSerializer,
    TransitionSerializer,
)


def sees_all_orders(user) -> bool:
    return any(user.has_capability(c) for c in (Capability.PURCHASING, Capability.ORDER_APPROVER))


class PurchasingOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.has_capability(Capability.PURCHASING) or bool(
            group_ids_with_role(request.user, Role.PI)
        )


class SupplierViewSet(viewsets.ModelViewSet):
    """Supplier list (everyone reads; purchasing staff and PIs maintain it)."""

    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [PurchasingOrReadOnly]


class CostCentreViewSet(viewsets.ModelViewSet):
    """Budgets. Group members see their group's; PIs manage them."""

    serializer_class = CostCentreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = CostCentre.objects.select_related("group")
        user = self.request.user
        if not sees_all_orders(user):
            qs = qs.filter(group__in=visible_group_ids(user))
        if group := self.request.query_params.get("group"):
            qs = qs.filter(group=group)
        return qs

    def _check(self, group):
        if not has_group_role(self.request.user, group, Role.PI):
            raise PermissionDenied("Only the group's PI or admin can manage its budgets.")

    def perform_create(self, serializer):
        self._check(serializer.validated_data["group"])
        serializer.save()

    def perform_update(self, serializer):
        self._check(serializer.instance.group)
        serializer.save()

    def perform_destroy(self, instance):
        self._check(instance.group)
        if instance.orders.exists():
            raise ValidationError("Cost centre has orders; deactivate it instead.")
        instance.delete()


@extend_schema(
    parameters=[
        OpenApiParameter("status", str, description="Comma-separated, or 'open'"),
        OpenApiParameter("group", str),
        OpenApiParameter("mine", bool),
        OpenApiParameter("q", str),
        OpenApiParameter("to_approve", bool, description="Orders the user can approve"),
    ]
)
class OrderViewSet(viewsets.ModelViewSet):
    """Reagent orders. Members request for their group; PIs/approvers approve; central
    purchasing (or the PI) places the order and receives it into the inventory."""

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.select_related(
            "compound", "group", "requested_by", "decided_by", "supplier", "cost_centre"
        ).prefetch_related("containers")
        if not sees_all_orders(user):
            qs = qs.filter(group__in=visible_group_ids(user))
        if self.action != "list":
            return qs
        p = self.request.query_params
        if status := p.get("status"):
            qs = qs.filter(status__in=OrderStatus.OPEN if status == "open" else status.split(","))
        if group := p.get("group"):
            qs = qs.filter(group=group)
        if p.get("mine") in ("1", "true"):
            qs = qs.filter(requested_by=user)
        if p.get("to_approve") in ("1", "true"):
            qs = qs.filter(status=OrderStatus.SUBMITTED)
            if not user.has_capability(Capability.ORDER_APPROVER):
                qs = qs.filter(group__in=group_ids_with_role(user, Role.PI))
        if q := p.get("q"):
            qs = qs.filter(
                Q(number__icontains=q)
                | Q(item_name__icontains=q)
                | Q(cas__icontains=q)
                | Q(catalog_number__icontains=q)
                | Q(po_number__icontains=q)
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    def perform_update(self, serializer):
        order = serializer.instance
        user = self.request.user
        if order.status in (OrderStatus.DRAFT, OrderStatus.REJECTED):
            if order.requested_by_id != user.id and not has_group_role(user, order.group, Role.PI):
                raise PermissionDenied("Only the requester or the PI can edit this order.")
        elif not services.can_receive(user, order):
            raise PermissionDenied("You cannot change this order.")
        serializer.save()

    def perform_destroy(self, order):
        if order.status != OrderStatus.DRAFT or order.requested_by_id != self.request.user.id:
            raise ValidationError("Only your own drafts can be deleted; cancel other orders.")
        order.delete()

    def _run(self, fn):
        try:
            return fn()
        except services.OrderPermissionError as e:
            raise PermissionDenied(str(e)) from e
        except services.OrderError as e:
            raise ValidationError({"detail": str(e)}) from e

    @extend_schema(request=TransitionSerializer, responses=OrderSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        """Workflow step: submit, approve, reject, place (ordered), cancel."""
        s = TransitionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        order = self._run(
            lambda: services.transition(
                self.get_object(),
                d["action"],
                request.user,
                note=d["note"],
                po_number=d.get("po_number"),
                expected_date=d.get("expected_date"),
                override_budget=d["override_budget"],
            )
        )
        return Response(self.get_serializer(order).data)

    @extend_schema(request=ReceiveSerializer, responses=ContainerSerializer(many=True))
    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        """Book packages in: creates one labelled inventory container per package."""
        s = ReceiveSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        location = get_object_or_404(Location, pk=d["location"]) if d.get("location") else None
        containers = self._run(
            lambda: services.receive(
                self.get_object(),
                request.user,
                quantity=d["quantity"],
                location=location,
                lot_number=d["lot_number"],
                expiry_date=d.get("expiry_date"),
                note=d["note"],
            )
        )
        return Response(ContainerSerializer(containers, many=True).data, status=201)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        return Response(OrderEventSerializer(self.get_object().events.all(), many=True).data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Counts per status plus open spend, for the dashboard."""
        qs = self.get_queryset()
        counts = dict(qs.values_list("status").annotate(n=Count("id")))
        to_approve = self.get_queryset().filter(status=OrderStatus.SUBMITTED)
        if not request.user.has_capability(Capability.ORDER_APPROVER):
            to_approve = to_approve.filter(group__in=group_ids_with_role(request.user, Role.PI))
        open_spend = qs.filter(
            status__in=[OrderStatus.APPROVED, OrderStatus.ORDERED, OrderStatus.PARTIAL]
        ).aggregate(s=Sum(F("unit_price") * F("quantity")))["s"]
        return Response(
            {
                "by_status": counts,
                "to_approve": to_approve.count(),
                "to_receive": qs.filter(
                    status__in=[OrderStatus.ORDERED, OrderStatus.PARTIAL]
                ).count(),
                "open_spend": open_spend,
            }
        )


@extend_schema(responses=OrderSerializer)
@api_view(["POST"])
def reorder_container(request, pk):
    """Draft a new order from an existing container (same product, supplier, size)."""
    container = get_object_or_404(Container, pk=pk)
    if not has_group_role(request.user, container.group, Role.MEMBER):
        raise PermissionDenied("Only members of the owning group can re-order.")
    order = services.reorder_from_container(container, request.user)
    return Response(OrderSerializer(order, context={"request": request}).data, status=201)
