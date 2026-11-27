"""Container actions. Each one changes the container and writes an activity event."""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q

from . import units
from .models import Container, ContainerEvent, ContainerStatus, EventKind


class InventoryError(ValueError):
    pass


@transaction.atomic
def move(container: Container, location, user, note: str = "") -> Container:
    old = container.location
    container.location = location
    container.save(update_fields=["location", "updated_at"])
    ContainerEvent.objects.create(
        container=container,
        user=user,
        kind=EventKind.MOVED,
        from_location=old,
        to_location=location,
        note=note,
    )
    return container


@transaction.atomic
def use(container: Container, amount: Decimal, unit: str, user, note: str = "") -> Container:
    container = Container.objects.select_for_update().get(pk=container.pk)
    try:
        used = units.convert(amount, unit, container.unit)
    except units.IncompatibleUnits as exc:
        raise InventoryError(str(exc)) from exc
    if used > container.amount:
        raise InventoryError(
            f"Only {container.amount.normalize()} {container.unit} left in {container.barcode}."
        )
    container.amount -= used
    if container.opened_date is None:
        container.opened_date = date.today()
    if container.amount == 0:
        container.status = ContainerStatus.EMPTY
    container.save()
    ContainerEvent.objects.create(
        container=container, user=user, kind=EventKind.USED, amount_change=-used, note=note
    )
    return container


@transaction.atomic
def adjust(container: Container, amount: Decimal, user, note: str = "") -> Container:
    change = amount - container.amount
    container.amount = amount
    if amount > 0 and container.status == ContainerStatus.EMPTY:
        container.status = ContainerStatus.AVAILABLE
    container.save()
    ContainerEvent.objects.create(
        container=container, user=user, kind=EventKind.ADJUSTED, amount_change=change, note=note
    )
    return container


@transaction.atomic
def set_status(container: Container, status: str, user, note: str = "") -> Container:
    old = container.status
    container.status = status
    container.save(update_fields=["status", "updated_at"])
    ContainerEvent.objects.create(
        container=container, user=user, kind=EventKind.STATUS, note=note or f"{old} → {status}"
    )
    return container


ACTIVE = ~Q(status__in=[ContainerStatus.DISPOSED, ContainerStatus.EMPTY])
PEROXIDE_RETEST_DAYS = 180
LOW_STOCK_FRACTION = Decimal("0.1")


def alerts(qs) -> dict:
    """Things that need attention, for the dashboard."""
    today = date.today()
    active = qs.filter(ACTIVE)
    return {
        "expired": active.filter(expiry_date__lt=today),
        "expiring_soon": active.filter(
            expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)
        ),
        "peroxide_retest": active.filter(
            compound__is_peroxide_former=True,
            opened_date__lte=today - timedelta(days=PEROXIDE_RETEST_DAYS),
        ),
        "low_stock": active.filter(
            initial_amount__gt=0, amount__lte=F("initial_amount") * LOW_STOCK_FRACTION
        ),
        "storage_conflicts": [
            c
            for c in active.exclude(location=None).select_related("location", "compound")
            if c.storage_warning
        ],
    }
