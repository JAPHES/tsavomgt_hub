from django.shortcuts import redirect

from django.db.utils import InterfaceError, OperationalError

from core.middleware import database_unavailable_response
from core.service_status import mark_database_unavailable


class ForceFirstLoginPasswordChangeMiddleware:
    """Keep temporary-password users inside the mandatory password-change flow."""

    allowed_view_names = {
        "accounts:first-login-password-change",
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
            if request.user.is_authenticated and request.user.must_change_password:
                return redirect("accounts:first-login-password-change")
        except (OperationalError, InterfaceError):
            mark_database_unavailable()
            return database_unavailable_response()
        return None
