"""Bulk import of containers from CSV/XLSX-exported CSV or SDF files.

Each row becomes a container; its compound is matched (InChIKey → CAS → exact name) or created.
Run with dry_run=True first: nothing is saved, but every row is validated and reported.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from rdkit import Chem

from apps.chemistry import rdkit_utils
from apps.chemistry.models import Compound
from apps.chemistry.safety import is_valid_cas
from apps.locations.models import PATH_SEPARATOR, Location

from .models import Container, ContainerEvent, EventKind
from .units import Unit

# Accepted column names (lower-case) for each field. Includes common spellings from other
# inventory systems' exports; extend as real export files are tested.
ALIASES = {
    "name": [
        "name",
        "compound",
        "chemical",
        "chemical name",
        "substance",
        "molecule_name",
        "product name",
    ],
    "cas": ["cas", "cas number", "cas no", "cas_nr", "casrn", "cas-nr"],
    "smiles": ["smiles", "structure"],
    "amount": ["amount", "quantity", "qty", "size"],
    "unit": ["unit", "units", "amount_unit", "uom"],
    "location": ["location", "storage", "storage_name", "location path", "place"],
    "supplier": ["supplier", "vendor", "manufacturer"],
    "catalog_number": [
        "catalog_number",
        "catalog number",
        "cat no",
        "cat. no.",
        "product number",
        "article number",
    ],
    "lot_number": ["lot", "lot_number", "lot number", "batch"],
    "purity": ["purity", "purity (%)", "assay"],
    "barcode": ["barcode", "container id", "bottle id"],
    "expiry_date": ["expiry", "expiry_date", "expiration date", "expires"],
    "received_date": ["received", "received_date", "date received"],
    "price": ["price", "cost"],
}
_UNIT_LOOKUP = {u.lower(): u for u in Unit.values} | {
    "µl": "uL",
    "µmol": "umol",
    "l": "L",
    "ml": "mL",
    "ul": "uL",
    "pieces": "pcs",
}


@dataclass
class ImportResult:
    dry_run: bool
    rows: int = 0
    created_containers: int = 0
    created_compounds: int = 0
    matched_compounds: int = 0
    errors: list[dict] = field(default_factory=list)


class _RowError(Exception):
    pass


def _normalise(row: dict) -> dict:
    lowered = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
    out = {}
    for key, names in ALIASES.items():
        for n in names:
            if lowered.get(n):
                out[key] = lowered[n]
                break
    return out


def _decimal(value: str, label: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace(",", ".").rstrip("%").strip())
    except InvalidOperation as exc:
        raise _RowError(f"{label} '{value}' is not a number") from exc


def _date(value: str, label: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise _RowError(f"{label} '{value}' must be a date like 2027-03-31") from exc


def _location(value: str, cache: dict) -> Location | None:
    if not value:
        return None
    if value not in cache:
        parts = [p.strip() for p in value.replace(">", "/").split("/") if p.strip()]
        loc = (
            Location.objects.filter(barcode=value).first()
            or Location.objects.filter(path=PATH_SEPARATOR.join(parts)).first()
        )
        if loc is None:
            raise _RowError(f"Location '{value}' not found (use its barcode or full path)")
        cache[value] = loc
    return cache[value]


def _compound(data: dict, user, result: ImportResult) -> Compound:
    smiles, cas, name = data.get("smiles", ""), data.get("cas", ""), data.get("name", "")
    if cas and not is_valid_cas(cas):
        raise _RowError(f"CAS number '{cas}' is invalid")
    info = None
    if smiles:
        try:
            info = rdkit_utils.analyse(smiles)
        except rdkit_utils.InvalidStructure as exc:
            raise _RowError(f"SMILES '{smiles}' could not be read") from exc
    found = None
    if info and info.inchikey:
        found = Compound.objects.filter(inchikey=info.inchikey).first()
    if not found and cas:
        found = Compound.objects.filter(cas=cas).first()
    if not found and name:
        found = Compound.objects.filter(name__iexact=name).first()
    if found:
        result.matched_compounds += 1
        return found
    if not name and not cas and not info:
        raise _RowError("Each row needs a name, CAS number or SMILES")
    compound = Compound(name=name or cas or info.formula, cas=cas, created_by=user)
    if smiles:
        compound.set_structure(smiles)
    compound.save()
    result.created_compounds += 1
    return compound


def _import_row(data: dict, group, user, result: ImportResult, loc_cache: dict) -> None:
    amount = _decimal(data.get("amount", ""), "Amount")
    if amount is None:
        raise _RowError("Amount is required")
    unit = _UNIT_LOOKUP.get(data.get("unit", "").lower())
    if not unit:
        raise _RowError(f"Unknown unit '{data.get('unit', '')}' (use mg, g, kg, µL, mL, L, mmol…)")
    barcode = data.get("barcode") or None
    if barcode and Container.objects.filter(barcode=barcode).exists():
        raise _RowError(f"Barcode {barcode} already exists")
    container = Container(
        compound=_compound(data, user, result),
        group=group,
        owner=user,
        location=_location(data.get("location", ""), loc_cache),
        amount=amount,
        unit=unit,
        purity=_decimal(data.get("purity", ""), "Purity"),
        supplier=data.get("supplier", ""),
        catalog_number=data.get("catalog_number", ""),
        lot_number=data.get("lot_number", ""),
        price=_decimal(data.get("price", ""), "Price"),
        expiry_date=_date(data.get("expiry_date", ""), "Expiry date"),
    )
    if received := _date(data.get("received_date", ""), "Received date"):
        container.received_date = received
    if barcode:
        container.barcode = barcode
    container.save()
    ContainerEvent.objects.create(
        container=container, user=user, kind=EventKind.CREATED, note="Imported"
    )
    result.created_containers += 1


def import_rows(rows, group, user, dry_run: bool = True) -> ImportResult:
    result = ImportResult(dry_run=dry_run)
    loc_cache: dict = {}
    with transaction.atomic():
        for number, raw in enumerate(rows, start=1):
            result.rows += 1
            data = _normalise(raw)
            try:
                with transaction.atomic():
                    _import_row(data, group, user, result, loc_cache)
            except _RowError as exc:
                result.errors.append({"row": number, "message": str(exc)})
        if dry_run or result.errors:
            # All-or-nothing: fix the file and import again.
            transaction.set_rollback(True)
            if not dry_run:
                result.created_containers = result.created_compounds = 0
    return result


def rows_from_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.DictReader(io.StringIO(text), dialect=dialect))


def rows_from_sdf(content: bytes) -> list[dict]:
    rows = []
    supplier = Chem.ForwardSDMolSupplier(io.BytesIO(content))
    for mol in supplier:
        if mol is None:
            rows.append({"smiles": "invalid"})
            continue
        row = {k: str(v) for k, v in mol.GetPropsAsDict().items()}
        row["smiles"] = Chem.MolToSmiles(mol)
        if mol.HasProp("_Name") and not any(k.lower() in ALIASES["name"] for k in row):
            row["name"] = mol.GetProp("_Name")
        rows.append(row)
    return rows
