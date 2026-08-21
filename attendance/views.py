from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from core.permissions import admin_required, innovator_required

from .models import AttendanceSession, HubBooking


@innovator_required
def booking_history(request):
    bookings = HubBooking.objects.filter(innovator=request.user)
    page_obj = Paginator(bookings, 20).get_page(request.GET.get("page"))
    return render(request, "attendance/history.html", {"page_obj": page_obj})


@admin_required
def admin_session_detail(request, pk):
    session = get_object_or_404(
        AttendanceSession.objects.select_related(
            "innovator", "innovator__innovator_profile", "corrected_by"
        ),
        pk=pk,
    )
    return render(request, "attendance/detail.html", {"session": session})
