from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.orgs.models import Membership

from .models import Capability, User


class UserSummarySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "orcid"]


class MyMembershipSerializer(serializers.ModelSerializer):
    group_id = serializers.UUIDField(source="group.id", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "group_id", "group_name", "role"]


def effective_capabilities(user) -> list[str]:
    if user.is_staff:
        return [c.value for c in Capability]
    return [c for c in (user.capabilities or []) if c in Capability.values]


class MeSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    memberships = MyMembershipSerializer(many=True, read_only=True)
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "initials",
            "job_title",
            "phone",
            "orcid",
            "is_staff",
            "capabilities",
            "memberships",
        ]
        read_only_fields = ["id", "email", "is_staff", "memberships"]

    def get_capabilities(self, user) -> list[str]:
        return effective_capabilities(user)


class UserAdminSerializer(serializers.ModelSerializer):
    """Full user record for user managers. Passwords are write-only and optional (SSO users)."""

    display_name = serializers.CharField(read_only=True)
    memberships = MyMembershipSerializer(many=True, read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    capabilities = serializers.ListField(
        child=serializers.ChoiceField(choices=Capability.choices), required=False
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "initials",
            "job_title",
            "phone",
            "orcid",
            "is_active",
            "is_staff",
            "capabilities",
            "memberships",
            "last_login",
            "date_joined",
            "password",
        ]
        read_only_fields = ["id", "last_login", "date_joined", "memberships"]

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value

    def validate_is_staff(self, value):
        request = self.context["request"]
        if value != getattr(self.instance, "is_staff", False) and not request.user.is_staff:
            raise serializers.ValidationError(
                "Only instance administrators can grant admin rights."
            )
        return value

    def validate(self, attrs):
        request = self.context["request"]
        if self.instance and self.instance == request.user and attrs.get("is_active") is False:
            raise serializers.ValidationError({"is_active": "You cannot deactivate yourself."})
        return attrs

    def create(self, validated):
        password = validated.pop("password", "") or None
        user = User.objects.create_user(**validated, password=password)
        if password is None:
            user.set_unusable_password()  # SSO or "set password" email later
            user.save(update_fields=["password"])
        return user

    def update(self, instance, validated):
        password = validated.pop("password", "")
        user = super().update(instance, validated)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
