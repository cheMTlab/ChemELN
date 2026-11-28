from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from .models import Department, Institution, Membership, ResearchGroup, Role
from .permissions import GroupManagerOrReadOnly, IsStaffOrReadOnly, has_group_role
from .serializers import (
    DepartmentSerializer,
    InstitutionSerializer,
    MembershipSerializer,
    ResearchGroupSerializer,
)


class InstitutionViewSet(viewsets.ModelViewSet):
    queryset = Institution.objects.all()
    serializer_class = InstitutionSerializer
    permission_classes = [IsStaffOrReadOnly]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related("institution")
    serializer_class = DepartmentSerializer
    permission_classes = [IsStaffOrReadOnly]


class ResearchGroupViewSet(viewsets.ModelViewSet):
    """Staff see every group; other users see only groups they belong to.

    Only staff create or delete groups; group admins/PIs may edit their group.
    """

    serializer_class = ResearchGroupSerializer
    permission_classes = [GroupManagerOrReadOnly]

    def get_queryset(self):
        qs = ResearchGroup.objects.select_related("department").prefetch_related("memberships")
        if self.request.user.is_staff:
            return qs
        return qs.filter(memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied("Only instance administrators can create groups.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied("Only instance administrators can delete groups.")
        instance.delete()


class MembershipViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Members of one group. Anyone in the group can list; admins/PIs manage."""

    serializer_class = MembershipSerializer

    def get_group(self) -> ResearchGroup:
        group = get_object_or_404(ResearchGroup, pk=self.kwargs["group_pk"])
        minimum = Role.VIEWER if self.request.method == "GET" else Role.PI
        if self._is_user_manager():
            return group
        if not has_group_role(self.request.user, group, minimum):
            # Hide existence of groups the user cannot see.
            if not has_group_role(self.request.user, group, Role.VIEWER):
                raise Http404
            raise PermissionDenied("Only group admins and PIs can manage members.")
        return group

    def get_queryset(self):
        return Membership.objects.filter(group=self.get_group()).select_related("user")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if "group_pk" in self.kwargs:
            ctx["group"] = self.get_group()
        return ctx

    def perform_update(self, serializer):
        self._guard_admin_escalation(serializer.validated_data.get("role"))
        serializer.save()

    def perform_create(self, serializer):
        self._guard_admin_escalation(serializer.validated_data.get("role"))
        serializer.save()

    def _guard_admin_escalation(self, role):
        """Only group admins (or staff) may grant the admin role."""
        if role == Role.ADMIN and not (
            self._is_user_manager()
            or has_group_role(self.request.user, self.get_group(), Role.ADMIN)
        ):
            raise PermissionDenied("Only group admins can grant the admin role.")

    def _is_user_manager(self) -> bool:
        user = self.request.user
        return user.is_authenticated and user.has_capability("user_manager")
