from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("institutions", views.InstitutionViewSet, basename="institution")
router.register("departments", views.DepartmentViewSet, basename="department")
router.register("groups", views.ResearchGroupViewSet, basename="group")

members = views.MembershipViewSet

urlpatterns = [
    path("", include(router.urls)),
    path(
        "groups/<uuid:group_pk>/members/",
        members.as_view({"get": "list", "post": "create"}),
        name="group-members",
    ),
    path(
        "groups/<uuid:group_pk>/members/<uuid:pk>/",
        members.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="group-member-detail",
    ),
]
