from django.contrib.sessions.middleware import SessionMiddleware
from django.db import connection
from django.db.utils import InterfaceError, OperationalError
from django.http import HttpResponse
from django.template.loader import get_template

from .service_status import (
    AVAILABLE,
    database_status,
    mark_database_available,
    mark_database_unavailable,
)
from .views import page_not_found_view


def database_unavailable_response():
    """Build a branded response without request/session/database context."""
    response = HttpResponse(get_template("errors/503.html").render(), status=503)
    response["Cache-Control"] = "no-store"
    response["Retry-After"] = "300"
    return response


class DatabaseFailureMiddleware:
    """Handle expected database connectivity failures without hiding code bugs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            response.status_code < 500
            and connection.connection is not None
            and database_status() != AVAILABLE
        ):
            mark_database_available()
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, (OperationalError, InterfaceError)):
            mark_database_unavailable()
            return database_unavailable_response()
        return None


class DatabaseResilientSessionMiddleware(SessionMiddleware):
    """Return the degraded page if a database session cannot be saved."""

    def process_response(self, request, response):
        try:
            return super().process_response(request, response)
        except (OperationalError, InterfaceError):
            mark_database_unavailable()
            return database_unavailable_response()


class CustomNotFoundMiddleware:
    """Render the branded 404 page for every not-found response.

    Django normally shows its technical 404 response while DEBUG is enabled.
    Replacing 404 responses here keeps missing application and admin URLs
    consistent in both development and production.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 404 and response.get("X-Tsavo-Error-Page") != "404":
            return page_not_found_view(request)
        return response
