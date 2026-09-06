from django.shortcuts import redirect

from accounts.models import User

from .models import InnovatorProfile


class ForceInnovatorProfileCompletionMiddleware:
    """Keep innovators with missing required details in the profile setup flow."""

    allowed_view_names = {
        "innovators:profile-complete",
        "accounts:logout",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if (
            not request.user.is_authenticated
            or request.user.role != User.Role.INNOVATOR
            or request.user.must_change_password
            or request.resolver_match.view_name in self.allowed_view_names
        ):
            return None

        try:
            profile = request.user.innovator_profile
        except InnovatorProfile.DoesNotExist:
            return None
        if not profile.has_completed_required_details:
            return redirect("innovators:profile-complete")
        return None
