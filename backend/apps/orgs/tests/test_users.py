import pytest

pytestmark = pytest.mark.django_db


def test_me_reports_capabilities(api, make_user):
    u = make_user(capabilities=["purchasing", "bogus"])
    api.force_authenticate(u)
    assert api.get("/api/me/").json()["capabilities"] == ["purchasing"]
    admin = make_user("root@example.org", is_staff=True)
    api.force_authenticate(admin)
    assert "user_manager" in api.get("/api/me/").json()["capabilities"]


def test_user_management(api, make_user, group):
    plain = make_user("plain@example.org")
    manager = make_user("hr@example.org", capabilities=["user_manager"])

    api.force_authenticate(plain)
    listing = api.get("/api/users/").json()["results"]
    assert "capabilities" not in listing[0]  # summary only
    assert api.post("/api/users/", {"email": "new@example.org"}, format="json").status_code == 403

    api.force_authenticate(manager)
    res = api.post(
        "/api/users/",
        {"email": "new@example.org", "first_name": "Nia", "capabilities": ["purchasing"]},
        format="json",
    )
    assert res.status_code == 201, res.json()
    new_id = res.json()["id"]
    # managers cannot make instance admins
    assert api.patch(f"/api/users/{new_id}/", {"is_staff": True}, format="json").status_code == 400
    # they can add people to any group, including as group admin
    res = api.post(
        f"/api/groups/{group.id}/members/",
        {"user_email": "new@example.org", "role": "admin"},
        format="json",
    )
    assert res.status_code == 201, res.json()
    assert (
        api.patch(f"/api/users/{new_id}/", {"is_active": False}, format="json").json()["is_active"]
        is False
    )
    assert (
        api.patch(f"/api/users/{manager.id}/", {"is_active": False}, format="json").status_code
        == 400
    )
    assert api.delete(f"/api/users/{new_id}/").status_code == 405
