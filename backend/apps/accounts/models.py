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


orcid_validator = RegexValidator(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", "Format: 0000-0000-0000-0000")


class User(AbstractUser):
    """A person using CheMTlab. Logs in with email (or institutional SSO)."""

    username = None
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True)
    orcid = models.CharField("ORCID iD", max_length=19, blank=True, validators=[orcid_validator])

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
