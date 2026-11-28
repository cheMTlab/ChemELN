import pytest

from apps.inventory.models import Container
from apps.orders.models import CostCentre, Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def people(make_user, member_of):
    member = make_user("member@example.org")
    pi = make_user("pi@example.org")
    buyer = make_user("buyer@example.org", capabilities=["purchasing"])
    outsider = make_user("outsider@example.org")
    member_of(member)
    member_of(pi, "pi")
    return {"member": member, "pi": pi, "buyer": buyer, "outsider": outsider}


def _order(api, group, compound, **extra):
    data = {
        "group": str(group.id),
        "compound": str(compound.id),
        "package_amount": "500",
        "package_unit": "mL",
        "quantity": 2,
        "unit_price": "40.00",
        "supplier_name": "Acme",
        **extra,
    }
    res = api.post("/api/orders/", data, format="json")
    assert res.status_code == 201, res.json()
    return res.json()


def _act(api, oid, action, **extra):
    return api.post(f"/api/orders/{oid}/transition/", {"action": action, **extra}, format="json")


def test_full_order_lifecycle(api, people, group, compound, lab):
    ethanol = compound("Ethanol", "CCO")
    api.force_authenticate(people["member"])
    order = _order(api, group, ethanol)
    assert order["number"].startswith("PO-")
    assert order["status"] == "draft"
    assert order["allowed_actions"] == ["submit", "cancel"]

    assert _act(api, order["id"], "submit").json()["status"] == "submitted"
    # members cannot approve
    assert _act(api, order["id"], "approve").status_code == 403

    api.force_authenticate(people["pi"])
    to_approve = api.get("/api/orders/", {"to_approve": "1"}).json()["results"]
    assert [o["id"] for o in to_approve] == [order["id"]]
    assert _act(api, order["id"], "approve").json()["status"] == "approved"

    api.force_authenticate(people["buyer"])  # central purchasing sees every group's orders
    res = _act(api, order["id"], "place", po_number="4500012345")
    assert res.json()["status"] == "ordered"
    assert res.json()["po_number"] == "4500012345"

    api.force_authenticate(people["member"])
    res = api.post(
        f"/api/orders/{order['id']}/receive/",
        {"quantity": 1, "location": str(lab["flam"].id), "lot_number": "L42"},
        format="json",
    )
    assert res.status_code == 201, res.json()
    assert len(res.json()) == 1
    o = api.get(f"/api/orders/{order['id']}/").json()
    assert o["status"] == "partial"
    api.post(f"/api/orders/{order['id']}/receive/", {"quantity": 1}, format="json")
    o = api.get(f"/api/orders/{order['id']}/").json()
    assert o["status"] == "received"
    assert len(o["container_barcodes"]) == 2
    c = Container.objects.get(barcode=o["container_barcodes"][0])
    assert c.lot_number == "L42" and c.supplier == "Acme" and c.group == group
    events = api.get(f"/api/orders/{order['id']}/events/").json()
    assert [e["to_status"] for e in events] == [
        "submitted",
        "approved",
        "ordered",
        "partial",
        "received",
    ]


def test_pi_order_is_auto_approved(api, people, group, compound):
    api.force_authenticate(people["pi"])
    order = _order(api, group, compound("Toluene", "Cc1ccccc1"))
    assert _act(api, order["id"], "submit").json()["status"] == "approved"


def test_budget_is_enforced(api, people, group, compound):
    cc = CostCentre.objects.create(group=group, code="ERC-1", name="Grant", budget=50)
    api.force_authenticate(people["member"])
    order = _order(api, group, compound("Ethanol", "CCO"), cost_centre=str(cc.id))  # 80 €
    _act(api, order["id"], "submit")
    api.force_authenticate(people["pi"])
    res = _act(api, order["id"], "approve")
    assert res.status_code == 400 and "Over budget" in res.json()["detail"]
    assert _act(api, order["id"], "approve", override_budget=True).status_code == 200
    assert api.get(f"/api/cost-centres/{cc.id}/").json()["remaining"] == "-30.00"


def test_reject_needs_reason_and_outsiders_see_nothing(api, people, group, compound):
    api.force_authenticate(people["member"])
    order = _order(api, group, compound("Ethanol", "CCO"))
    _act(api, order["id"], "submit")
    api.force_authenticate(people["pi"])
    assert _act(api, order["id"], "reject").status_code == 400
    res = _act(api, order["id"], "reject", note="Use the stock in Lab 102")
    assert res.json()["status"] == "rejected"
    api.force_authenticate(people["outsider"])
    assert api.get("/api/orders/").json()["count"] == 0
    assert (
        api.post(
            "/api/orders/",
            {"group": str(group.id), "item_name": "X", "package_amount": 1, "package_unit": "g"},
            format="json",
        ).status_code
        == 400
    )


def test_reorder_from_container(api, people, group, compound):
    c = Container.objects.create(
        compound=compound("Ethanol", "CCO"),
        group=group,
        amount=100,
        unit="mL",
        supplier="Acme",
        catalog_number="E-1",
    )
    api.force_authenticate(people["member"])
    res = api.post(f"/api/containers/{c.id}/reorder/")
    assert res.status_code == 201
    o = Order.objects.get(pk=res.json()["id"])
    assert o.catalog_number == "E-1" and o.status == "draft"
