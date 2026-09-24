from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health_check, name="health"),
    path("health/database/", views.database_health_check, name="database-health"),
    path("status/", views.status_view, name="status"),
]
