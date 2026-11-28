from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("plasmids", views.PlasmidViewSet, basename="plasmid")
router.register("strains", views.StrainViewSet, basename="strain")
router.register("oligos", views.OligoViewSet, basename="oligo")
router.register("bio-samples", views.BioSampleViewSet, basename="bio-sample")
router.register("assays", views.AssayViewSet, basename="assay")
router.register("plates", views.PlateViewSet, basename="plate")
router.register("wells", views.WellViewSet, basename="well")

urlpatterns = [
    path("bio/oligo-tools/", views.oligo_tools, name="oligo-tools"),
    path("", include(router.urls)),
]
