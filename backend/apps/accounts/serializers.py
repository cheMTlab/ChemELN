from rest_framework import serializers

from apps.orgs.models import Membership

from .models import User


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
        fields = ["group_id", "group_name", "role"]


class MeSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    memberships = MyMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "orcid",
            "is_staff",
            "memberships",
        ]
        read_only_fields = ["id", "email", "is_staff", "memberships"]
