"""GHS hazard helpers and storage-class suggestions."""

import re

from django.core.exceptions import ValidationError
from django.db import models

GHS_PICTOGRAMS = {
    "GHS01": "Explosive",
    "GHS02": "Flammable",
    "GHS03": "Oxidizing",
    "GHS04": "Compressed gas",
    "GHS05": "Corrosive",
    "GHS06": "Toxic",
    "GHS07": "Harmful / irritant",
    "GHS08": "Health hazard",
    "GHS09": "Environmental hazard",
}

H_CODE = re.compile(r"\b(?:EU)?H\d{3}[A-Za-z]{0,2}\b")
P_CODE = re.compile(r"\bP\d{3}(?:\+P\d{3})*\b")


class SignalWord(models.TextChoices):
    NONE = "", "None"
    WARNING = "warning", "Warning"
    DANGER = "danger", "Danger"


class StorageClass(models.TextChoices):
    """Simplified storage segregation classes (in the spirit of TRGS 510 / NFPA)."""

    GENERAL = "general", "General"
    EXPLOSIVE = "explosive", "Explosive"
    COMPRESSED_GAS = "gas", "Compressed gas"
    FLAMMABLE_LIQUID = "flam_liquid", "Flammable liquid"
    FLAMMABLE_SOLID = "flam_solid", "Flammable solid"
    PYROPHORIC = "pyrophoric", "Pyrophoric"
    WATER_REACTIVE = "water_reactive", "Water-reactive"
    OXIDIZER = "oxidizer", "Oxidizer"
    ORGANIC_PEROXIDE = "org_peroxide", "Organic peroxide"
    TOXIC = "toxic", "Acutely toxic"
    CORROSIVE = "corrosive", "Corrosive"


# Most dangerous first: the first matching rule wins.
_STORAGE_RULES: list[tuple[StorageClass, tuple[str, ...]]] = [
    (StorageClass.EXPLOSIVE, ("H200", "H201", "H202", "H203", "H204", "H205")),
    (StorageClass.PYROPHORIC, ("H250",)),
    (StorageClass.WATER_REACTIVE, ("H260", "H261")),
    (StorageClass.ORGANIC_PEROXIDE, ("H240", "H241", "H242")),
    (StorageClass.COMPRESSED_GAS, ("H220", "H221", "H280", "H281")),
    (StorageClass.OXIDIZER, ("H270", "H271", "H272")),
    (StorageClass.FLAMMABLE_LIQUID, ("H224", "H225", "H226")),
    (StorageClass.FLAMMABLE_SOLID, ("H228",)),
    (StorageClass.TOXIC, ("H300", "H310", "H330", "H301", "H311", "H331")),
    (StorageClass.CORROSIVE, ("H314", "H290")),
]


def suggest_storage_class(h_statements: list[str]) -> str:
    codes = {h.strip().upper()[:4] for h in h_statements}
    for storage_class, triggers in _STORAGE_RULES:
        if codes.intersection(triggers):
            return storage_class
    return StorageClass.GENERAL


def validate_pictograms(value):
    unknown = [p for p in value or [] if p not in GHS_PICTOGRAMS]
    if unknown:
        raise ValidationError(f"Unknown GHS pictogram(s): {', '.join(unknown)}")


def validate_cas(value: str) -> None:
    """CAS Registry Number with check digit, e.g. 64-17-5."""
    if not value:
        return
    if not re.fullmatch(r"\d{2,7}-\d{2}-\d", value):
        raise ValidationError("CAS number must look like 64-17-5")
    digits = value.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    if total % 10 != check:
        raise ValidationError("CAS number check digit is wrong")


def is_valid_cas(value: str) -> bool:
    try:
        validate_cas(value)
        return bool(value)
    except ValidationError:
        return False
