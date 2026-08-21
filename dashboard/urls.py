from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_index, name="index"),
    path("innovator/", views.innovator_dashboard, name="innovator"),
    path("admin/", views.admin_dashboard, name="admin"),
    path("admin/bookings/<int:pk>/admit/", views.admit_booking_view, name="admit-booking"),
    path("bookings/", views.booking_records, name="bookings"),
    path("live-attendance/", views.booking_records, name="live-attendance"),
]
