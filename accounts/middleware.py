from django.shortcuts import redirect


class ForceFirstLoginPasswordChangeMiddleware:
    """Keep temporary-password users inside the mandatory password-change flow."""

    allowed_view_names = {
        "accounts:first-login-password-change",
        "accounts:logout",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if (
            request.user.is_authenticated
            and request.user.must_change_password
            and request.resolver_match.view_name not in self.allowed_view_names
        ):
            return redirect("accounts:first-login-password-change")
        return None
