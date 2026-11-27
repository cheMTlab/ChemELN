"""Optional PubChem lookups (off unless CHEMTLAB_ALLOW_EXTERNAL_LOOKUPS=true).

Only the search term (name, CAS or SMILES) is sent to PubChem: never user or inventory data.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

import chemtlab

from .safety import GHS_PICTOGRAMS, H_CODE, P_CODE, is_valid_cas

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest"
PROPERTIES = "Title,IUPACName,MolecularFormula,MolecularWeight,SMILES,IsomericSMILES,InChIKey"
CAS_PATTERN = re.compile(r"^\d{2,7}-\d{2}-\d$")


class LookupDisabled(Exception):
    pass


class NotFound(Exception):
    pass


def fetch_json(url: str, data: bytes | None = None) -> dict:
    req = urllib.request.Request(  # noqa: S310 (fixed https host)
        url,
        data=data,
        headers={"User-Agent": f"CheMTlab/{chemtlab.__version__}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:  # noqa: S310
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NotFound from exc
        raise


def _properties(query: str, kind: str) -> dict:
    if kind == "smiles":
        url = f"{BASE}/pug/compound/smiles/property/{PROPERTIES}/JSON"
        data = urllib.parse.urlencode({"smiles": query}).encode()
        payload = fetch_json(url, data)
    else:
        url = f"{BASE}/pug/compound/name/{urllib.parse.quote(query)}/property/{PROPERTIES}/JSON"
        payload = fetch_json(url)
    props = payload.get("PropertyTable", {}).get("Properties", [])
    if not props:
        raise NotFound
    return props[0]


def _synonyms(cid: int) -> list[str]:
    try:
        payload = fetch_json(f"{BASE}/pug/compound/cid/{cid}/synonyms/JSON")
    except NotFound:
        return []
    info = payload.get("InformationList", {}).get("Information", [])
    return info[0].get("Synonym", []) if info else []


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def parse_ghs(payload: dict) -> dict:
    """Extract pictograms, signal word, H and P codes from a PUG View GHS section."""
    pictograms: list[str] = []
    signal = ""
    h_codes: list[str] = []
    p_codes: list[str] = []
    for node in _walk(payload):
        name = node.get("Name")
        if name not in {
            "Pictogram(s)",
            "Signal",
            "GHS Hazard Statements",
            "Precautionary Statement Codes",
        }:
            continue
        for swm in node.get("Value", {}).get("StringWithMarkup", []):
            text = swm.get("String", "")
            if name == "Pictogram(s)":
                for markup in swm.get("Markup", []):
                    m = re.search(r"(GHS0\d)", markup.get("URL", ""))
                    if m and m.group(1) in GHS_PICTOGRAMS and m.group(1) not in pictograms:
                        pictograms.append(m.group(1))
            elif name == "Signal" and not signal:
                signal = text.strip().lower()
            elif name == "GHS Hazard Statements":
                h_codes += [c for c in H_CODE.findall(text) if c not in h_codes]
            else:
                p_codes += [c for c in P_CODE.findall(text) if c not in p_codes]
    return {
        "ghs_pictograms": sorted(pictograms),
        "signal_word": signal if signal in {"danger", "warning"} else "",
        "h_statements": h_codes,
        "p_statements": p_codes,
    }


def _ghs(cid: int) -> dict:
    url = f"{BASE}/pug_view/data/compound/{cid}/JSON?heading=GHS+Classification"
    try:
        return parse_ghs(fetch_json(url))
    except NotFound:
        return parse_ghs({})


def lookup(query: str, kind: str = "auto") -> dict:
    """Return pre-fill data for a new compound. Raises LookupDisabled / NotFound."""
    if not settings.CHEMTLAB["ALLOW_EXTERNAL_LOOKUPS"]:
        raise LookupDisabled
    query = query.strip()
    if kind == "auto":
        kind = "cas" if CAS_PATTERN.match(query) else "name"
    cache_key = f"pubchem:{kind}:{query}"
    if (hit := cache.get(cache_key)) is not None:
        return hit

    props = _properties(query, kind)
    cid = props["CID"]
    synonyms = _synonyms(cid)
    cas = next((s for s in synonyms if CAS_PATTERN.match(s) and is_valid_cas(s)), "")
    if kind == "cas" and is_valid_cas(query):
        cas = query
    result = {
        "pubchem_cid": cid,
        "name": props.get("Title") or props.get("IUPACName") or query,
        "iupac_name": props.get("IUPACName", ""),
        "formula": props.get("MolecularFormula", ""),
        "mw": float(props["MolecularWeight"]) if props.get("MolecularWeight") else None,
        "smiles": props.get("SMILES") or props.get("IsomericSMILES", ""),
        "inchikey": props.get("InChIKey", ""),
        "cas": cas,
        "synonyms": [s for s in synonyms[:15] if s != cas],
        **_ghs(cid),
    }
    cache.set(cache_key, result, 60 * 60 * 24)
    return result
