"""Order state machine. Every transition is checked here and logged as an OrderEvent."""

from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Capability
from apps.inventory.models import Container, ContainerEvent, EventKind
from apps.orgs.models import Role
from apps.orgs.permissions import has_group_role

from .models import Order, OrderEvent, OrderStatus


class OrderError(ValueError):
    pass


class OrderPermissionError(PermissionError):
    pass


S = OrderStatus

TRANSITIONS = {
    "submit": ({S.DRAFT, S.REJECTED}, S.SUBMITTED),
    "approve": ({S.SUBMITTED}, S.APPROVED),
    "reject": ({S.SUBMITTED}, S.REJECTED),
    "place": ({S.APPROVED}, S.ORDERED),
    "cancel": ({S.DRAFT, S.SUBMITTED, S.APPROVED, S.ORDERED}, S.CANCELLED),
}


def can_approve(user, order: Order) -> bool:
    return user.has_capability(Capability.ORDER_APPROVER) or has_group_role(
        user, order.group, Role.PI
    )


def can_purchase(user, order: Order) -> bool:
    """Central purchasing places and receives orders; PIs can do it for their own group."""
    return user.has_capability(Capability.PURCHASING) or has_group_role(user, order.group, Role.PI)


def can_receive(user, order: Order) -> bool:
    return can_purchase(user, order) or has_group_role(user, order.group, Role.MEMBER)


def allowed_actions(user, order: Order) -> list[str]:
    actions = []
    is_requester = order.requested_by_id == user.id
    member = has_group_role(user, order.group, Role.MEMBER)
    for name, (sources, _) in TRANSITIONS.items():
        if order.status not in sources:
            continue
        if name == "submit" and (is_requester or member):
            actions.append(name)
        elif name in ("approve", "reject") and can_approve(user, order):
            actions.append(name)
        elif name == "place" and can_purchase(user, order):
            actions.append(name)
        elif name == "cancel" and (
            (is_requester and order.status in (S.DRAFT, S.SUBMITTED)) or can_purchase(user, order)
        ):
            actions.append(name)
    if order.status in (S.ORDERED, S.PARTIAL) and can_receive(user, order):
        actions.append("receive")
    return actions


def _log(order: Order, user, old: str, note: str = ""):
    OrderEvent.objects.create(
        order=order, user=user, from_status=old, to_status=order.status, note=note[:500]
    )


@transaction.atomic
def transition(order: Order, action: str, user, note: str = "", **fields) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if action not in TRANSITIONS:
        raise OrderError(f"Unknown action {action!r}")
    if action not in allowed_actions(user, order):
        sources, _ = TRANSITIONS[action]
        if order.status not in sources:
            raise OrderError(f"Cannot {action} an order that is {order.get_status_display()}.")
        raise OrderPermissionError(f"You are not allowed to {action} this order.")

    old = order.status
    now = timezone.now()
    if action == "submit":
        if order.cost_centre and order.cost_centre.group_id != order.group_id:
            raise OrderError("The cost centre belongs to another group.")
        order.submitted_at = now
        order.rejection_reason = ""
        # PIs/approvers ordering for themselves skip the queue.
        order.status = S.APPROVED if can_approve(user, order) else S.SUBMITTED
        if order.status == S.APPROVED:
            order.decided_by, order.decided_at = user, now
    elif action == "approve":
        cc = order.cost_centre
        total = order.total_price
        if cc and cc.budget is not None and total is not None and cc.remaining < total:
            if not fields.get("override_budget"):
                raise OrderError(
                    f"Over budget: {cc.code} has {cc.remaining} {cc.currency} left, "
                    f"this order costs {total} {order.currency}."
                )
            note = (note + " (budget override)").strip()
        order.status, order.decided_by, order.decided_at = S.APPROVED, user, now
    elif action == "reject":
        if not note:
            raise OrderError("Give a reason for rejecting the order.")
        order.status, order.decided_by, order.decided_at = S.REJECTED, user, now
        order.rejection_reason = note
    elif action == "place":
        order.status, order.ordered_by, order.ordered_at = S.ORDERED, user, now
        order.po_number = fields.get("po_number") or order.po_number
        order.expected_date = fields.get("expected_date") or order.expected_date
    elif action == "cancel":
        order.status = S.CANCELLED
    order.save()
    _log(order, user, old, note)
    return order


@transaction.atomic
def receive(
    order: Order,
    user,
    *,
    quantity: int,
    location=None,
    lot_number: str = "",
    expiry_date: date | None = None,
    note: str = "",
) -> list[Container]:
    """Book `quantity` packages in: one inventory container (with barcode) per package."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if "receive" not in allowed_actions(user, order):
        if order.status not in (S.ORDERED, S.PARTIAL):
            raise OrderError(f"Cannot receive an order that is {order.get_status_display()}.")
        raise OrderPermissionError("You are not allowed to receive this order.")
    outstanding = order.quantity - order.received_quantity
    if quantity < 1 or quantity > outstanding:
        raise OrderError(f"Quantity must be between 1 and {outstanding}.")
    if order.compound is None:
        raise OrderError(
            "Link the order to a compound before receiving it, so the containers can be created."
        )

    containers = []
    for _ in range(quantity):
        c = Container.objects.create(
            compound=order.compound,
            group=order.group,
            owner=order.requested_by,
            location=location or order.delivery_location,
            amount=order.package_amount,
            unit=order.package_unit,
            purity=order.purity,
            grade=order.grade,
            supplier=order.supplier.name if order.supplier else order.supplier_name,
            catalog_number=order.catalog_number,
            lot_number=lot_number,
            price=order.unit_price,
            currency=order.currency,
            expiry_date=expiry_date,
        )
        ContainerEvent.objects.create(
            container=c,
            user=user,
            kind=EventKind.CREATED,
            note=f"Received from order {order.number}",
        )
        containers.append(c)
    order.containers.add(*containers)

    old = order.status
    order.received_quantity += quantity
    order.status = S.RECEIVED if order.received_quantity >= order.quantity else S.PARTIAL
    order.received_at = timezone.now()
    order.save()
    _log(order, user, old, note or f"Received {quantity} package(s)")
    return containers


def reorder_from_container(container: Container, user) -> Order:
    """Draft a new order copying the product details of an existing bottle."""
    return Order.objects.create(
        group=container.group,
        requested_by=user,
        compound=container.compound,
        supplier_name=container.supplier,
        catalog_number=container.catalog_number,
        package_amount=container.initial_amount or container.amount,
        package_unit=container.unit,
        purity=container.purity,
        grade=container.grade,
        unit_price=container.price,
        delivery_location=container.location,
        justification=f"Re-order of {container.barcode}",
    )
