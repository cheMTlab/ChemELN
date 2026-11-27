"""Structure search.

Uses the RDKit PostgreSQL cartridge when it is available (fast, index-backed), and falls back
to RDKit in Python otherwise (fine for development and small instances).
"""

from functools import cache

from django.db import connection
from django.db.models import Q, QuerySet
from rdkit import Chem

from . import rdkit_utils

SIMILARITY_LIMIT = 200


@cache
def cartridge_available() -> bool:
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'rdkit'")
        return cur.fetchone() is not None


def text_filter(qs: QuerySet, q: str) -> QuerySet:
    """Name, synonym, CAS, formula or InChIKey."""
    q = q.strip()
    cond = (
        Q(name__icontains=q)
        | Q(cas=q)
        | Q(formula__iexact=q)
        | Q(inchikey=q.upper())
        | Q(synonyms__icontains=q)
    )
    return qs.filter(cond)


def substructure_filter(qs: QuerySet, query_text: str) -> QuerySet:
    """Compounds containing the query substructure. `qs` must be a Compound queryset."""
    query = rdkit_utils.query_mol(query_text)
    if cartridge_available():
        table = qs.model._meta.db_table
        # Safe: only our own table name is interpolated; user input is a bound parameter.
        return qs.extra(  # noqa: S610
            where=[
                f'"{table}"."smiles" <> \'\' AND '
                f'mol_from_smiles("{table}"."smiles"::cstring) @> qmol_from_smarts(%s::cstring)'
            ],
            params=[Chem.MolToSmarts(query)],
        )
    ids = [
        pk
        for pk, smiles in qs.exclude(smiles="")
        .values_list("id", "smiles")
        .iterator(chunk_size=2000)
        if rdkit_utils.has_substructure(smiles, query)
    ]
    return qs.filter(id__in=ids)


def similarity_scores(qs: QuerySet, query_text: str, threshold: float = 0.5) -> dict:
    """{compound_id: tanimoto} for compounds at or above `threshold` (best first)."""
    mol = rdkit_utils.mol_from_input(query_text)
    if cartridge_available():
        table = qs.model._meta.db_table
        expr = (
            f'tanimoto_sml(morganbv_fp(mol_from_smiles("{table}"."smiles"::cstring)), '
            "morganbv_fp(mol_from_smiles(%s::cstring)))"
        )
        smiles = Chem.MolToSmiles(mol)
        # Safe: only our own table name is interpolated; user input is a bound parameter.
        rows = (
            qs.exclude(smiles="")
            .extra(select={"sim": expr}, select_params=[smiles])  # noqa: S610
            .extra(where=[f"{expr} >= %s"], params=[smiles, threshold])  # noqa: S610
            .order_by("-sim")
            .values_list("id", "sim")[:SIMILARITY_LIMIT]
        )
        return dict(rows)
    query_fp = rdkit_utils.fingerprint(mol)
    scored = (
        (pk, rdkit_utils.tanimoto(smiles, query_fp))
        for pk, smiles in qs.exclude(smiles="")
        .values_list("id", "smiles")
        .iterator(chunk_size=2000)
    )
    hits = sorted((s for s in scored if s[1] >= threshold), key=lambda s: -s[1])
    return dict(hits[:SIMILARITY_LIMIT])
