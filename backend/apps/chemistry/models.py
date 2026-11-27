import hashlib

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel

from . import rdkit_utils
from .safety import SignalWord, StorageClass, validate_cas, validate_pictograms


class Compound(BaseModel):
    """A chemical substance, shared by everyone on the instance.

    Structures are canonicalised with RDKit, and the InChIKey prevents duplicates.
    Substances without a defined structure (mixtures, Celite, polymers) are allowed.
    """

    name = models.CharField(max_length=255, db_index=True)
    synonyms = models.JSONField(default=list, blank=True)
    cas = models.CharField(
        "CAS number", max_length=12, blank=True, db_index=True, validators=[validate_cas]
    )

    # Structure (filled from `set_structure`)
    smiles = models.TextField("canonical SMILES", blank=True)
    molfile = models.TextField(blank=True)
    inchi = models.TextField(blank=True)
    inchikey = models.CharField(max_length=27, unique=True, null=True, blank=True)
    formula = models.CharField(max_length=100, blank=True)
    mw = models.FloatField("molecular weight (g/mol)", null=True, blank=True)
    exact_mass = models.FloatField(null=True, blank=True)
    density = models.FloatField("density (g/mL)", null=True, blank=True)

    # Safety
    signal_word = models.CharField(
        max_length=10, choices=SignalWord.choices, blank=True, default=SignalWord.NONE
    )
    ghs_pictograms = models.JSONField(default=list, blank=True, validators=[validate_pictograms])
    h_statements = models.JSONField(default=list, blank=True)
    p_statements = models.JSONField(default=list, blank=True)
    storage_class = models.CharField(
        max_length=20, choices=StorageClass.choices, default=StorageClass.GENERAL
    )
    is_peroxide_former = models.BooleanField(default=False)
    is_controlled = models.BooleanField(
        default=False, help_text="Controlled substance / drug precursor / dual-use"
    )

    pubchem_cid = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def set_structure(self, text: str) -> None:
        """Set structure from SMILES or molfile; empty text clears it."""
        if not (text or "").strip():
            self.smiles = self.molfile = self.inchi = self.formula = ""
            self.inchikey = None
            self.mw = self.exact_mass = None
            return
        info = rdkit_utils.analyse(text)
        self.smiles = info.smiles
        self.molfile = info.molfile
        self.inchi = info.inchi
        self.inchikey = info.inchikey or None
        self.formula = info.formula
        self.mw = info.mw
        self.exact_mass = info.exact_mass


def sds_upload_to(instance, filename):
    return f"sds/{instance.compound_id}/{filename}"


class SafetyDataSheet(BaseModel):
    compound = models.ForeignKey(Compound, on_delete=models.CASCADE, related_name="sds")
    supplier = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=10, default="en")
    revision_date = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to=sds_upload_to, blank=True)
    url = models.URLField(blank=True)
    sha256 = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        ordering = ["-revision_date"]

    def save(self, *args, **kwargs):
        if self.file and not self.sha256:
            digest = hashlib.sha256()
            for chunk in self.file.chunks():
                digest.update(chunk)
            self.sha256 = digest.hexdigest()
        super().save(*args, **kwargs)
