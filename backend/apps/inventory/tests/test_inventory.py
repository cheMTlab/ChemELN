from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.inventory.models import Container, ContainerEvent
from apps.inventory.units import IncompatibleUnits, convert
from apps.locations.models import Location
from apps.orgs.models import Membership, ResearchGroup

pytestmark = pytest.mark.django_db


@pytest.fixture
def chemist(api, make_user, member_of):
    user = make_user("chemist@example.org")
    member_of(user)
    api.force_authenticate(user)
    return user


@pytest.fixture
def ethanol(compound):
    return compound(
        "Ethanol",
        "CCO",
        cas="64-17-5",
        storage_class="flam_liquid",
        ghs_pictograms=["GHS02"],
        signal_word="danger",
    )


def new_container(api, group, compound, **extra):
    payload = {
        "compound": str(compound.id),
        "group": str(group.id),
        "amount": "1.000",
        "unit": "g",
        **extra,
    }
    return api.post("/api/containers/", payload, format="json")


# --- units ----------------------------------------------------------------------------------


def test_unit_conversion():
    assert convert(Decimal("500"), "mg", "g") == Decimal("0.5")
    assert convert(Decimal("2"), "L", "mL") == Decimal("2000")
    with pytest.raises(IncompatibleUnits):
        convert(Decimal("1"), "g", "mL")


# --- locations ------------------------------------------------------------------------------


def test_location_paths_follow_renames(lab):
    assert lab["shelf"].path == "Main Site / Chem Building / Lab 101 / Shelf A"
    lab["building"].name = "Building B"
    lab["building"].save()
    lab["shelf"].refresh_from_db()
    assert lab["shelf"].path == "Main Site / Building B / Lab 101 / Shelf A"


def test_location_cycle_rejected(api, make_user, lab):
    api.force_authenticate(make_user("staff@example.org", is_staff=True))
    res = api.patch(
        f"/api/locations/{lab['site'].id}/", {"parent": str(lab["shelf"].id)}, format="json"
    )
    assert res.status_code == 400


def test_only_group_pi_creates_group_locations(api, make_user, member_of, group, lab):
    member, pi = make_user("m@example.org"), make_user("pi@example.org")
    member_of(member)
    member_of(pi, "pi")
    payload = {
        "name": "Fridge 1",
        "kind": "fridge",
        "parent": str(lab["room"].id),
        "group": str(group.id),
    }
    api.force_authenticate(member)
    assert api.post("/api/locations/", payload, format="json").status_code == 403
    api.force_authenticate(pi)
    assert api.post("/api/locations/", payload, format="json").status_code == 201


# --- containers -----------------------------------------------------------------------------


def test_create_container_generates_barcode_and_event(api, chemist, group, ethanol, lab):
    res = new_container(api, group, ethanol, location=str(lab["flam"].id))
    assert res.status_code == 201, res.json()
    data = res.json()
    assert data["barcode"].startswith("CT") and len(data["barcode"]) == 10
    assert data["initial_amount"] == "1.0000"
    assert data["owner_name"] == "chemist@example.org"
    assert data["storage_warning"] == ""
    assert ContainerEvent.objects.filter(container_id=data["id"], kind="created").exists()


def test_storage_warning(api, chemist, group, compound, lab):
    acid = compound("Sulfuric acid", "OS(=O)(=O)O", storage_class="corrosive")
    data = new_container(api, group, acid, location=str(lab["flam"].id)).json()
    assert "should not be stored" in data["storage_warning"]


def test_cannot_create_in_foreign_group(api, chemist, ethanol, group):
    other = ResearchGroup.objects.create(department=group.department, name="Other Lab")
    assert new_container(api, other, ethanol).status_code == 400


def test_viewer_cannot_create(api, make_user, member_of, group, ethanol):
    viewer = make_user("v@example.org")
    member_of(viewer, "viewer")
    api.force_authenticate(viewer)
    assert new_container(api, group, ethanol).status_code == 400


def test_use_with_unit_conversion_and_empty(api, chemist, group, ethanol):
    cid = new_container(api, group, ethanol).json()["id"]
    res = api.post(f"/api/containers/{cid}/use/", {"amount": "250", "unit": "mg"}, format="json")
    assert res.status_code == 200
    assert res.json()["amount"] == "0.7500"
    assert res.json()["opened_date"] == date.today().isoformat()

    res = api.post(f"/api/containers/{cid}/use/", {"amount": "2", "unit": "g"}, format="json")
    assert res.status_code == 400  # more than is left

    res = api.post(f"/api/containers/{cid}/use/", {"amount": "1", "unit": "mL"}, format="json")
    assert res.status_code == 400  # incompatible unit

    res = api.post(f"/api/containers/{cid}/use/", {"amount": "750", "unit": "mg"}, format="json")
    assert res.json()["status"] == "empty"
    kinds = [e["kind"] for e in api.get(f"/api/containers/{cid}/events/").json()]
    assert kinds.count("used") == 2


def test_move_and_status(api, chemist, group, ethanol, lab):
    cid = new_container(api, group, ethanol).json()["id"]
    res = api.post(
        f"/api/containers/{cid}/move/", {"location": str(lab["shelf"].id)}, format="json"
    )
    assert res.json()["location_path"].endswith("Shelf A")
    res = api.post(f"/api/containers/{cid}/status/", {"status": "disposed"}, format="json")
    assert res.json()["status"] == "disposed"
    # disposed containers are hidden by default
    assert api.get("/api/containers/").json()["count"] == 0
    assert api.get("/api/containers/?status=disposed").json()["count"] == 1


