"""Reagent ordering: request → approval → purchase → receipt into the inventory.

Modelled on Open Enventory's order system (order requests, central purchasing, cost centres,
supplier offers), with an explicit, audited state machine.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Sum
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.inventory.units import Unit


class Supplier(BaseModel):
    name = models.CharField(max_length=150, unique=True)
    website = models.URLField(blank=True)
    customer_number = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CostCentre(BaseModel):
    """A budget line (grant, project account) that orders are charged to."""

    group = models.ForeignKey(
        "orgs.ResearchGroup", on_delete=models.PROTECT, related_name="cost_centres"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["group__name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["group", "code"], name="uniq_cost_centre_code")
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    def save(self, *args, **kwargs):
        if not self.currency:
            self.currency = settings.CHEMTLAB["CURRENCY"]
        super().save(*args, **kwargs)

    @property
    def committed(self) -> Decimal:
        """Money approved, ordered or received against this budget."""
        total = self.orders.filter(status__in=OrderStatus.COMMITTED).aggregate(
            t=Sum(F("unit_price") * F("quantity"))
        )["t"]
        return total or Decimal("0")

    @property
    def remaining(self) -> Decimal | None:
        return None if self.budget is None else self.budget - self.committed


class OrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Waiting for approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    ORDERED = "ordered", "Ordered"
    PARTIAL = "partial", "Partially received"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


OrderStatus.COMMITTED = [  # type: ignore[attr-defined]
    OrderStatus.APPROVED,
    OrderStatus.ORDERED,
    OrderStatus.PARTIAL,
    OrderStatus.RECEIVED,
]
OrderStatus.OPEN = [  # type: ignore[attr-defined]
    OrderStatus.DRAFT,
    OrderStatus.SUBMITTED,
    OrderStatus.APPROVED,
    OrderStatus.ORDERED,
    OrderStatus.PARTIAL,
]


class Urgency(models.TextChoices):
    NORMAL = "normal", "Normal"
    URGENT = "urgent", "Urgent"


class Order(BaseModel):
    """One line: N packages of one product from one supplier."""

    number = models.CharField(max_length=20, unique=True, editable=False)
    group = models.ForeignKey("orgs.ResearchGroup", on_delete=models.PROTECT, related_name="orders")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders_requested"
    )
    status = models.CharField(max_length=10, choices=OrderStatus.choices, default=OrderStatus.DRAFT)
    urgency = models.CharField(max_length=10, choices=Urgency.choices, default=Urgency.NORMAL)

    # What: a known compound, or free text for things not yet in the database.
    compound = models.ForeignKey(
        "chemistry.Compound", null=True, blank=True, on_delete=models.PROTECT, related_name="orders"
    )
    item_name = models.CharField(max_length=255, blank=True)
    cas = models.CharField("CAS number", max_length=12, blank=True)
    grade = models.CharField(max_length=100, blank=True)
    purity = models.DecimalField(
        "purity (%)", max_digits=6, decimal_places=3, null=True, blank=True
    )

    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="orders"
    )
    supplier_name = models.CharField(max_length=150, blank=True, help_text="If not in the list")
    catalog_number = models.CharField(max_length=100, blank=True)
    package_amount = models.DecimalField(max_digits=14, decimal_places=4)
    package_unit = models.CharField(max_length=5, choices=Unit.choices)
    quantity = models.PositiveIntegerField(default=1, help_text="Number of packages")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    cost_centre = models.ForeignKey(
        CostCentre, null=True, blank=True, on_delete=models.PROTECT, related_name="orders"
    )
    justification = models.TextField(blank=True)
    delivery_location = models.ForeignKey(
        "locations.Location", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # Workflow stamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=500, blank=True)
    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    ordered_at = models.DateTimeField(null=True, blank=True)
    po_number = models.CharField("purchase order no.", max_length=100, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    received_quantity = models.PositiveIntegerField(default=0)
    received_at = models.DateTimeField(null=True, blank=True)

    containers = models.ManyToManyField(
        "inventory.Container", blank=True, related_name="orders", editable=False
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "group"])]

    def __str__(self) -> str:
        return f"{self.number} {self.display_name}"

    @property
    def display_name(self) -> str:
        return self.compound.name if self.compound else self.item_name

    @property
    def total_price(self) -> Decimal | None:
        return None if self.unit_price is None else self.unit_price * self.quantity

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_order_number()
        if not self.currency:
            self.currency = settings.CHEMTLAB["CURRENCY"]
        if self.compound and not self.item_name:
            self.item_name = self.compound.name
            self.cas = self.cas or self.compound.cas
        super().save(*args, **kwargs)


def next_order_number() -> str:
    from django.utils import timezone

    year = timezone.now().year
    prefix = f"PO-{year}-"
    last = (
        Order.objects.filter(number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:05d}"


class OrderEvent(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    from_status = models.CharField(max_length=10, blank=True)
    to_status = models.CharField(max_length=10)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["created_at"]
