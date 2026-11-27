from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import Department, Institution, Membership, ResearchGroup


class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = ["id", "name", "short_name", "ror_id", "country"]


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "institution", "name"]


class ResearchGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source="memberships.count", read_only=True)

    class Meta:
        model = ResearchGroup
        fields = ["id", "department", "name", "description", "member_count"]


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    user_email = serializers.EmailField(write_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "user_email", "role"]

    def validate_user_email(self, value):
        try:
            return get_user_model().objects.get(email__iexact=value)
        except get_user_model().DoesNotExist as exc:
            raise serializers.ValidationError("No user with this email.") from exc

    def create(self, validated_data):
        user = validated_data.pop("user_email")
        membership, _ = Membership.objects.update_or_create(
            user=user, group=self.context["group"], defaults=validated_data
        )
        return membership

    def update(self, instance, validated_data):
        validated_data.pop("user_email", None)
        return super().update(instance, validated_data)
