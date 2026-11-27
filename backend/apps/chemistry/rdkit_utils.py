"""Thin wrapper around RDKit: parsing, canonicalisation, properties, fingerprints, depiction."""

from dataclasses import dataclass

from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import Descriptors, rdFingerprintGenerator, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

RDLogger.DisableLog("rdApp.*")

_morgan = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


class InvalidStructure(ValueError):
    pass


def _is_molblock(text: str) -> bool:
    return "M  END" in text or "V2000" in text or "V3000" in text


def mol_from_input(text: str) -> Chem.Mol:
    """Parse SMILES or an MDL molfile. Raises InvalidStructure.

    Molfiles are never stripped: their 3 header lines are positional and the first one is often
    empty. If a client trimmed that empty line away, we retry with it restored.
    """
    if _is_molblock(text or ""):
        mol = Chem.MolFromMolBlock(text) or Chem.MolFromMolBlock("\n" + text.lstrip("\r\n"))
    else:
        text = (text or "").strip()
        if not text:
            raise InvalidStructure("Empty structure")
        mol = Chem.MolFromSmiles(text)
    if mol is None or mol.GetNumAtoms() == 0:
        raise InvalidStructure("Could not read the structure")
    return mol


def query_mol(text: str) -> Chem.Mol:
    """A substructure query: molfile, SMILES, or SMARTS."""
    if _is_molblock(text or ""):
        return mol_from_input(text)
    text = (text or "").strip()
    mol = Chem.MolFromSmiles(text) or Chem.MolFromSmarts(text)
    if mol is None or mol.GetNumAtoms() == 0:
        raise InvalidStructure("Could not read the query structure")
    return mol


@dataclass(frozen=True)
class StructureInfo:
    smiles: str
    inchi: str
    inchikey: str
    formula: str
    mw: float
    exact_mass: float
    molfile: str


def analyse(text: str) -> StructureInfo:
    mol = mol_from_input(text)
    inchi = Chem.MolToInchi(mol) or ""
    return StructureInfo(
        smiles=Chem.MolToSmiles(mol),
        inchi=inchi,
        inchikey=Chem.InchiToInchiKey(inchi) if inchi else "",
        formula=rdMolDescriptors.CalcMolFormula(mol),
        mw=round(Descriptors.MolWt(mol), 4),
        exact_mass=round(Descriptors.ExactMolWt(mol), 6),
        molfile=text if _is_molblock(text) else Chem.MolToMolBlock(mol),
    )


def has_substructure(smiles: str, query: Chem.Mol) -> bool:
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    return bool(mol and mol.HasSubstructMatch(query))


def fingerprint(mol: Chem.Mol):
    return _morgan.GetFingerprint(mol)


def tanimoto(smiles: str, query_fp) -> float:
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        return 0.0
    return DataStructs.TanimotoSimilarity(fingerprint(mol), query_fp)


def to_svg(text: str, width: int = 300, height: int = 200) -> str:
    mol = mol_from_input(text)
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = drawer.drawOptions()
    opts.clearBackground = False
    opts.addStereoAnnotation = True
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()
