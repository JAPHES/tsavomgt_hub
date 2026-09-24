from django.shortcuts import redirect
from django.db.utils import InterfaceError, OperationalError

from accounts.models import User
from core.middleware import database_unavailable_response
from core.service_status import mark_database_unavailable

from .models import InnovatorProfile


class ForceInnovatorProfileCompletionMiddleware:
    """Keep innovators with missing required details in the profile setup flow."""

    allowed_view_names = {
        "innovators:profile-complete",
        "accounts:logout",
        "core:database-health",
        "core:health",
        "core:status",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.resolver_match.view_name in self.allowed_view_names:
            return None
        try:
            if (
                not request.user.is_authenticated
                or request.user.role != User.Role.INNOVATOR
                or request.user.must_change_password
            ):
                return None

            try:
                profile = request.user.innovator_profile
            except InnovatorProfile.DoesNotExist:
                return None
        except (OperationalError, InterfaceError):
            mark_database_unavailable()
            return database_unavailable_response()
        if not profile.has_completed_required_details:
            return redirect("innovators:profile-complete")
        return None
