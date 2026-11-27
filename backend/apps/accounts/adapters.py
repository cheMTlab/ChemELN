from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    """Self sign-up is closed by default; institutions invite users or use SSO."""

    def is_open_for_signup(self, request):
        return settings.CHEMTLAB_OPEN_SIGNUP


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Anyone who authenticates through the institution's identity provider may join."""

    def is_open_for_signup(self, request, sociallogin):
        return True
