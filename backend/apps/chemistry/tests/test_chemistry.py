import pytest
from django.core.exceptions import ValidationError

from apps.chemistry import pubchem, rdkit_utils
from apps.chemistry.safety import StorageClass, suggest_storage_class, validate_cas

pytestmark = pytest.mark.django_db

PHENOL_MOLFILE = """
  RDKit          2D

  7  7  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0
    1.2990    0.7500    0.0000 C   0  0
    1.2990    2.2500    0.0000 C   0  0
    0.0000    3.0000    0.0000 C   0  0
   -1.2990    2.2500    0.0000 C   0  0
   -1.2990    0.7500    0.0000 C   0  0
    0.0000   -1.5000    0.0000 O   0  0
  1  2  2  0
  2  3  1  0
  3  4  2  0
  4  5  1  0
  5  6  2  0
  6  1  1  0
  1  7  1  0
M  END
"""


# --- pure chemistry -------------------------------------------------------------------------


def test_canonicalisation_gives_same_inchikey():
    a = rdkit_utils.analyse("OCC")
    b = rdkit_utils.analyse("C(O)C")
    assert a.smiles == b.smiles == "CCO"
    assert a.inchikey == b.inchikey == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert a.formula == "C2H6O"
    assert a.mw == pytest.approx(46.069, abs=0.01)


def test_molfile_input():
    info = rdkit_utils.analyse(PHENOL_MOLFILE)
    assert info.smiles == "Oc1ccccc1"


def test_invalid_structure():
    with pytest.raises(rdkit_utils.InvalidStructure):
        rdkit_utils.analyse("C1CC(")


@pytest.mark.parametrize("cas", ["64-17-5", "7732-18-5", "108-95-2"])
def test_valid_cas(cas):
    validate_cas(cas)


@pytest.mark.parametrize("cas", ["64-17-6", "6417-5", "abc"])
def test_invalid_cas(cas):
    with pytest.raises(ValidationError):
        validate_cas(cas)


def test_storage_class_suggestion():
    assert suggest_storage_class(["H225", "H319"]) == StorageClass.FLAMMABLE_LIQUID
    assert suggest_storage_class(["H250", "H225"]) == StorageClass.PYROPHORIC
    assert suggest_storage_class(["H314"]) == StorageClass.CORROSIVE
    assert suggest_storage_class(["H319"]) == StorageClass.GENERAL


# --- API ------------------------------------------------------------------------------------


@pytest.fixture
def contributor(api, make_user, member_of):
    user = make_user("chemist@example.org")
    member_of(user)
    api.force_authenticate(user)
    return user


