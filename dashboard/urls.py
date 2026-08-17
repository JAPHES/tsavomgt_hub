from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_index, name="index"),
    path("innovator/", views.innovator_dashboard, name="innovator"),
    path("admin/", views.admin_dashboard, name="admin"),
    path("live-attendance/", views.live_attendance, name="live-attendance"),
]
