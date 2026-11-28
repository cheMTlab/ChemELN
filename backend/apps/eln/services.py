"""ELN business logic: stoichiometry, reaction import, inventory links, signing."""

import hashlib
import json
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rdkit import Chem
from rdkit.Chem import rdChemReactions

from apps.chemistry import rdkit_utils
from apps.chemistry.models import Compound
from apps.inventory import services as inventory
from apps.inventory.models import Container, ContainerEvent, EventKind
from apps.orgs.models import Role
from apps.orgs.permissions import has_group_role

from .models import ComponentRole, Experiment, ReactionComponent, Signature, SignatureKind


class ElnError(ValueError):
    pass


# --- stoichiometry -------------------------------------------------------------------------


def _r(x, nd=4):
    return None if x is None else round(x, nd)


def recalculate(experiment: Experiment) -> None:
    """Fill in mmol / mass / volume from the limiting reagent and equivalents.

    Rules (as chemists do it on paper):
    * The limiting reactant sets the scale: its mmol comes from mass (or volume) if given.
    * Every other row with equivalents gets mmol = scale × eq; mass = mmol × MW / purity;
      volume = mass / density, or mmol / molarity for solutions.
    * Products: theoretical mmol = scale × eq (default 1); yield = actual mass / theoretical.
    """
    rows = list(experiment.components.all())
    limiting = next((c for c in rows if c.is_limiting), None) or next(
        (c for c in rows if c.role == ComponentRole.REACTANT and (c.mmol or c.mass_mg)), None
    )
    scale = None
    if limiting:
        _fill_from_amount(limiting)
        limiting.equivalents = 1.0
        scale = limiting.mmol
    for c in rows:
        if c is limiting or scale is None:
            if c is not limiting:
                _fill_from_amount(c)
        elif c.role == ComponentRole.PRODUCT:
            c.mmol = scale * (c.equivalents or 1.0)
            if c.mw:
                c.mass_mg = c.mmol * c.mw  # theoretical
        elif c.equivalents is not None:
            c.mmol = scale * c.equivalents
            _fill_mass_volume(c)
        else:
            _fill_from_amount(c)
        if c.role == ComponentRole.PRODUCT:
            c.yield_percent = None
            if c.actual_mass_mg and c.mass_mg:
                purity = (c.product_purity or 100.0) / 100.0
                c.yield_percent = _r(100.0 * c.actual_mass_mg * purity / c.mass_mg, 1)
    for c in rows:
        c.mmol, c.mass_mg, c.volume_ml = _r(c.mmol), _r(c.mass_mg, 3), _r(c.volume_ml, 4)
        c.save()


def _fill_from_amount(c: ReactionComponent) -> None:
    """Derive mmol from whatever amount the user typed."""
    purity = (c.purity or 100.0) / 100.0
    if c.mass_mg and c.mw:
        c.mmol = c.mass_mg * purity / c.mw
    elif c.volume_ml and c.molarity:
        c.mmol = c.volume_ml * c.molarity
    elif c.volume_ml and c.density and c.mw:
        c.mass_mg = c.volume_ml * c.density * 1000
        c.mmol = c.mass_mg * purity / c.mw
    elif c.mmol:
        _fill_mass_volume(c)
    if c.mass_mg and c.density and not c.volume_ml and c.role != ComponentRole.PRODUCT:
        c.volume_ml = c.mass_mg / 1000 / c.density


def _fill_mass_volume(c: ReactionComponent) -> None:
    purity = (c.purity or 100.0) / 100.0
    if c.molarity:
        c.volume_ml = c.mmol / c.molarity
        c.mass_mg = c.mmol * c.mw if c.mw else None
        return
    if c.mw:
        c.mass_mg = c.mmol * c.mw / purity
        c.volume_ml = c.mass_mg / 1000 / c.density if c.density else None


def fill_from_compound(c: ReactionComponent) -> None:
    if c.compound:
        c.name = c.name or c.compound.name
        c.smiles = c.smiles or c.compound.smiles
        c.mw = c.mw or c.compound.mw
        if c.density is None and c.compound.density:
            c.density = float(c.compound.density)
    if c.container:
        c.compound = c.compound or c.container.compound
        if c.purity is None and c.container.purity:
            c.purity = float(c.container.purity)
        if not c.molarity and c.container.concentration:
            c.molarity = _parse_molarity(c.container.concentration)
        fill = c.container.compound
        c.name = c.name or fill.name
        c.smiles = c.smiles or fill.smiles
        c.mw = c.mw or fill.mw
        if c.density is None and fill.density:
            c.density = float(fill.density)
    if c.smiles and not c.mw:
        try:
            c.mw = rdkit_utils.analyse(c.smiles).mw
        except rdkit_utils.InvalidStructure:
            pass


def _parse_molarity(text: str) -> float | None:
    """'1.0 M in THF' → 1.0"""
    import re

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*M\b", text)
    return float(m.group(1).replace(",", ".")) if m else None


# --- reaction import -----------------------------------------------------------------------


