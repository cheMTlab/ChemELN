"""Biology: plasmids, strains/cell lines, oligos, biological samples, well plates and assays."""

import string

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel

from . import sequence


def _next_code(model, prefix: str, field: str = "code") -> str:
    codes = model.objects.filter(**{f"{field}__startswith": prefix}).values_list(field, flat=True)
    nums = [int(c[len(prefix) :]) for c in codes if c[len(prefix) :].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1:04d}"


class BiosafetyLevel(models.IntegerChoices):
    BSL1 = 1, "BSL-1"
    BSL2 = 2, "BSL-2"
    BSL3 = 3, "BSL-3"
    BSL4 = 4, "BSL-4"


class Plasmid(BaseModel):
    code = models.CharField(max_length=20, unique=True, editable=False)
    group = models.ForeignKey(
        "orgs.ResearchGroup", on_delete=models.PROTECT, related_name="plasmids"
    )
    name = models.CharField(max_length=255)
    alias = models.CharField(max_length=255, blank=True)
    backbone = models.CharField(max_length=150, blank=True)
    insert = models.CharField(max_length=255, blank=True)
    insert_species = models.CharField(max_length=100, blank=True)
    vector_type = models.CharField(
        max_length=50, blank=True, help_text="e.g. bacterial expression, mammalian, lentiviral"
    )
    resistance = models.JSONField(default=list, blank=True, help_text="e.g. ['Ampicillin']")
    origin = models.CharField(max_length=50, blank=True)
    promoter = models.CharField(max_length=100, blank=True)
    tags = models.JSONField(default=list, blank=True, help_text="Protein tags, e.g. His6, GFP")
    copy_number = models.CharField(max_length=20, blank=True)
    growth_temperature = models.CharField(max_length=20, blank=True)
    sequence = models.TextField(blank=True)
    features = models.JSONField(
        default=list, blank=True, help_text="[{name, type, start, end, strand}] (1-based)"
    )
    circular = models.BooleanField(default=True)
    size_bp = models.PositiveIntegerField(null=True, blank=True)
    gc_content = models.FloatField(null=True, blank=True, editable=False)
    source = models.CharField(max_length=255, blank=True, help_text="Lab, company or Addgene")
    addgene_id = models.CharField(max_length=20, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivatives"
    )
    verified = models.BooleanField(default=False, help_text="Sequence verified")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = _next_code(Plasmid, settings.CHEMTLAB.get("PLASMID_PREFIX", "pCT"))
        self.sequence = sequence.clean(self.sequence)
        if self.sequence:
            self.size_bp = len(self.sequence)
            self.gc_content = sequence.gc_content(self.sequence)
        super().save(*args, **kwargs)


class StrainKind(models.TextChoices):
    BACTERIUM = "bacterium", "Bacterial strain"
    YEAST = "yeast", "Yeast strain"
    CELL_LINE = "cell_line", "Cell line"
    VIRUS = "virus", "Virus"
    OTHER = "other", "Other organism"


class Strain(BaseModel):
    code = models.CharField(max_length=20, unique=True, editable=False)
    group = models.ForeignKey(
        "orgs.ResearchGroup", on_delete=models.PROTECT, related_name="strains"
    )
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=10, choices=StrainKind.choices)
    organism = models.CharField(max_length=150, blank=True, help_text="e.g. E. coli, H. sapiens")
    genotype = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivatives"
    )
    plasmids = models.ManyToManyField(Plasmid, blank=True, related_name="strains")
    resistance = models.JSONField(default=list, blank=True)
    biosafety_level = models.PositiveSmallIntegerField(
        choices=BiosafetyLevel.choices, default=BiosafetyLevel.BSL1
    )
    is_gmo = models.BooleanField("genetically modified", default=False)
    growth_conditions = models.CharField(max_length=255, blank=True)
    tissue = models.CharField(max_length=100, blank=True, help_text="Cell lines")
    passage = models.PositiveIntegerField(null=True, blank=True, help_text="Cell lines")
    mycoplasma_tested_on = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=255, blank=True, help_text="e.g. ATCC CRL-1573")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            prefix = "CL" if self.kind == StrainKind.CELL_LINE else "ST"
            self.code = _next_code(Strain, prefix)
        super().save(*args, **kwargs)


