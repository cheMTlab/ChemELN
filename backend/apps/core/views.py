from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

import chemtlab

from . import checks


@extend_schema(
    responses=inline_serializer(
        "Health",
        {"status": serializers.CharField(), "version": serializers.CharField()},
    )
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness/readiness probe. Deliberately reveals no internals."""
    db = checks.check_database()
    return Response(
        {"status": "ok" if db.ok else "error", "version": chemtlab.__version__},
        status=200 if db.ok else 503,
    )


@extend_schema(
    responses=inline_serializer(
        "InstanceConfig",
        {
            "instance_name": serializers.CharField(),
            "version": serializers.CharField(),
            "structure_editor": serializers.CharField(),
            "sso_providers": serializers.ListField(child=serializers.DictField()),
            "open_signup": serializers.BooleanField(),
            "external_lookups": serializers.BooleanField(),
            "ai_enabled": serializers.BooleanField(),
        },
    )
)
@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def instance_config(request):
    """Public, non-secret configuration the frontend needs before login.

    Also sets the CSRF cookie the SPA needs for login and other POSTs.
    """
    cfg = settings.CHEMTLAB
    providers = [
        {"id": app["provider_id"], "name": app["name"]}
        for app in settings.SOCIALACCOUNT_PROVIDERS.get("openid_connect", {}).get("APPS", [])
    ]
    return Response(
        {
            "instance_name": cfg["INSTANCE_NAME"],
            "version": chemtlab.__version__,
            "structure_editor": cfg["STRUCTURE_EDITOR"],
            "sso_providers": providers,
            "open_signup": settings.CHEMTLAB_OPEN_SIGNUP,
            "external_lookups": cfg["ALLOW_EXTERNAL_LOOKUPS"],
            "ai_enabled": bool(cfg["AI_PROVIDER"]),
        }
    )
