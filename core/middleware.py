from .views import page_not_found_view


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
