"""Amount units and conversion between compatible units."""

from decimal import Decimal

from django.db import models


class Unit(models.TextChoices):
    MG = "mg", "mg"
    G = "g", "g"
    KG = "kg", "kg"
    UL = "uL", "µL"
    ML = "mL", "mL"
    L = "L", "L"
    UMOL = "umol", "µmol"
    MMOL = "mmol", "mmol"
    MOL = "mol", "mol"
    PCS = "pcs", "pieces"


# unit -> (dimension, factor to the base unit of that dimension)
_UNITS: dict[str, tuple[str, Decimal]] = {
    "mg": ("mass", Decimal("0.001")),
    "g": ("mass", Decimal("1")),
    "kg": ("mass", Decimal("1000")),
    "uL": ("volume", Decimal("0.001")),
    "mL": ("volume", Decimal("1")),
    "L": ("volume", Decimal("1000")),
    "umol": ("moles", Decimal("0.000001")),
    "mmol": ("moles", Decimal("0.001")),
    "mol": ("moles", Decimal("1")),
    "pcs": ("count", Decimal("1")),
}


class IncompatibleUnits(ValueError):
    pass


def dimension(unit: str) -> str:
    return _UNITS[unit][0]


def convert(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """Convert between units of the same dimension (mass, volume, moles, count)."""
    value = Decimal(value)
    if from_unit == to_unit:
        return value
    d_from, f_from = _UNITS[from_unit]
    d_to, f_to = _UNITS[to_unit]
    if d_from != d_to:
        raise IncompatibleUnits(f"Cannot convert {from_unit} to {to_unit}")
    return value * f_from / f_to
