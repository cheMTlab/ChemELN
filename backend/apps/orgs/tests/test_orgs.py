import pytest

pytestmark = pytest.mark.django_db


def test_me_lists_memberships(api, make_user, member_of, group):
    user = make_user()
    member_of(user, "pi")
    api.force_authenticate(user)
    data = api.get("/api/me/").json()
    assert data["email"] == "user@example.org"
    [m] = data["memberships"]
    assert {k: m[k] for k in ("group_id", "group_name", "role")} == {
        "group_id": str(group.id),
        "group_name": "Synthesis Lab",
        "role": "pi",
    }


def test_users_only_see_their_groups(api, make_user, member_of, group):
    outsider = make_user("out@example.org")
    insider = make_user("in@example.org")
    member_of(insider)

    api.force_authenticate(outsider)
    assert api.get("/api/groups/").json()["count"] == 0
    assert api.get(f"/api/groups/{group.id}/members/").status_code == 404

    api.force_authenticate(insider)
    assert api.get("/api/groups/").json()["count"] == 1


def test_only_staff_create_groups(api, make_user, group):
    payload = {"department": str(group.department_id), "name": "New Lab"}
    api.force_authenticate(make_user())
    assert api.post("/api/groups/", payload).status_code == 403
    api.force_authenticate(make_user("staff@example.org", is_staff=True))
    assert api.post("/api/groups/", payload).status_code == 201


def test_member_cannot_add_members_but_pi_can(api, make_user, member_of, group):
    member = make_user("m@example.org")
    pi = make_user("pi@example.org")
    make_user("new@example.org")
    member_of(member)
    member_of(pi, "pi")
    url = f"/api/groups/{group.id}/members/"

    api.force_authenticate(member)
    assert api.post(url, {"user_email": "new@example.org"}).status_code == 403

    api.force_authenticate(pi)
    res = api.post(url, {"user_email": "new@example.org", "role": "member"})
    assert res.status_code == 201
    assert res.json()["user"]["email"] == "new@example.org"


def test_pi_cannot_grant_admin(api, make_user, member_of, group):
    pi = make_user("pi@example.org")
    make_user("new@example.org")
    member_of(pi, "pi")
    api.force_authenticate(pi)
    res = api.post(
        f"/api/groups/{group.id}/members/", {"user_email": "new@example.org", "role": "admin"}
    )
    assert res.status_code == 403


def test_institutions_read_only_for_non_staff(api, make_user, group):
    api.force_authenticate(make_user())
    assert api.get("/api/institutions/").status_code == 200
    assert api.post("/api/institutions/", {"name": "X"}).status_code == 403
