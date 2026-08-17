from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.permissions import admin_required, innovator_required

from .forms import AttendanceCorrectionForm, CheckInForm, CheckOutForm
from .models import AttendanceSession
from .services import AttendanceError, check_in, check_out, correct_attendance


@innovator_required
def check_in_view(request):
    profile = request.user.innovator_profile
    form = CheckInForm(
        request.POST or None,
        project_name=profile.innovation_project_name,
    )
    if request.method == "POST" and form.is_valid():
        try:
            session, stale = check_in(request.user, **form.cleaned_data)
        except AttendanceError as exc:
            form.add_error(None, str(exc))
        else:
            if stale:
                messages.warning(
                    request,
                    "Your previous session was marked incomplete because no checkout was recorded.",
                )
            messages.success(
                request,
                f"Checked in at {timezone.localtime(session.check_in_at):%H:%M}.",
            )
            return redirect("dashboard:innovator")
    return render(request, "attendance/check_in.html", {"form": form})


@innovator_required
def check_out_view(request):
    active = AttendanceSession.objects.filter(
        innovator=request.user, status=AttendanceSession.Status.ACTIVE
    ).first()
    if not active:
        messages.warning(request, "There is no active session to check out from.")
        return redirect("dashboard:innovator")
    form = CheckOutForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            session = check_out(request.user, **form.cleaned_data)
        except AttendanceError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Checkout recorded. Thank you for documenting your work.")
            return redirect("attendance:detail", pk=session.pk)
    return render(request, "attendance/check_out.html", {"form": form, "session": active})


@innovator_required
def attendance_history(request):
    sessions = AttendanceSession.objects.filter(innovator=request.user)
    page_obj = Paginator(sessions, 20).get_page(request.GET.get("page"))
    return render(request, "attendance/history.html", {"page_obj": page_obj})


def _permitted_session(request, pk):
    queryset = AttendanceSession.objects.select_related("innovator", "innovator__innovator_profile")
    if request.user.role != request.user.Role.ADMIN:
        queryset = queryset.filter(innovator=request.user)
    return get_object_or_404(queryset, pk=pk)


@innovator_required
def innovator_session_detail(request, pk):
    session = _permitted_session(request, pk)
    return render(request, "attendance/detail.html", {"session": session})


@admin_required
def admin_session_detail(request, pk):
    session = get_object_or_404(
        AttendanceSession.objects.select_related(
            "innovator", "innovator__innovator_profile", "corrected_by"
        ).prefetch_related("corrections__administrator"),
        pk=pk,
    )
    return render(request, "attendance/detail.html", {"session": session})


@admin_required
def correct_session(request, pk):
    session = get_object_or_404(
        AttendanceSession.objects.select_related("innovator", "innovator__innovator_profile"), pk=pk
    )
    form = AttendanceCorrectionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        try:
            corrected = correct_attendance(
                session.pk, form.cleaned_data, administrator=request.user, request=request
            )
        except AttendanceError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Attendance correction saved with an audit record.")
            return redirect("attendance:admin-detail", pk=corrected.pk)
    return render(request, "attendance/correct.html", {"form": form, "session": session})
