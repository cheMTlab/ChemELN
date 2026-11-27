from django.core.exceptions import ValidationError
from django.db import models, transaction
from simple_history.models import HistoricalRecords

from apps.chemistry.safety import StorageClass
from apps.core.models import BaseModel

PATH_SEPARATOR = " / "


class LocationKind(models.TextChoices):
    SITE = "site", "Site"
    BUILDING = "building", "Building"
    FLOOR = "floor", "Floor"
    ROOM = "room", "Room"
    CABINET = "cabinet", "Cabinet"
    SHELF = "shelf", "Shelf"
    FRIDGE = "fridge", "Fridge"
    FREEZER = "freezer", "Freezer"
    GLOVEBOX = "glovebox", "Glovebox"
    BOX = "box", "Box"
    OTHER = "other", "Other"


class Location(BaseModel):
    """A place where containers are stored, in a tree: site › building › room › cabinet › shelf."""

    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=LocationKind.choices, default=LocationKind.OTHER)
    barcode = models.CharField(max_length=64, unique=True, null=True, blank=True)
    group = models.ForeignKey(
        "orgs.ResearchGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locations",
        help_text="Owning group. Empty means a shared location managed by administrators.",
    )
    allowed_storage_classes = models.JSONField(
        default=list,
        blank=True,
        help_text="Storage classes allowed here. Empty means any.",
    )
    temperature = models.CharField(max_length=30, blank=True, help_text="e.g. 4 °C, -20 °C")
    notes = models.TextField(blank=True)
    path = models.CharField(max_length=1000, editable=False, db_index=True)
    depth = models.PositiveSmallIntegerField(default=0, editable=False)

    history = HistoricalRecords()

    class Meta:
        ordering = ["path"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="uniq_location_name")
        ]

    def __str__(self) -> str:
        return self.path or self.name

    def clean(self):
        node = self.parent
        while node is not None:
            if node.pk == self.pk:
                raise ValidationError({"parent": "A location cannot be inside itself."})
            node = node.parent
        bad = [c for c in self.allowed_storage_classes if c not in StorageClass.values]
        if bad:
            raise ValidationError({"allowed_storage_classes": f"Unknown: {', '.join(bad)}"})

    def _compute_path(self):
        if self.parent:
            self.path = f"{self.parent.path}{PATH_SEPARATOR}{self.name}"
            self.depth = self.parent.depth + 1
        else:
            self.path, self.depth = self.name, 0

    def save(self, *args, **kwargs):
        old_path = (
            Location.objects.filter(pk=self.pk).values_list("path", flat=True).first()
            if self.pk
            else None
        )
        self._compute_path()
        with transaction.atomic():
            super().save(*args, **kwargs)
            if old_path and old_path != self.path:
                for child in self.children.all():
                    child.save()  # cascades down the tree

    def allows(self, storage_class: str) -> bool:
        return not self.allowed_storage_classes or storage_class in self.allowed_storage_classes

    def descendant_ids(self) -> list:
        prefix = f"{self.path}{PATH_SEPARATOR}"
        ids = list(Location.objects.filter(path__startswith=prefix).values_list("id", flat=True))
        return [self.id, *ids]
