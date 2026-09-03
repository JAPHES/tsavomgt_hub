from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render


def home(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    return redirect("dashboard:index")


def permission_denied_view(request, exception=None):
    return render(request, "errors/403.html", status=403)


def page_not_found_view(request, exception=None):
    response = render(
        request,
        "errors/404.html",
        {"requested_path": request.path},
        status=404,
    )
    response["X-Tsavo-Error-Page"] = "404"
    return response


def server_error_view(request):
    return render(request, "errors/500.html", status=500)