def test_create_compound_from_structure(api, contributor):
    res = api.post(
        "/api/compounds/",
        {"name": "Ethanol", "cas": "64-17-5", "structure": "OCC", "h_statements": ["H225"]},
        format="json",
    )
    assert res.status_code == 201, res.json()
    data = res.json()
    assert data["formula"] == "C2H6O"
    assert data["inchikey"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert data["storage_class"] == "flam_liquid"  # suggested from H225


def test_duplicate_structure_is_rejected(api, contributor, compound):
    existing = compound("Ethanol", "CCO")
    res = api.post("/api/compounds/", {"name": "EtOH", "structure": "OCC"}, format="json")
    assert res.status_code == 400
    assert res.json()["existing_id"] == [str(existing.id)]


def test_viewer_only_user_cannot_create(api, make_user, member_of):
    viewer = make_user("viewer@example.org")
    member_of(viewer, "viewer")
    api.force_authenticate(viewer)
    assert api.post("/api/compounds/", {"name": "X"}, format="json").status_code == 403
    assert api.get("/api/compounds/").status_code == 200


def test_text_search(api, contributor, compound):
    compound("Ethanol", "CCO", cas="64-17-5", synonyms=["ethyl alcohol"])
    compound("Toluene", "Cc1ccccc1", cas="108-88-3")
    names = lambda r: [c["name"] for c in r.json()["results"]]  # noqa: E731
    assert names(api.get("/api/compounds/?q=64-17-5")) == ["Ethanol"]
    assert names(api.get("/api/compounds/?q=ethyl alcohol")) == ["Ethanol"]
    assert names(api.get("/api/compounds/?q=tolu")) == ["Toluene"]


def test_substructure_search(api, contributor, compound):
    compound("Phenol", "Oc1ccccc1")
    compound("Toluene", "Cc1ccccc1")
    compound("Ethanol", "CCO")
    compound("Celite")  # no structure
    res = api.get("/api/compounds/", {"substructure": "c1ccccc1"})
    assert res.status_code == 200
    assert sorted(c["name"] for c in res.json()["results"]) == ["Phenol", "Toluene"]
    # molfile query: phenol substructure only matches phenol
    res = api.get("/api/compounds/", {"substructure": PHENOL_MOLFILE})
    assert [c["name"] for c in res.json()["results"]] == ["Phenol"]


def test_similarity_search_is_ranked(api, contributor, compound):
    compound("Toluene", "Cc1ccccc1")
    compound("Ethylbenzene", "CCc1ccccc1")
    compound("Ethanol", "CCO")
    res = api.get("/api/compounds/", {"similar": "Cc1ccccc1", "threshold": "0.3"})
    results = res.json()["results"]
    assert results[0]["name"] == "Toluene"
    assert results[0]["similarity"] == 1.0
    assert "Ethanol" not in [r["name"] for r in results]


def test_postgres_uses_rdkit_cartridge():
    """In CI (PostgreSQL + RDKit image) the fast cartridge path must be active."""
    from django.db import connection

    from apps.chemistry import search

    if connection.vendor != "postgresql":
        pytest.skip("SQLite uses the Python fallback")
    search.cartridge_available.cache_clear()
    assert search.cartridge_available()


def test_invalid_query_structure_gives_400(api, contributor):
    assert api.get("/api/compounds/", {"substructure": "C1CC("}).status_code == 400


def test_depict_returns_svg(api, contributor, compound):
    c = compound("Phenol", "Oc1ccccc1")
    res = api.get(f"/api/compounds/{c.id}/depict/")
    assert res.status_code == 200
    assert res["Content-Type"] == "image/svg+xml"
    assert b"<svg" in res.content


def test_analyse_endpoint(api, contributor):
    res = api.post("/api/chem/analyse/", {"structure": "c1ccccc1O"}, format="json")
    assert res.status_code == 200
    assert res.json()["formula"] == "C6H6O"
    assert res.json()["svg"].lstrip().startswith("<?xml") or "<svg" in res.json()["svg"]


# --- PubChem (network mocked) ---------------------------------------------------------------

GHS_VIEW = {
    "Record": {
        "Section": [
            {
                "Information": [
                    {
                        "Name": "Pictogram(s)",
                        "Value": {
                            "StringWithMarkup": [
                                {
                                    "String": "  ",
                                    "Markup": [
                                        {
                                            "URL": "https://pubchem.ncbi.nlm.nih.gov/images/ghs/GHS02.svg"
                                        },
                                        {
                                            "URL": "https://pubchem.ncbi.nlm.nih.gov/images/ghs/GHS07.svg"
                                        },
                                    ],
                                }
                            ]
                        },
                    },
                    {"Name": "Signal", "Value": {"StringWithMarkup": [{"String": "Danger"}]}},
                    {
                        "Name": "GHS Hazard Statements",
                        "Value": {
                            "StringWithMarkup": [
                                {"String": "H225 (100%): Highly Flammable liquid and vapor"},
                                {"String": "H319 (99%): Causes serious eye irritation"},
                            ]
                        },
                    },
                    {
                        "Name": "Precautionary Statement Codes",
                        "Value": {"StringWithMarkup": [{"String": "P210, P233, P305+P351+P338"}]},
                    },
                ]
            }
        ]
    }
}


def fake_fetch(url, data=None):
    if "/property/" in url:
        return {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 702,
                        "Title": "Ethanol",
                        "IUPACName": "ethanol",
                        "MolecularFormula": "C2H6O",
                        "MolecularWeight": "46.07",
                        "SMILES": "CCO",
                        "InChIKey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
                    }
                ]
            }
        }
    if "/synonyms/" in url:
        return {
            "InformationList": {
                "Information": [{"Synonym": ["ethanol", "64-17-5", "ethyl alcohol"]}]
            }
        }
    if "pug_view" in url:
        return GHS_VIEW
    raise AssertionError(url)


def test_lookup_disabled_by_default(api, contributor):
    res = api.get("/api/compounds/lookup/", {"q": "64-17-5"})
    assert res.status_code == 403


def test_lookup_parses_pubchem(api, contributor, settings, monkeypatch, compound):
    settings.CHEMTLAB = {**settings.CHEMTLAB, "ALLOW_EXTERNAL_LOOKUPS": True}
    monkeypatch.setattr(pubchem, "fetch_json", fake_fetch)
    existing = compound("Ethanol", "CCO")
    res = api.get("/api/compounds/lookup/", {"q": "64-17-5"})
    assert res.status_code == 200
    data = res.json()
    assert data["cas"] == "64-17-5"
    assert data["ghs_pictograms"] == ["GHS02", "GHS07"]
    assert data["signal_word"] == "danger"
    assert data["h_statements"] == ["H225", "H319"]
    assert data["p_statements"] == ["P210", "P233", "P305+P351+P338"]
    assert data["existing_id"] == str(existing.id)
