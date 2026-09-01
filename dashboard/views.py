from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from attendance.forms import HubBookingForm
from attendance.models import HubBooking
from attendance.services import BookingError, admit_booking, create_booking
from core.permissions import admin_required, innovator_required

from .forms import AttendanceFilterForm


def _base_bookings():
    return HubBooking.objects.select_related(
        "innovator", "innovator__innovator_profile", "admitted_by"
    )


@login_required
def dashboard_index(request):
    if request.user.role == User.Role.ADMIN:
        return redirect("dashboard:admin")
    if request.user.role == User.Role.INNOVATOR:
        return redirect("dashboard:innovator")
    raise PermissionDenied


@innovator_required
def innovator_dashboard(request):
    booking_form = HubBookingForm(request.POST or None, innovator=request.user)
    if request.method == "POST" and booking_form.is_valid():
        try:
            booking = create_booking(request.user, **booking_form.cleaned_data)
        except BookingError as exc:
            booking_form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Your hub visit for {booking.visit_date:%d %B %Y} at "
                f"{booking.arrival_time:%H:%M} has been booked.",
            )
            return redirect("dashboard:innovator")
    now = timezone.now()
    today = timezone.localdate(now)
    bookings = HubBooking.objects.filter(innovator=request.user)
    upcoming_bookings = bookings.filter(
        visit_date__gte=today, status=HubBooking.Status.BOOKED
    ).order_by("visit_date", "arrival_time")
    bookings_this_month = bookings.filter(
        visit_date__year=today.year, visit_date__month=today.month
    )
    return render(
        request,
        "dashboard/innovator.html",
        {
            "now": now,
            "booking_form": booking_form,
            "upcoming_bookings": upcoming_bookings[:5],
            "recent_bookings": bookings[:7],
            "bookings_this_month": bookings_this_month.count(),
            "admitted_visits": bookings.filter(status=HubBooking.Status.ADMITTED).count(),
        },
    )


@admin_required
def admin_dashboard(request):
    today = timezone.localdate()
    today_bookings = _base_bookings().filter(visit_date=today).order_by("arrival_time")
    return render(
        request,
        "dashboard/admin.html",
        {
            "today": today,
            "today_bookings": today_bookings,
            "summary": {
                "active_innovators": User.objects.filter(
                    role=User.Role.INNOVATOR,
                    account_status=User.AccountStatus.ACTIVE,
                    is_active=True,
                ).count(),
                "bookings_today": today_bookings.count(),
                "awaiting_admission": today_bookings.filter(
                    status=HubBooking.Status.BOOKED
                ).count(),
                "admitted_today": today_bookings.filter(
                    status=HubBooking.Status.ADMITTED
                ).count(),
            },
        },
    )


@admin_required
@require_POST
def admit_booking_view(request, pk):
    booking = get_object_or_404(HubBooking, pk=pk)
    try:
        admitted = admit_booking(request.user, booking, request=request)
    except BookingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"{admitted.innovator.get_full_name()} was admitted to the hub at "
            f"{timezone.localtime(admitted.admitted_at):%H:%M}.",
        )
    return redirect("dashboard:admin")


def filter_bookings(queryset, cleaned):
    innovator_name = cleaned.get("innovator_name", "")
    for name_part in innovator_name.split():
        queryset = queryset.filter(
            Q(innovator__first_name__icontains=name_part)
            | Q(innovator__last_name__icontains=name_part)
        )
    return queryset


@admin_required
def booking_records(request):
    form = AttendanceFilterForm(request.GET or None)
    bookings = _base_bookings()
    if form.is_valid():
        bookings = filter_bookings(bookings, form.cleaned_data)
    page_obj = Paginator(bookings, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/live_attendance.html",
        {
            "form": form,
            "page_obj": page_obj,
            "filter_applied": bool(form.is_bound and form.is_valid() and form.cleaned_data["innovator_name"]),
        },
    )
