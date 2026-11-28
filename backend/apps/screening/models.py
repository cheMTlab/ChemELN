"""Reaction screening & optimization campaigns (design: docs/roadmap/m4-optimization.md)."""

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Equipment(models.TextChoices):
    MANUAL = "manual", "Manual (flasks / vials)"
    HTE_PLATE = "hte_plate", "HTE plate"
    FLOW = "flow", "Flow reactor"
    ROBOT = "robot", "Automated platform"


class CampaignStatus(models.TextChoices):
    DESIGN = "design", "Designing"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    ARCHIVED = "archived", "Archived"


class Campaign(BaseModel):
    group = models.ForeignKey(
        "orgs.ResearchGroup", on_delete=models.PROTECT, related_name="campaigns"
    )
    project = models.ForeignKey(
        "eln.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="campaigns"
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=255)
    objective = models.TextField(blank=True)
    reaction_smiles = models.TextField(blank=True)
    reaction_rxn = models.TextField(blank=True)
    equipment = models.CharField(max_length=10, choices=Equipment.choices, default=Equipment.MANUAL)
    plate_format = models.PositiveSmallIntegerField(
        default=96, help_text="Wells per plate for HTE campaigns"
    )
    status = models.CharField(
        max_length=10, choices=CampaignStatus.choices, default=CampaignStatus.DESIGN
    )
    notes = models.TextField(blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class VariableKind(models.TextChoices):
    CONTINUOUS = "continuous", "Continuous (range)"
    DISCRETE = "discrete", "Discrete numeric levels"
    CATEGORICAL = "categorical", "Categorical (e.g. solvent, catalyst)"


class Variable(BaseModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="variables")
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=12, choices=VariableKind.choices)
    unit = models.CharField(max_length=30, blank=True)
    low = models.FloatField(null=True, blank=True)
    high = models.FloatField(null=True, blank=True)
    levels = models.JSONField(
        default=list,
        blank=True,
        help_text="Discrete numbers or category labels; categories may carry a compound id",
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["campaign", "position", "created_at"]

    def __str__(self) -> str:
        return self.name


class Goal(models.TextChoices):
    MAXIMIZE = "maximize", "Maximize"
    MINIMIZE = "minimize", "Minimize"
    TARGET = "target", "Hit a target"
    MONITOR = "monitor", "Only record"


class Response(BaseModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="responses")
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=30, blank=True)
    goal = models.CharField(max_length=10, choices=Goal.choices, default=Goal.MAXIMIZE)
    target = models.FloatField(null=True, blank=True)
    weight = models.FloatField(default=1.0)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["campaign", "position", "created_at"]

    def __str__(self) -> str:
        return self.name


class RunStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    RUNNING = "running", "Running"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class Run(BaseModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="runs")
    index = models.PositiveIntegerField()
    label = models.CharField(max_length=50, blank=True)
    plate = models.PositiveSmallIntegerField(null=True, blank=True)
    well = models.CharField(max_length=4, blank=True, help_text="e.g. A1 (HTE)")
    factors = models.JSONField(default=dict, help_text="{variable_id: value}")
    results = models.JSONField(default=dict, blank=True, help_text="{response_id: value}")
    status = models.CharField(max_length=8, choices=RunStatus.choices, default=RunStatus.PLANNED)
    failure_reason = models.CharField(max_length=255, blank=True)
    source = models.CharField(
        max_length=20, default="design", help_text="design, suggestion, manual, import"
    )
    experiment = models.ForeignKey(
        "eln.Experiment", null=True, blank=True, on_delete=models.SET_NULL, related_name="runs"
    )
    lots = models.JSONField(
        default=list,
        blank=True,
        help_text="Inventory containers used (hidden-variable capture): barcodes",
    )
    notes = models.CharField(max_length=500, blank=True)
    performed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["campaign", "index"]
        constraints = [models.UniqueConstraint(fields=["campaign", "index"], name="uniq_run_index")]

    def __str__(self) -> str:
        return f"Run {self.index}"
