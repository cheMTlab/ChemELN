from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Location


class LocationSerializer(serializers.ModelSerializer):
    container_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Location
        fields = [
            "id",
            "parent",
            "name",
            "kind",
            "barcode",
            "group",
            "allowed_storage_classes",
            "temperature",
            "notes",
            "path",
            "depth",
            "container_count",
        ]
        read_only_fields = ["path", "depth"]

    def validate(self, attrs):
        instance = Location(**{**self._current(), **attrs})
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs

    def _current(self) -> dict:
        if not self.instance:
            return {}
        return {
            "id": self.instance.pk,
            "parent": self.instance.parent,
            "name": self.instance.name,
            "allowed_storage_classes": self.instance.allowed_storage_classes,
        }
