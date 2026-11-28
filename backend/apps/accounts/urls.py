from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MeView, UserViewSet, capability_list

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("capabilities/", capability_list, name="capabilities"),
    path("", include(router.urls)),
]