def parse_reaction(text: str) -> tuple[list[str], list[str], list[str]]:
    """RXN block or reaction SMILES → (reactant SMILES, agent SMILES, product SMILES)."""
    text = text or ""
    try:
        if "$RXN" in text:
            rxn = rdChemReactions.ReactionFromRxnBlock(text)
        else:
            rxn = rdChemReactions.ReactionFromSmarts(text.strip(), useSmiles=True)
    except Exception as exc:  # RDKit raises various types
        raise ElnError(f"Could not read the reaction: {exc}") from exc
    if rxn is None:
        raise ElnError("Could not read the reaction.")

    def smiles(mols):
        out = []
        for m in mols:
            try:
                m = Chem.Mol(m)
                Chem.SanitizeMol(m)
                out.append(Chem.MolToSmiles(m))
            except Exception:  # noqa: S112 - skip unparseable fragments (e.g. arrows/text)
                continue
        return [s for s in out if s]

    return (
        smiles(rxn.GetReactants()),
        smiles(rxn.GetAgents()),
        smiles(rxn.GetProducts()),
    )


@transaction.atomic
def import_reaction(experiment: Experiment, text: str, replace: bool = True) -> None:
    reactants, agents, products = parse_reaction(text)
    if not (reactants or products):
        raise ElnError("The drawing contains no reactants or products.")
    if replace:
        experiment.components.filter(container__isnull=True, consumed=False).delete()
    pos = experiment.components.aggregate(m=Max("position"))["m"] or 0
    first = True
    for role, items in (
        (ComponentRole.REACTANT, reactants),
        (ComponentRole.REAGENT, agents),
        (ComponentRole.PRODUCT, products),
    ):
        for smi in items:
            pos += 1
            info = rdkit_utils.analyse(smi)
            compound = Compound.objects.filter(inchikey=info.inchikey).first()
            c = ReactionComponent(
                experiment=experiment,
                role=role,
                position=pos,
                smiles=info.smiles,
                mw=info.mw,
                compound=compound,
                name=compound.name if compound else info.formula,
                equivalents=1.0,
                is_limiting=role == ComponentRole.REACTANT and first,
            )
            if role == ComponentRole.REACTANT:
                first = False
            fill_from_compound(c)
            c.save()
    experiment.reaction_smiles = (
        ".".join(reactants) + ">" + ".".join(agents) + ">" + ".".join(products)
    )
    if "$RXN" in (text or ""):
        experiment.reaction_rxn = text
    experiment.save(update_fields=["reaction_smiles", "reaction_rxn", "updated_at"])


# --- inventory links -----------------------------------------------------------------------


@transaction.atomic
def deduct_inventory(experiment: Experiment, user) -> list[str]:
    """Book the amounts used out of the linked containers (once per row)."""
    done = []
    for c in experiment.components.select_related("container").filter(
        container__isnull=False, consumed=False
    ):
        if c.role == ComponentRole.PRODUCT:
            continue
        unit = c.container.unit
        if unit in ("mL", "L", "uL") and c.volume_ml:
            amount, amount_unit = Decimal(str(c.volume_ml)), "mL"
        elif c.mass_mg:
            amount, amount_unit = Decimal(str(c.mass_mg)), "mg"
        elif c.volume_ml:
            amount, amount_unit = Decimal(str(c.volume_ml)), "mL"
        else:
            raise ElnError(f"No amount for {c.name}.")
        try:
            inventory.use(c.container, amount, amount_unit, user, note=f"Used in {experiment.code}")
        except inventory.InventoryError as exc:
            raise ElnError(f"{c.name}: {exc}") from exc
        c.consumed = True
        c.save(update_fields=["consumed", "updated_at"])
        done.append(c.container.barcode)
    experiment.inventory_deducted = True
    experiment.save(update_fields=["inventory_deducted", "updated_at"])
    return done


@transaction.atomic
def register_product(
    component: ReactionComponent, user, *, name: str = "", location=None, amount_mg=None
) -> Container:
    """Create (or find) the product compound and a new container with the isolated amount."""
    if component.role != ComponentRole.PRODUCT:
        raise ElnError("Only products can be registered.")
    if component.registered_container_id:
        raise ElnError("This product is already in the inventory.")
    amount = amount_mg or component.actual_mass_mg
    if not amount:
        raise ElnError("Enter the isolated mass first.")
    exp = component.experiment
    compound = component.compound
    if compound is None:
        if component.smiles:
            info = rdkit_utils.analyse(component.smiles)
            compound = Compound.objects.filter(inchikey=info.inchikey).first()
        if compound is None:
            compound = Compound(name=name or component.name or f"Product of {exp.code}")
            if component.smiles:
                compound.set_structure(component.smiles)
            compound.created_by = user
            compound.save()
    container = Container.objects.create(
        compound=compound,
        group=exp.group,
        owner=user,
        location=location,
        amount=Decimal(str(amount)),
        unit="mg",
        purity=component.product_purity,
        supplier=f"Synthesised ({exp.code})",
        lot_number=exp.code,
        notes=f"Product of {exp.code}: {exp.title}",
    )
    ContainerEvent.objects.create(
        container=container, user=user, kind=EventKind.CREATED, note=f"Product of {exp.code}"
    )
    component.compound = compound
    component.registered_container = container
    component.save(update_fields=["compound", "registered_container", "updated_at"])
    return container


