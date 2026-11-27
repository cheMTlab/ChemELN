import secrets
from datetime import date

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel

from .units import Unit

# Crockford base32 without ambiguous characters (no I, L, O, U)
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_barcode() -> str:
    prefix = settings.CHEMTLAB["BARCODE_PREFIX"]
    while True:
        code = prefix + "".join(secrets.choice(_ALPHABET) for _ in range(8))
        if not Container.objects.filter(barcode=code).exists():
            return code


class ContainerStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    BORROWED = "borrowed", "Borrowed / checked out"
    EMPTY = "empty", "Empty"
    MISSING = "missing", "Missing"
    DISPOSED = "disposed", "Disposed"


class Container(BaseModel):
    """A physical bottle, vial or bag of a compound, with a scannable barcode."""

    barcode = models.CharField(max_length=64, unique=True, default=generate_barcode)
    compound = models.ForeignKey(
        "chemistry.Compound", on_delete=models.PROTECT, related_name="containers"
    )
    group = models.ForeignKey(
        "orgs.ResearchGroup", on_delete=models.PROTECT, related_name="containers"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="containers",
    )
    location = models.ForeignKey(
        "locations.Location",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="containers",
    )
    status = models.CharField(
        max_length=12, choices=ContainerStatus.choices, default=ContainerStatus.AVAILABLE
    )

    amount = models.DecimalField(max_digits=14, decimal_places=4)
    initial_amount = models.DecimalField(max_digits=14, decimal_places=4, blank=True)
    unit = models.CharField(max_length=5, choices=Unit.choices)
    purity = models.DecimalField(
        "purity (%)", max_digits=6, decimal_places=3, null=True, blank=True
    )
    concentration = models.CharField(
        max_length=50, blank=True, help_text="For solutions, e.g. 1.0 M in THF"
    )
    grade = models.CharField(max_length=100, blank=True)

    supplier = models.CharField(max_length=150, blank=True)
    catalog_number = models.CharField(max_length=100, blank=True)
    lot_number = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)

    received_date = models.DateField(default=date.today)
    opened_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["compound__name", "-received_date"]
        indexes = [models.Index(fields=["status", "expiry_date"])]

    def __str__(self) -> str:
        return f"{self.barcode} {self.compound} ({self.amount} {self.unit})"

    def save(self, *args, **kwargs):
        if self.initial_amount is None:
            self.initial_amount = self.amount
        if not self.currency:
            self.currency = settings.CHEMTLAB["CURRENCY"]
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return bool(self.expiry_date and self.expiry_date < date.today())

    @property
    def fraction_remaining(self) -> float | None:
        if not self.initial_amount:
            return None
        return float(self.amount / self.initial_amount)

    @property
    def storage_warning(self) -> str:
        if self.location and not self.location.allows(self.compound.storage_class):
            return (
                f"{self.compound.get_storage_class_display()} should not be stored in "
                f"{self.location.path}."
            )
        return ""


class EventKind(models.TextChoices):
    CREATED = "created", "Created"
    MOVED = "moved", "Moved"
    USED = "used", "Used"
    ADJUSTED = "adjusted", "Amount corrected"
    OPENED = "opened", "Opened"
    STATUS = "status", "Status changed"


class ContainerEvent(BaseModel):
    """Human-readable activity log of a container (the full field history is in `history`)."""

    container = models.ForeignKey(Container, on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    kind = models.CharField(max_length=10, choices=EventKind.choices)
    amount_change = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    from_location = models.ForeignKey(
        "locations.Location", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    to_location = models.ForeignKey(
        "locations.Location", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
