from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("cost-centres", views.CostCentreViewSet, basename="cost-centre")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = [
    path("containers/<uuid:pk>/reorder/", views.reorder_container, name="container-reorder"),
    path("", include(router.urls)),
]
