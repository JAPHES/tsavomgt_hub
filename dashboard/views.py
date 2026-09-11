from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import User
from attendance.forms import BookingCancellationForm, HubBookingForm
from attendance.models import HubBooking
from attendance.services import (
    BookingError,
    BookingNotificationError,
    admit_booking,
    cancel_booking,
    create_booking,
    send_booking_cancellation_email,
)
from core.permissions import admin_required, innovator_required

from .forms import AttendanceFilterForm


def _base_bookings():
    return HubBooking.objects.select_related(
        "innovator", "innovator__innovator_profile", "admitted_by", "cancelled_by"
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
        visit_date__year=today.year,
        visit_date__month=today.month,
    ).exclude(
        status=HubBooking.Status.CANCELLED,
    )
    return render(
        request,
        "dashboard/innovator.html",
        {
            "now": now,
            "booking_form": booking_form,
            "upcoming_bookings": upcoming_bookings[:5],
            "bookings_this_month": bookings_this_month.count(),
            "admitted_visits": bookings.filter(status=HubBooking.Status.ADMITTED).count(),
        },
    )


@admin_required
def admin_dashboard(request):
    today = timezone.localdate()
    today_bookings = (
        _base_bookings()
        .filter(visit_date=today)
        .exclude(status=HubBooking.Status.CANCELLED)
        .order_by("arrival_time")
    )
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
def future_bookings(request):
    today = timezone.localdate()
    bookings = _base_bookings().filter(
        visit_date__gt=today,
        status=HubBooking.Status.BOOKED,
    ).order_by("visit_date", "arrival_time")
    page_obj = Paginator(bookings, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/future_bookings.html",
        {"page_obj": page_obj},
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


@admin_required
@require_http_methods(["GET", "POST"])
def cancel_booking_view(request, pk):
    return_targets = {
        "future": ("dashboard:future-bookings", "future bookings"),
        "bookings": ("dashboard:bookings", "booking records"),
    }
    return_to = request.POST.get("next") or request.GET.get("next") or ""
    return_view, return_label = return_targets.get(
        return_to,
        ("dashboard:admin", "administrator dashboard"),
    )
    return_url = reverse(return_view)
    booking = get_object_or_404(
        _base_bookings(),
        pk=pk,
    )
    if booking.status != HubBooking.Status.BOOKED:
        messages.error(request, "Only a booking awaiting admission can be cancelled.")
        return redirect(return_url)

    form = BookingCancellationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancelled = cancel_booking(
                request.user,
                booking,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except BookingError as exc:
            messages.error(request, str(exc))
            return redirect(return_url)

        try:
            send_booking_cancellation_email(cancelled)
        except BookingNotificationError as exc:
            messages.warning(request, str(exc))
        else:
            messages.success(
                request,
                f"The visit for {cancelled.innovator.get_full_name()} was cancelled "
                "and the innovator was notified by email.",
            )
        return redirect(return_url)

    return render(
        request,
        "dashboard/cancel_booking.html",
        {
            "booking": booking,
            "form": form,
            "return_to": return_to if return_to in return_targets else "",
            "return_url": return_url,
            "return_label": return_label,
        },
    )


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
