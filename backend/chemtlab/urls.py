from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("_allauth/", include("allauth.headless.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.orgs.urls")),
    path("api/", include("apps.chemistry.urls")),
    path("api/", include("apps.locations.urls")),
    path("api/", include("apps.inventory.urls")),
]

admin.site.site_header = "CheMTlab administration"
admin.site.site_title = "CheMTlab admin"
