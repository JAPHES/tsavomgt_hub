from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from attendance.models import AttendanceSession
from attendance.services import record_daily_attendance
from core.permissions import admin_required, innovator_required

from attendance.forms import DailyAttendanceForm

from .forms import AttendanceFilterForm


def _base_sessions():
    return AttendanceSession.objects.select_related("innovator", "innovator__innovator_profile")


@login_required
def dashboard_index(request):
    if request.user.role == User.Role.ADMIN:
        return redirect("dashboard:admin")
    if request.user.role == User.Role.INNOVATOR:
        return redirect("dashboard:innovator")
    raise PermissionDenied


@innovator_required
def innovator_dashboard(request):
    attendance_form = DailyAttendanceForm(request.POST or None)
    if request.method == "POST" and attendance_form.is_valid():
        session = record_daily_attendance(
            request.user,
            check_in_at=attendance_form.cleaned_data["check_in_at"],
            check_out_at=attendance_form.cleaned_data["check_out_at"],
            work_completed=attendance_form.cleaned_data["work_completed"],
            challenges_encountered=attendance_form.cleaned_data["challenges_encountered"],
        )
        messages.success(request, "Today's attendance and completed work were recorded.")
        return redirect("attendance:detail", pk=session.pk)
    now = timezone.now()
    today = timezone.localdate(now)
    week_start = today - timedelta(days=today.weekday())
    week_sessions = AttendanceSession.objects.filter(
        innovator=request.user, check_in_at__date__gte=week_start, check_in_at__date__lte=today
    )
    total_seconds = sum(
        (session.duration.total_seconds() for session in week_sessions if session.duration), 0
    )
    recent_sessions = AttendanceSession.objects.filter(innovator=request.user)[:7]
    return render(
        request,
        "dashboard/innovator.html",
        {
            "now": now,
            "attendance_form": attendance_form,
            "recent_sessions": recent_sessions,
            "visits_this_week": week_sessions.count(),
            "hours_this_week": total_seconds / 3600,
        },
    )


@admin_required
def admin_dashboard(request):
    today = timezone.localdate()
    sessions = _base_sessions()
    today_sessions = sessions.filter(check_in_at__date=today).order_by("check_in_at")
    return render(
        request,
        "dashboard/admin.html",
        {
            "today_sessions": today_sessions,
            "summary": {
                "active_innovators": User.objects.filter(
                    role=User.Role.INNOVATOR,
                    account_status=User.AccountStatus.ACTIVE,
                    is_active=True,
                ).count(),
                "attended_today": today_sessions.values("innovator_id").distinct().count(),
            },
        },
    )


def filter_attendance(queryset, cleaned):
    innovator_name = cleaned.get("innovator_name", "")
    for name_part in innovator_name.split():
        queryset = queryset.filter(
            Q(innovator__first_name__icontains=name_part)
            | Q(innovator__last_name__icontains=name_part)
        )
    return queryset


@admin_required
def live_attendance(request):
    form = AttendanceFilterForm(request.GET or None)
    sessions = _base_sessions()
    if form.is_valid():
        sessions = filter_attendance(sessions, form.cleaned_data)
    page_obj = Paginator(sessions, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/live_attendance.html",
        {
            "form": form,
            "page_obj": page_obj,
            "filter_applied": bool(form.is_bound and form.is_valid() and form.cleaned_data["innovator_name"]),
        },
    )
