from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("config/", views.instance_config, name="instance-config"),
]
