from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.eln import services
from apps.eln.models import Signature
from apps.inventory.models import Container

pytestmark = pytest.mark.django_db


@pytest.fixture
def chemist(api, make_user, member_of):
    u = make_user("ada@example.org", first_name="Ada", last_name="Bloggs")
    member_of(u)
    api.force_authenticate(u)
    return u


def _exp(api, group, **extra):
    res = api.post(
        "/api/experiments/",
        {"group": str(group.id), "title": "Esterification", **extra},
        format="json",
    )
    assert res.status_code == 201, res.json()
    return res.json()


def test_codes_follow_initials(api, chemist, group):
    assert _exp(api, group)["code"] == "AB-0001"
    assert _exp(api, group)["code"] == "AB-0002"


def test_reaction_import_and_stoichiometry(api, chemist, group):
    exp = _exp(api, group)
    res = api.post(
        f"/api/experiments/{exp['id']}/import-reaction/",
        {"reaction": "CC(=O)O.OCC>>CC(=O)OCC"},
        format="json",
    )
    assert res.status_code == 200, res.json()
    comps = res.json()["components"]
    assert [c["role"] for c in comps] == ["reactant", "reactant", "product"]
    acid, ethanol, ester = comps
    assert acid["is_limiting"]
    # 10 mmol acetic acid, 3 eq ethanol (d 0.789)
    api.patch(f"/api/reaction-components/{acid['id']}/", {"mmol": 10}, format="json")
    api.patch(
        f"/api/reaction-components/{ethanol['id']}/",
        {"equivalents": 3, "density": 0.789},
        format="json",
    )
    api.patch(f"/api/reaction-components/{ester['id']}/", {"actual_mass_mg": 705}, format="json")
    rows = {c["id"]: c for c in api.get(f"/api/experiments/{exp['id']}/").json()["components"]}
    assert rows[acid["id"]]["mass_mg"] == pytest.approx(600.5, abs=0.5)
    assert rows[ethanol["id"]]["mmol"] == pytest.approx(30)
    assert rows[ethanol["id"]]["volume_ml"] == pytest.approx(30 * 46.069 / 1000 / 0.789, rel=1e-3)
    assert rows[ester["id"]]["mass_mg"] == pytest.approx(881.1, abs=0.5)  # theoretical
    assert rows[ester["id"]]["yield_percent"] == pytest.approx(80.0, abs=0.2)


def test_inventory_deduction_and_product_registration(api, chemist, group, compound, lab):
    ethanol = compound("Ethanol", "CCO", density=Decimal("0.789"))
    bottle = Container.objects.create(compound=ethanol, group=group, amount=100, unit="mL")
    exp = _exp(api, group)
    r = api.post(
        "/api/reaction-components/",
        {
            "experiment": exp["id"],
            "role": "reactant",
            "container": str(bottle.id),
            "volume_ml": 5,
            "is_limiting": True,
        },
        format="json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["name"] == "Ethanol"  # filled from the container
    p = api.post(
        "/api/reaction-components/",
        {
            "experiment": exp["id"],
            "role": "product",
            "smiles": "CCOC(C)=O",
            "actual_mass_mg": 250,
        },
        format="json",
    ).json()

    res = api.post(f"/api/experiments/{exp['id']}/deduct-inventory/")
    assert res.status_code == 200, res.json()
    bottle.refresh_from_db()
    assert bottle.amount == Decimal("95")
    # second call does nothing
    api.post(f"/api/experiments/{exp['id']}/deduct-inventory/")
    bottle.refresh_from_db()
    assert bottle.amount == Decimal("95")

    res = api.post(
        f"/api/reaction-components/{p['id']}/register/",
        {"location": str(lab["shelf"].id)},
        format="json",
    )
    assert res.status_code == 201, res.json()
    assert res.json()["amount"] == "250.0000" and res.json()["lot_number"] == exp["code"]


def test_signing_locks_and_witness_rules(api, chemist, group, make_user, member_of):
    exp = _exp(api, group, procedure="Mix and heat.")
    f = SimpleUploadedFile("nmr.jdx", b"##TITLE=test")
    assert (
        api.post(
            "/api/attachments/",
            {"experiment": exp["id"], "file": f, "kind": "NMR"},
            format="multipart",
        ).status_code
        == 201
    )
    res = api.post(f"/api/experiments/{exp['id']}/sign/")
    assert res.status_code == 201, res.json()
    assert (
        api.patch(
            f"/api/experiments/{exp['id']}/", {"procedure": "changed"}, format="json"
        ).status_code
        == 400
    )
    assert (
        api.patch(
            f"/api/experiments/{exp['id']}/", {"status": "completed"}, format="json"
        ).status_code
        == 200
    )
    # Comments after signing become addenda
    c = api.post(
        "/api/comments/", {"experiment": exp["id"], "text": "Typo in step 2"}, format="json"
    ).json()
    assert c["is_addendum"] is True
    # Own witness refused; colleague accepted
    assert api.post(f"/api/experiments/{exp['id']}/witness/").status_code == 400
    colleague = make_user("bob@example.org")
    member_of(colleague)
    api.force_authenticate(colleague)
    assert api.post(f"/api/experiments/{exp['id']}/witness/").status_code == 201
    v = api.get(f"/api/experiments/{exp['id']}/verify/").json()
    assert v["intact"] is True and len(v["signatures"]) == 2
    assert api.get("/api/eln/ledger/").json() == {"intact": True, "length": 2}


def test_tampering_is_detected(api, chemist, group):
    exp = _exp(api, group, procedure="Original")
    api.post(f"/api/experiments/{exp['id']}/sign/")
    from apps.eln.models import Experiment

    Experiment.objects.filter(pk=exp["id"]).update(procedure="Forged")  # bypasses the API
    assert api.get(f"/api/experiments/{exp['id']}/verify/").json()["intact"] is False
    Signature.objects.update(prev_hash="x")
    assert services.verify_ledger()["intact"] is False


def test_viewer_reads_but_cannot_write(api, make_user, member_of, group, chemist):
    exp = _exp(api, group)
    viewer = make_user("v@example.org")
    member_of(viewer, "viewer")
    api.force_authenticate(viewer)
    assert api.get(f"/api/experiments/{exp['id']}/").status_code == 200
    assert (
        api.patch(f"/api/experiments/{exp['id']}/", {"title": "x"}, format="json").status_code
        == 403
    )
    outsider = make_user("o@example.org")
    api.force_authenticate(outsider)
    assert api.get(f"/api/experiments/{exp['id']}/").status_code == 404


def test_duplicate_and_search(api, chemist, group):
    exp = _exp(api, group)
    api.post(
        f"/api/experiments/{exp['id']}/import-reaction/",
        {"reaction": "CC(=O)O.OCC>>CC(=O)OCC"},
        format="json",
    )
    dup = api.post(f"/api/experiments/{exp['id']}/duplicate/").json()
    assert dup["title"].endswith("(repeat)") and len(dup["components"]) == 3
    assert api.get("/api/experiments/", {"q": "repeat"}).json()["count"] == 1
