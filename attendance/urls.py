from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("bookings/", views.booking_history, name="booking-history"),
    path("history/", views.booking_history, name="history"),
    path("session/<int:pk>/admin/", views.admin_session_detail, name="admin-detail"),
]
