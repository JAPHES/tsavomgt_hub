from django.contrib.auth.views import redirect_to_login
from django.db import connection
from django.db.utils import InterfaceError, OperationalError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import get_template
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .service_status import (
    UNAVAILABLE,
    database_status,
    mark_database_available,
    mark_database_unavailable,
)


def home(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    return redirect("dashboard:index")


@require_GET
@never_cache
def health_check(request):
    """Report process liveness without accessing sessions or the database."""
    return JsonResponse({"status": "ok"})


@require_GET
@never_cache
def database_health_check(request):
    """Report database readiness without exposing connection details."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (OperationalError, InterfaceError):
        mark_database_unavailable()
        return JsonResponse(
            {"status": "degraded", "database": "unavailable"},
            status=503,
        )
    mark_database_available()
    return JsonResponse({"status": "ok", "database": "available"})


@require_GET
@never_cache
def status_view(request):
    """Render service status using only filesystem-backed outage state."""
    is_degraded = database_status() == UNAVAILABLE
    template = get_template("core/status.html")
    return HttpResponse(
        template.render({"is_degraded": is_degraded}),
        status=503 if is_degraded else 200,
    )


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
    # Avoid RequestContext here: auth and session context can need PostgreSQL.
    return HttpResponse(get_template("errors/500.html").render(), status=500)
