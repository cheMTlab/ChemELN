from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("compounds", views.CompoundViewSet, basename="compound")
router.register("sds", views.SafetyDataSheetViewSet, basename="sds")

urlpatterns = [
    path("", include(router.urls)),
    path("chem/analyse/", views.analyse_structure, name="analyse-structure"),
]