# --- signing -------------------------------------------------------------------------------


def content_snapshot(experiment: Experiment) -> dict:
    # Status, tags, project and completion date stay editable after signing (LOCK_EXEMPT in
    # serializers), so they are not part of the signed content.
    fields = [
        "code",
        "title",
        "kind",
        "aim",
        "procedure",
        "observations",
        "conclusion",
        "reaction_smiles",
        "reaction_rxn",
        "temperature",
        "duration",
        "atmosphere",
        "solvent",
        "workup",
        "started_on",
    ]
    data = {f: str(getattr(experiment, f) or "") for f in fields}
    data["owner"] = experiment.owner.email
    data["components"] = [
        {
            k: (str(v) if v is not None else None)
            for k, v in {
                "role": c.role,
                "name": c.name,
                "smiles": c.smiles,
                "mw": c.mw,
                "equivalents": c.equivalents,
                "mmol": c.mmol,
                "mass_mg": c.mass_mg,
                "volume_ml": c.volume_ml,
                "actual_mass_mg": c.actual_mass_mg,
                "yield_percent": c.yield_percent,
                "container": c.container.barcode if c.container else None,
            }.items()
        }
        for c in experiment.components.select_related("container").order_by("position", "id")
    ]
    data["attachments"] = sorted(a.sha256 for a in experiment.attachments.all())
    return data


def content_hash(experiment: Experiment) -> str:
    blob = json.dumps(content_snapshot(experiment), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _append_signature(experiment, kind, user, meaning) -> Signature:
    last = Signature.objects.select_for_update().order_by("-seq").first()
    prev = last.hash if last else ""
    seq = (last.seq + 1) if last else 1
    chash = content_hash(experiment)
    now = timezone.now()
    digest = hashlib.sha256(
        f"{prev}|{chash}|{experiment.id}|{kind}|{user.id}|{now.isoformat()}".encode()
    ).hexdigest()
    sig = Signature.objects.create(
        experiment=experiment,
        kind=kind,
        user=user,
        meaning=meaning,
        content_hash=chash,
        prev_hash=prev,
        hash=digest,
        seq=seq,
    )
    Signature.objects.filter(pk=sig.pk).update(created_at=now)
    return sig


@transaction.atomic
def sign(experiment: Experiment, user, meaning: str = "") -> Signature:
    experiment = Experiment.objects.select_for_update().get(pk=experiment.pk)
    if experiment.is_locked:
        raise ElnError("Already signed.")
    if experiment.owner_id != user.id:
        raise ElnError("Only the author can sign the experiment.")
    sig = _append_signature(
        experiment, SignatureKind.SIGN, user, meaning or "I am the author of this record."
    )
    experiment.signed_by, experiment.signed_at = user, sig.created_at or timezone.now()
    experiment.save(update_fields=["signed_by", "signed_at", "updated_at"])
    return sig


@transaction.atomic
def witness(experiment: Experiment, user, meaning: str = "") -> Signature:
    experiment = Experiment.objects.select_for_update().get(pk=experiment.pk)
    if not experiment.is_locked:
        raise ElnError("The author must sign first.")
    if experiment.witnessed_at:
        raise ElnError("Already witnessed.")
    if user.id == experiment.owner_id:
        raise ElnError("You cannot witness your own experiment.")
    if not has_group_role(user, experiment.group, Role.MEMBER):
        raise ElnError("Witnesses must be members of the experiment's group.")
    sig = _append_signature(
        experiment,
        SignatureKind.WITNESS,
        user,
        meaning or "I have read and understood this record.",
    )
    experiment.witnessed_by, experiment.witnessed_at = user, timezone.now()
    experiment.save(update_fields=["witnessed_by", "witnessed_at", "updated_at"])
    return sig


def verify_experiment(experiment: Experiment) -> dict:
    """Recompute the content hash and check it against every signature."""
    current = content_hash(experiment)
    sigs = list(experiment.signatures.select_related("user"))
    return {
        "content_hash": current,
        "intact": all(s.content_hash == current for s in sigs) if sigs else None,
        "signatures": [
            {
                "kind": s.kind,
                "user": s.user.display_name,
                "at": s.created_at,
                "hash": s.hash,
                "matches": s.content_hash == current,
            }
            for s in sigs
        ],
    }


def verify_ledger() -> dict:
    """Walk the whole signature chain; a broken link means the ledger was altered."""
    prev = ""
    for s in Signature.objects.order_by("seq"):
        if s.prev_hash != prev:
            return {"intact": False, "broken_at": s.seq}
        prev = s.hash
    return {"intact": True, "length": Signature.objects.count()}
