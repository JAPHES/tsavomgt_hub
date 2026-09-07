from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import page_not_found_view

urlpatterns = [
    # Administrators authenticate through the application's branded login.
    # Keep Django's standalone login endpoint undiscoverable while retaining
    # database administration for staff who already have an authenticated session.
    path("admin/login/", page_not_found_view, name="hidden-admin-login"),
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("innovators/", include("innovators.urls")),
    path("attendance/", include("attendance.urls")),
    path("dashboard/", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "core.views.permission_denied_view"
handler404 = "core.views.page_not_found_view"
handler500 = "core.views.server_error_view"
