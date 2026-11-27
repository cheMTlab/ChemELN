import pytest
from django.core.management import CommandError, call_command


@pytest.mark.django_db
def test_health_is_public(api):
    res = api.get("/api/health/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.django_db
def test_config_is_public_and_private_by_default(api):
    data = api.get("/api/config/").json()
    assert data["structure_editor"] == "ketcher"
    assert data["external_lookups"] is False
    assert data["ai_enabled"] is False
    assert data["open_signup"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/api/me/", "/api/groups/", "/api/institutions/"])
def test_api_requires_login(api, url):
    assert api.get(url).status_code == 403


@pytest.mark.django_db
def test_doctor_passes_with_strong_secret(settings, capsys):
    settings.SECRET_KEY = "x" * 60
    call_command("doctor")
    assert "healthy" in capsys.readouterr().out


@pytest.mark.django_db
def test_doctor_fails_on_default_secret_in_production(settings):
    settings.DEBUG = False
    settings.SECRET_KEY = "change-me-in-production"
    with pytest.raises(CommandError):
        call_command("doctor")


@pytest.mark.django_db
def test_openapi_schema_builds(api, make_user):
    api.force_authenticate(make_user())
    res = api.get("/api/schema/")
    assert res.status_code == 200
