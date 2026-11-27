from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import ROLE_RANK, Membership, ResearchGroup, Role


def role_in_group(user, group: ResearchGroup) -> str | None:
    if not user.is_authenticated:
        return None
    return Membership.objects.filter(user=user, group=group).values_list("role", flat=True).first()


def has_group_role(user, group: ResearchGroup, minimum: str) -> bool:
    """True if the user is instance staff or holds at least `minimum` role in the group."""
    if user.is_authenticated and user.is_staff:
        return True
    role = role_in_group(user, group)
    return role is not None and ROLE_RANK[Role(role)] >= ROLE_RANK[Role(minimum)]


def writable_group_ids(user) -> set:
    """Groups where the user may add or change records (member role or higher)."""
    if not user.is_authenticated:
        return set()
    qs = ResearchGroup.objects.all()
    if not user.is_staff:
        qs = qs.filter(
            memberships__user=user,
            memberships__role__in=[Role.MEMBER, Role.PI, Role.ADMIN],
        )
    return set(qs.values_list("id", flat=True))


class IsContributorOrReadOnly(BasePermission):
    """Logged-in users read; users who are a member (or higher) of any group may write."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff or bool(writable_group_ids(request.user))


class IsStaffOrReadOnly(BasePermission):
    """Logged-in users can read; only instance staff can write."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or request.user.is_staff


class GroupManagerOrReadOnly(BasePermission):
    """Members can read their group; group admins/PIs (and staff) can change it."""

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj: ResearchGroup):
        if request.method in SAFE_METHODS:
            return has_group_role(request.user, obj, Role.VIEWER)
        return has_group_role(request.user, obj, Role.PI)