class Oligo(BaseModel):
    code = models.CharField(max_length=20, unique=True, editable=False)
    group = models.ForeignKey("orgs.ResearchGroup", on_delete=models.PROTECT, related_name="oligos")
    name = models.CharField(max_length=255)
    sequence = models.CharField(max_length=500, help_text="5'→3'")
    purpose = models.CharField(max_length=100, blank=True, help_text="PCR, sequencing, gRNA…")
    target = models.CharField(max_length=255, blank=True)
    modifications = models.CharField(max_length=255, blank=True, help_text="e.g. 5'-FAM")
    scale = models.CharField(max_length=50, blank=True)
    purification = models.CharField(max_length=50, blank=True)
    supplier = models.CharField(max_length=150, blank=True)
    tm = models.FloatField("Tm (°C)", null=True, blank=True, editable=False)
    gc_content = models.FloatField(null=True, blank=True, editable=False)
    plasmid = models.ForeignKey(
        Plasmid, null=True, blank=True, on_delete=models.SET_NULL, related_name="oligos"
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = _next_code(Oligo, "OL")
        self.sequence = sequence.clean(self.sequence, allow_n=True)
        if self.sequence:
            self.tm = sequence.melting_temperature(self.sequence)
            self.gc_content = sequence.gc_content(self.sequence)
        super().save(*args, **kwargs)


class SampleKind(models.TextChoices):
    GLYCEROL = "glycerol", "Glycerol stock"
    DNA = "dna", "DNA prep"
    RNA = "rna", "RNA"
    CELLS = "cells", "Frozen cells"
    PROTEIN = "protein", "Protein"
    ANTIBODY = "antibody", "Antibody"
    SERUM = "serum", "Serum / tissue"
    OTHER = "other", "Other"


class BioSample(BaseModel):
    """A physical tube of biological material (stored in the shared location tree)."""

    barcode = models.CharField(max_length=64, unique=True)
    group = models.ForeignKey(
        "orgs.ResearchGroup", on_delete=models.PROTECT, related_name="bio_samples"
    )
    kind = models.CharField(max_length=10, choices=SampleKind.choices)
    name = models.CharField(max_length=255)
    plasmid = models.ForeignKey(
        Plasmid, null=True, blank=True, on_delete=models.PROTECT, related_name="samples"
    )
    strain = models.ForeignKey(
        Strain, null=True, blank=True, on_delete=models.PROTECT, related_name="samples"
    )
    location = models.ForeignKey(
        "locations.Location", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    box_position = models.CharField(max_length=10, blank=True, help_text="e.g. A1 in a 9×9 box")
    concentration = models.FloatField(null=True, blank=True)
    concentration_unit = models.CharField(max_length=20, blank=True, help_text="ng/µL, mg/mL…")
    volume_ul = models.FloatField("volume (µL)", null=True, blank=True)
    passage = models.PositiveIntegerField(null=True, blank=True)
    prepared_on = models.DateField(null=True, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_available = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.barcode} {self.name}"

    def save(self, *args, **kwargs):
        if not self.barcode:
            from apps.inventory.models import generate_barcode

            self.barcode = "B" + generate_barcode()
        super().save(*args, **kwargs)


PLATE_FORMATS = {
    6: (2, 3),
    12: (3, 4),
    24: (4, 6),
    48: (6, 8),
    96: (8, 12),
    384: (16, 24),
    1536: (32, 48),
}


def row_label(i: int) -> str:
    letters = string.ascii_uppercase
    return letters[i] if i < 26 else letters[i // 26 - 1] + letters[i % 26]


class PlateKind(models.TextChoices):
    ASSAY = "assay", "Assay plate"
    CULTURE = "culture", "Culture plate"
    LIBRARY = "library", "Compound library"
    PCR = "pcr", "PCR / qPCR"
    STORAGE = "storage", "Storage plate"


class Assay(BaseModel):
    group = models.ForeignKey("orgs.ResearchGroup", on_delete=models.PROTECT, related_name="assays")
    name = models.CharField(max_length=255)
    readout = models.CharField(
        max_length=30,
        default="absorbance",
        help_text="absorbance, fluorescence, luminescence, OD600, qPCR Ct, other",
    )
    wavelength = models.CharField(max_length=50, blank=True, help_text="e.g. 450 nm, ex485/em520")
    unit = models.CharField(max_length=30, blank=True)
    target = models.CharField(max_length=255, blank=True)
    higher_is_active = models.BooleanField(
        default=False, help_text="Off: inhibition assay (signal falls with activity)"
    )
    protocol = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Plate(BaseModel):
    barcode = models.CharField(max_length=64, unique=True)
    group = models.ForeignKey("orgs.ResearchGroup", on_delete=models.PROTECT, related_name="plates")
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=10, choices=PlateKind.choices, default=PlateKind.ASSAY)
    format = models.PositiveSmallIntegerField(default=96)
    assay = models.ForeignKey(
        Assay, null=True, blank=True, on_delete=models.SET_NULL, related_name="plates"
    )
    experiment = models.ForeignKey(
        "eln.Experiment", null=True, blank=True, on_delete=models.SET_NULL, related_name="plates"
    )
    location = models.ForeignKey(
        "locations.Location", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    template = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Layout copied from this plate",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.barcode} {self.name}"

    @property
    def shape(self) -> tuple[int, int]:
        return PLATE_FORMATS[self.format]

    def save(self, *args, **kwargs):
        if not self.barcode:
            from apps.inventory.models import generate_barcode

            self.barcode = "P" + generate_barcode()
        super().save(*args, **kwargs)


class WellRole(models.TextChoices):
    EMPTY = "empty", "Empty"
    SAMPLE = "sample", "Sample"
    POSITIVE = "positive", "Positive control"
    NEGATIVE = "negative", "Negative control"
    BLANK = "blank", "Blank"
    STANDARD = "standard", "Standard"


class Well(BaseModel):
    plate = models.ForeignKey(Plate, on_delete=models.CASCADE, related_name="wells")
    row = models.PositiveSmallIntegerField()
    col = models.PositiveSmallIntegerField()
    role = models.CharField(max_length=10, choices=WellRole.choices, default=WellRole.EMPTY)
    label = models.CharField(max_length=100, blank=True, help_text="Sample name or ID")
    compound = models.ForeignKey(
        "chemistry.Compound", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    strain = models.ForeignKey(
        Strain, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    plasmid = models.ForeignKey(
        Plasmid, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    sample = models.ForeignKey(
        BioSample, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    concentration = models.FloatField(null=True, blank=True)
    concentration_unit = models.CharField(max_length=20, blank=True, default="µM")
    volume_ul = models.FloatField(null=True, blank=True)
    replicate = models.PositiveSmallIntegerField(null=True, blank=True)
    group_label = models.CharField(
        max_length=100, blank=True, help_text="Wells sharing this label form one dose-response"
    )
    excluded = models.BooleanField(default=False, help_text="Outlier, ignored in analysis")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["plate", "row", "col"]
        constraints = [models.UniqueConstraint(fields=["plate", "row", "col"], name="uniq_well")]

    @property
    def name(self) -> str:
        return f"{row_label(self.row)}{self.col + 1}"


class Measurement(BaseModel):
    well = models.ForeignKey(Well, on_delete=models.CASCADE, related_name="measurements")
    channel = models.CharField(max_length=50, default="signal", help_text="Read name / channel")
    timepoint = models.FloatField(default=0, help_text="Minutes from start (kinetic reads)")
    value = models.FloatField()

    class Meta:
        ordering = ["well", "channel", "timepoint"]
        indexes = [models.Index(fields=["well", "channel"])]
