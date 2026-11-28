from django.db.models import Q
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Capability, User
from .serializers import MeSerializer, UserAdminSerializer, UserSummarySerializer


class MeView(generics.RetrieveUpdateAPIView):
    """The logged-in user's profile, capabilities and group memberships."""

    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class CanManageUsers(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return user.has_capability(Capability.USER_MANAGER)


class UserViewSet(viewsets.ModelViewSet):
    """People on this instance. Everyone signed in can look people up (for pickers);
    user managers see full records and can create, edit and deactivate accounts.
    Accounts are never deleted (records keep their author); deactivate instead."""

    permission_classes = [CanManageUsers]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = User.objects.prefetch_related("memberships__group")
        if not self.request.user.has_capability(Capability.USER_MANAGER):
            qs = qs.filter(is_active=True)
        if q := self.request.query_params.get("q"):
            qs = qs.filter(
                Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )
        if group := self.request.query_params.get("group"):
            qs = qs.filter(memberships__group=group)
        return qs

    def get_serializer_class(self):
        if self.request.user.has_capability(Capability.USER_MANAGER):
            return UserAdminSerializer
        return UserSummarySerializer


@api_view(["GET"])
def capability_list(request):
    """The instance-wide capabilities that can be granted, with descriptions."""
    return Response([{"value": c.value, "label": c.label} for c in Capability])
