"""Institution → Department → Research group, with per-group roles.

Instance administrators are Django staff users. Everything else is decided by the user's
role in a research group (admin > pi > member > viewer).
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Institution(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=50, blank=True)
    ror_id = models.URLField(
        "ROR ID", blank=True, help_text="Research Organization Registry, e.g. https://ror.org/..."
    )
    country = models.CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.short_name or self.name


class Department(BaseModel):
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="departments"
    )
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["institution__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "name"], name="uniq_department_name")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.institution})"


class ResearchGroup(BaseModel):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="groups")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Membership", related_name="research_groups"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["department", "name"], name="uniq_group_name")
        ]

    def __str__(self) -> str:
        return self.name


class Role(models.TextChoices):
    ADMIN = "admin", "Group admin"
    PI = "pi", "Principal investigator"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


ROLE_RANK = {Role.VIEWER: 0, Role.MEMBER: 1, Role.PI: 2, Role.ADMIN: 3}


class Membership(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    group = models.ForeignKey(ResearchGroup, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        ordering = ["group__name", "user__email"]
        constraints = [models.UniqueConstraint(fields=["user", "group"], name="uniq_membership")]

    def __str__(self) -> str:
        return f"{self.user} in {self.group} ({self.role})"
