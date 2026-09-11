from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.permissions import admin_required, innovator_required

from .forms import HubBookingForm
from .models import AttendanceSession, HubBooking
from .services import BookingError, update_booking


@innovator_required
def booking_history(request):
    bookings = HubBooking.objects.filter(innovator=request.user)
    today = timezone.localdate()
    history = bookings.exclude(
        visit_date__gte=today,
        status=HubBooking.Status.BOOKED,
    ).select_related("admitted_by", "cancelled_by")
    page_obj = Paginator(history, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "attendance/history.html",
        {"page_obj": page_obj},
    )


@innovator_required
@require_http_methods(["GET", "POST"])
def booking_edit(request, pk):
    booking = get_object_or_404(HubBooking, pk=pk, innovator=request.user)
    if booking.status != HubBooking.Status.BOOKED:
        messages.error(request, "Only a booking awaiting admission can be updated.")
        return redirect("attendance:booking-history")

    form = HubBookingForm(
        request.POST or None,
        instance=booking,
        innovator=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            updated = update_booking(
                request.user,
                booking,
                request=request,
                **form.cleaned_data,
            )
        except BookingError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Your hub visit for {updated.visit_date:%d %B %Y} was updated.",
            )
            return redirect("dashboard:innovator")
    return render(
        request,
        "attendance/booking_edit.html",
        {"booking": booking, "form": form},
    )


@admin_required
def admin_session_detail(request, pk):
    session = get_object_or_404(
        AttendanceSession.objects.select_related(
            "innovator", "innovator__innovator_profile", "corrected_by"
        ),
        pk=pk,
    )
    return render(request, "attendance/detail.html", {"session": session})