def test_outsider_can_find_but_not_change(api, chemist, make_user, group, ethanol):
    cid = new_container(api, group, ethanol).json()["id"]
    api.force_authenticate(make_user("outsider@example.org"))
    assert api.get("/api/containers/?q=ethanol").json()["count"] == 1
    res = api.post(f"/api/containers/{cid}/use/", {"amount": "1", "unit": "mg"}, format="json")
    assert res.status_code == 403


def test_group_visibility_setting(api, chemist, make_user, group, ethanol, settings):
    new_container(api, group, ethanol)
    settings.CHEMTLAB = {**settings.CHEMTLAB, "INVENTORY_VISIBILITY": "group"}
    api.force_authenticate(make_user("outsider@example.org"))
    assert api.get("/api/containers/").json()["count"] == 0


def test_search_filters(api, chemist, group, ethanol, compound, lab):
    toluene = compound("Toluene", "Cc1ccccc1")
    new_container(api, group, ethanol, location=str(lab["flam"].id))
    new_container(api, group, toluene, location=str(lab["shelf"].id))
    count = lambda **p: api.get("/api/containers/", p).json()["count"]  # noqa: E731
    assert count(location=str(lab["room"].id)) == 2  # includes sub-locations
    assert count(location=str(lab["shelf"].id)) == 1
    assert count(substructure="c1ccccc1") == 1
    assert count(hazard="GHS02") == 1
    barcode = Container.objects.get(compound=toluene).barcode
    assert count(barcode=barcode) == 1


def test_alerts(api, chemist, group, compound):
    ether = compound("Diethyl ether", "CCOCC", is_peroxide_former=True)
    old = date.today() - timedelta(days=400)
    Container.objects.create(
        compound=ether, group=group, amount=1, unit="L", opened_date=old, expiry_date=old
    )
    Container.objects.create(
        compound=ether, group=group, amount=Decimal("0.05"), initial_amount=1, unit="L"
    )
    data = api.get("/api/containers/alerts/").json()
    assert data["expired"]["count"] == 1
    assert data["peroxide_retest"]["count"] == 1
    assert data["low_stock"]["count"] == 1


def test_labels_pdf(api, chemist, group, ethanol):
    ids = [new_container(api, group, ethanol).json()["id"] for _ in range(4)]
    for layout in ("roll-62x29", "a4-3x7"):
        res = api.get("/api/containers/labels/", {"ids": ",".join(ids), "layout": layout})
        assert res.status_code == 200
        assert res.content.startswith(b"%PDF")


def test_history_records_user(api, chemist, group, ethanol):
    cid = new_container(api, group, ethanol).json()["id"]
    api.patch(f"/api/containers/{cid}/", {"lot_number": "LOT42"}, format="json")
    history = Container.objects.get(id=cid).history.all()
    assert history.count() == 2
    assert history.first().history_user == chemist


# --- import ---------------------------------------------------------------------------------

CSV = (
    "Name;CAS;SMILES;Amount;Unit;Location;Supplier;Lot\n"
    "Ethanol;64-17-5;CCO;2,5;L;Main Site/Chem Building/Lab 101/Flammables cabinet;Acme;A1\n"
    "Phenol;108-95-2;Oc1ccccc1;100;g;Main Site / Chem Building / Lab 101 / Shelf A;Acme;B2\n"
)


def upload(api, group, content, name="stock.csv", dry_run=True):
    file = SimpleUploadedFile(name, content.encode())
    return api.post(
        "/api/containers/import/",
        {"file": file, "group": str(group.id), "dry_run": dry_run},
        format="multipart",
    )


def test_import_dry_run_saves_nothing(api, chemist, group, lab):
    res = upload(api, group, CSV)
    assert res.status_code == 200, res.json()
    assert res.json()["created_containers"] == 2
    assert res.json()["errors"] == []
    assert Container.objects.count() == 0


def test_import_creates_and_matches(api, chemist, group, lab, ethanol):
    res = upload(api, group, CSV, dry_run=False).json()
    assert res["created_containers"] == 2
    assert res["matched_compounds"] == 1  # ethanol already existed
    assert res["created_compounds"] == 1
    c = Container.objects.get(compound=ethanol)
    assert c.amount == Decimal("2.5") and c.unit == "L"
    assert c.location == Location.objects.get(name="Flammables cabinet")


def test_import_reports_errors_and_rolls_back(api, chemist, group, lab):
    bad = CSV + "Water;7732-18-6;O;1;L;;;\nMystery;;;abc;g;Nowhere;;\n"
    res = upload(api, group, bad, dry_run=False).json()
    messages = {e["row"]: e["message"] for e in res["errors"]}
    assert "CAS" in messages[3]
    assert "not a number" in messages[4]
    assert Container.objects.count() == 0  # all-or-nothing


def test_import_sdf(api, chemist, group):
    sdf = "Benzene\n  RDKit\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n"
    from rdkit import Chem

    mol = Chem.MolFromSmiles("c1ccccc1")
    mol.SetProp("_Name", "Benzene")
    mol.SetProp("Amount", "500")
    mol.SetProp("Unit", "mL")
    sdf = Chem.MolToMolBlock(mol) + "> <Amount>\n500\n\n> <Unit>\nmL\n\n$$$$\n"
    sdf = "Benzene" + sdf[sdf.index("\n") :]
    res = upload(api, group, sdf, name="stock.sdf", dry_run=False).json()
    assert res["errors"] == [] and res["created_containers"] == 1
    assert Container.objects.get().compound.formula == "C6H6"


def test_import_requires_group_membership(api, chemist, group):
    other = ResearchGroup.objects.create(department=group.department, name="Other Lab")
    assert not Membership.objects.filter(group=other).exists()
    assert upload(api, other, CSV).status_code == 403
