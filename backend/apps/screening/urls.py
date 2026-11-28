from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("campaigns", views.CampaignViewSet, basename="campaign")
router.register("campaign-variables", views.VariableViewSet, basename="campaign-variable")
router.register("campaign-responses", views.ResponseViewSet, basename="campaign-response")
router.register("campaign-runs", views.RunViewSet, basename="campaign-run")

urlpatterns = [path("", include(router.urls))]
