import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orgs.models import Department, Institution, Membership, ResearchGroup


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db):
    def _make(email="user@example.org", **extra):
        return User.objects.create_user(email=email, password="a-Strong-pass-123", **extra)

    return _make


@pytest.fixture
def group(db):
    inst = Institution.objects.create(name="Example University", short_name="EXU")
    dept = Department.objects.create(institution=inst, name="Chemistry")
    return ResearchGroup.objects.create(department=dept, name="Synthesis Lab")


@pytest.fixture
def compound(db):
    from apps.chemistry.models import Compound

    def _make(name, smiles="", **extra):
        c = Compound(name=name, **extra)
        if smiles:
            c.set_structure(smiles)
        c.save()
        return c

    return _make


@pytest.fixture
def lab(db, group):
    """Location tree: Main Site / Chem Building / Lab 101 / {Flammables cabinet, Shelf A}."""
    from apps.locations.models import Location

    site = Location.objects.create(name="Main Site", kind="site")
    building = Location.objects.create(name="Chem Building", kind="building", parent=site)
    room = Location.objects.create(name="Lab 101", kind="room", parent=building, group=group)
    flam = Location.objects.create(
        name="Flammables cabinet",
        kind="cabinet",
        parent=room,
        group=group,
        allowed_storage_classes=["flam_liquid"],
    )
    shelf = Location.objects.create(name="Shelf A", kind="shelf", parent=room, group=group)
    return {"site": site, "building": building, "room": room, "flam": flam, "shelf": shelf}


@pytest.fixture
def member_of(group):
    def _add(user, role="member", grp=None):
        return Membership.objects.create(user=user, group=grp or group, role=role)

    return _add
