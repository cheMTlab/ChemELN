from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("containers", views.ContainerViewSet, basename="container")

urlpatterns = [
    path("containers/import/", views.import_containers, name="container-import"),
    path("", include(router.urls)),
]
