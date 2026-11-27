"""Health checks shared by the /api/health endpoint and the `doctor` command."""

from dataclasses import dataclass

from django.conf import settings
from django.db import connection


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    critical: bool = True


def check_database() -> CheckResult:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return CheckResult("database", True, connection.vendor)
    except Exception as exc:  # noqa: BLE001
        return CheckResult("database", False, str(exc))


def check_rdkit_cartridge() -> CheckResult:
    """The RDKit cartridge is needed for structure search (M1). Non-critical in M0."""
    if connection.vendor != "postgresql":
        return CheckResult("rdkit_cartridge", False, "not PostgreSQL", critical=False)
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'rdkit'")
            row = cur.fetchone()
        if row:
            return CheckResult("rdkit_cartridge", True, f"rdkit {row[0]}", critical=False)
        return CheckResult("rdkit_cartridge", False, "extension not installed", critical=False)
    except Exception as exc:  # noqa: BLE001
        return CheckResult("rdkit_cartridge", False, str(exc), critical=False)


def check_secret_key() -> CheckResult:
    weak = settings.SECRET_KEY in {"insecure-dev-key", "change-me-in-production"}
    if settings.DEBUG:
        return CheckResult("secret_key", True, "debug mode", critical=False)
    return CheckResult("secret_key", not weak, "weak default key!" if weak else "set")


def run_all() -> list[CheckResult]:
    return [check_database(), check_rdkit_cartridge(), check_secret_key()]
