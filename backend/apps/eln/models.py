"""Electronic lab notebook: projects, experiments, reactions linked to the inventory, signing.

Notebook codes follow Open Enventory's lab-journal style (<initials>-<number>, e.g. AB-0042).
Signed experiments are immutable; signatures form a SHA-256 hash chain so any later tampering
with stored content or the signature ledger is detectable (21 CFR Part 11-style).
"""

import hashlib

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class ProjectStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ON_HOLD = "on_hold", "On hold"
    ARCHIVED = "archived", "Archived"


class Project(BaseModel):
    group = models.ForeignKey(
        "orgs.ResearchGroup", on_delete=models.PROTECT, related_name="projects"
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=ProjectStatus.choices, default=ProjectStatus.ACTIVE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["group", "name"], name="uniq_project_name")]

    def __str__(self) -> str:
        return self.name


class ExperimentKind(models.TextChoices):
    SYNTHESIS = "synthesis", "Synthesis"
    ANALYSIS = "analysis", "Analysis"
    BIOLOGY = "biology", "Biology"
    SCREENING = "screening", "Screening run"
    GENERAL = "general", "General"


class ExperimentStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ExperimentTemplate(BaseModel):
    group = models.ForeignKey(
        "orgs.ResearchGroup",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="experiment_templates",
        help_text="Empty: available to everyone",
    )
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=10, choices=ExperimentKind.choices)
    aim = models.TextField(blank=True)
    procedure = models.TextField(blank=True)
    components = models.JSONField(default=list, blank=True, help_text="Default reaction rows")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Experiment(BaseModel):
    code = models.CharField(max_length=20, unique=True, editable=False)
    group = models.ForeignKey(
        "orgs.ResearchGroup", on_delete=models.PROTECT, related_name="experiments"
    )
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="experiments"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="experiments"
    )
    title = models.CharField(max_length=255)
    kind = models.CharField(
        max_length=10, choices=ExperimentKind.choices, default=ExperimentKind.SYNTHESIS
    )
    status = models.CharField(
        max_length=12, choices=ExperimentStatus.choices, default=ExperimentStatus.PLANNED
    )
    tags = models.JSONField(default=list, blank=True)
    template = models.ForeignKey(
        ExperimentTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    references = models.ManyToManyField("self", blank=True, symmetrical=False, related_name="+")

    # Narrative (Markdown)
    aim = models.TextField(blank=True)
    procedure = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)

    # Reaction
    reaction_rxn = models.TextField(blank=True, help_text="MDL RXN from the structure editor")
    reaction_smiles = models.TextField(blank=True)
    temperature = models.CharField(max_length=50, blank=True, help_text="e.g. 80 °C, reflux")
    duration = models.CharField(max_length=50, blank=True, help_text="e.g. 16 h")
    atmosphere = models.CharField(max_length=50, blank=True)
    solvent = models.CharField(max_length=150, blank=True)
    workup = models.TextField(blank=True)

    started_on = models.DateField(null=True, blank=True)
    completed_on = models.DateField(null=True, blank=True)
    inventory_deducted = models.BooleanField(default=False)

    # Signing
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    witnessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    witnessed_at = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["group", "status"])]

    def __str__(self) -> str:
        return f"{self.code} {self.title}"

    @property
    def is_locked(self) -> bool:
        return self.signed_at is not None

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = next_code(self.owner)
        super().save(*args, **kwargs)


def next_code(user) -> str:
    prefix = user.notebook_prefix() + "-"
    codes = Experiment.objects.filter(code__startswith=prefix).values_list("code", flat=True)
    nums = [int(c[len(prefix) :]) for c in codes if c[len(prefix) :].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1:04d}"


class ComponentRole(models.TextChoices):
    REACTANT = "reactant", "Reactant"
    REAGENT = "reagent", "Reagent"
    CATALYST = "catalyst", "Catalyst"
    SOLVENT = "solvent", "Solvent"
    PRODUCT = "product", "Product"


class ReactionComponent(BaseModel):
    """One row of the stoichiometry table. Amounts are kept in mmol / mg / mL."""

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name="components")
    role = models.CharField(max_length=10, choices=ComponentRole.choices)
    position = models.PositiveSmallIntegerField(default=0)
    compound = models.ForeignKey(
        "chemistry.Compound", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    container = models.ForeignKey(
        "inventory.Container",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reaction_uses",
    )
    name = models.CharField(max_length=255, blank=True)
    smiles = models.TextField(blank=True)
    mw = models.FloatField("molar mass (g/mol)", null=True, blank=True)
    density = models.FloatField("density (g/mL)", null=True, blank=True)
    purity = models.FloatField("purity (%)", null=True, blank=True)
    molarity = models.FloatField("concentration (mol/L)", null=True, blank=True)
    equivalents = models.FloatField(null=True, blank=True)
    is_limiting = models.BooleanField(default=False)
    mmol = models.FloatField(null=True, blank=True)
    mass_mg = models.FloatField(null=True, blank=True)
    volume_ml = models.FloatField(null=True, blank=True)
    # Products
    actual_mass_mg = models.FloatField(null=True, blank=True)
    product_purity = models.FloatField(null=True, blank=True)
    yield_percent = models.FloatField(null=True, blank=True, editable=False)
    registered_container = models.ForeignKey(
        "inventory.Container", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    consumed = models.BooleanField(default=False, editable=False)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["experiment", "position", "created_at"]

    def __str__(self) -> str:
        return f"{self.get_role_display()}: {self.name}"


def attachment_upload_to(instance, filename):
    return f"eln/{instance.experiment_id}/{filename}"


class Attachment(BaseModel):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_upload_to)
    name = models.CharField(max_length=255)
    kind = models.CharField(
        max_length=20, blank=True, help_text="e.g. NMR, MS, IR, HPLC, photo, other"
    )
    description = models.CharField(max_length=500, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, editable=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self.file and not self.sha256:
            h = hashlib.sha256()
            for chunk in self.file.chunks():
                h.update(chunk)
            self.sha256 = h.hexdigest()
            self.size = self.file.size
        super().save(*args, **kwargs)


class Comment(BaseModel):
    """Discussion and addenda. Allowed after signing (signed content itself never changes)."""

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    text = models.TextField()
    is_addendum = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["created_at"]


class SignatureKind(models.TextChoices):
    SIGN = "sign", "Signed by author"
    WITNESS = "witness", "Witnessed"


class Signature(BaseModel):
    """Append-only ledger. hash = SHA256(prev_hash + content_hash + meta)."""

    experiment = models.ForeignKey(Experiment, on_delete=models.PROTECT, related_name="signatures")
    kind = models.CharField(max_length=10, choices=SignatureKind.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    meaning = models.CharField(max_length=200, blank=True)
    content_hash = models.CharField(max_length=64)
    prev_hash = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64, unique=True)
    seq = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ["seq"]
