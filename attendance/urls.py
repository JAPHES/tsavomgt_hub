from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("check-in/", views.check_in_view, name="check-in"),
    path("check-out/", views.check_out_view, name="check-out"),
    path("history/", views.attendance_history, name="history"),
    path("session/<int:pk>/", views.innovator_session_detail, name="detail"),
    path("session/<int:pk>/admin/", views.admin_session_detail, name="admin-detail"),
]
