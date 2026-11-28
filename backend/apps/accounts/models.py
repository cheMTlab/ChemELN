import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create_user(email, password, **extra)


class Capability(models.TextChoices):
    """Instance-wide powers, on top of the per-group roles (admin > pi > member > viewer).

    Inspired by Open Enventory's permission bits. Instance staff implicitly hold all of them.
    """

    USER_MANAGER = "user_manager", "Manage users and group memberships"
    PURCHASING = "purchasing", "Central purchasing: place and receive orders"
    ORDER_APPROVER = "order_approver", "Approve orders for any group"
    SAFETY_OFFICER = "safety_officer", "Safety officer: see all inventory and safety reports"
    INVENTORY_MANAGER = "inventory_manager", "Manage shared locations and any container"
    BIOSAFETY_OFFICER = "biosafety_officer", "Biosafety officer: see all strains and plasmids"


orcid_validator = RegexValidator(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", "Format: 0000-0000-0000-0000")


class User(AbstractUser):
    """A person using CheMTlab. Logs in with email (or institutional SSO)."""

    username = None
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True)
    orcid = models.CharField("ORCID iD", max_length=19, blank=True, validators=[orcid_validator])
    initials = models.CharField(
        max_length=6, blank=True, help_text="Prefix for notebook codes, e.g. AB → AB-0001"
    )
    job_title = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    capabilities = models.JSONField(default=list, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        ordering = ["last_name", "first_name", "email"]

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.email

    def has_capability(self, capability: str) -> bool:
        if not self.is_active:
            return False
        return self.is_staff or capability in (self.capabilities or [])

    def notebook_prefix(self) -> str:
        if self.initials:
            return self.initials.upper()
        parts = [p for p in (self.first_name, self.last_name) if p]
        if parts:
            return "".join(p[0] for p in parts).upper()
        return self.email[:2].upper()
