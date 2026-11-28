from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("projects", views.ProjectViewSet, basename="project")
router.register("experiment-templates", views.TemplateViewSet, basename="experiment-template")
router.register("experiments", views.ExperimentViewSet, basename="experiment")
router.register("reaction-components", views.ComponentViewSet, basename="reaction-component")
router.register("attachments", views.AttachmentViewSet, basename="attachment")
router.register("comments", views.CommentViewSet, basename="comment")

urlpatterns = [
    path("eln/ledger/", views.ledger_status, name="eln-ledger"),
    path("", include(router.urls)),
]
