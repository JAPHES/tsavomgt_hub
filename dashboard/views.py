from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from attendance.models import AttendanceSession
from core.permissions import admin_required, innovator_required

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
    now = timezone.now()
    today = timezone.localdate(now)
    week_start = today - timedelta(days=today.weekday())
    week_sessions = AttendanceSession.objects.filter(
        innovator=request.user, check_in_at__date__gte=week_start, check_in_at__date__lte=today
    )
    total_seconds = sum(
        (session.duration.total_seconds() for session in week_sessions if session.duration), 0
    )
    active_session = week_sessions.filter(status=AttendanceSession.Status.ACTIVE).first()
    if not active_session:
        active_session = AttendanceSession.objects.filter(
            innovator=request.user, status=AttendanceSession.Status.ACTIVE
        ).first()
    incomplete_sessions = AttendanceSession.objects.filter(
        innovator=request.user, status=AttendanceSession.Status.INCOMPLETE
    )[:5]
    recent_sessions = AttendanceSession.objects.filter(innovator=request.user)[:7]
    today_session = AttendanceSession.objects.filter(
        innovator=request.user, check_in_at__date=today
    ).first()
    return render(
        request,
        "dashboard/innovator.html",
        {
            "now": now,
            "active_session": active_session,
            "today_session": today_session,
            "incomplete_sessions": incomplete_sessions,
            "recent_sessions": recent_sessions,
            "visits_this_week": week_sessions.count(),
            "hours_this_week": total_seconds / 3600,
        },
    )


@admin_required
def admin_dashboard(request):
    today = timezone.localdate()
    sessions = _base_sessions()
    current_sessions = sessions.filter(status=AttendanceSession.Status.ACTIVE).order_by("check_in_at")
    today_sessions = sessions.filter(check_in_at__date=today)
    completed_today = sessions.filter(
        check_out_at__date=today,
        status__in=[AttendanceSession.Status.COMPLETED, AttendanceSession.Status.ADMIN_CLOSED],
    ).order_by("-check_out_at")
    incomplete_sessions = sessions.filter(status=AttendanceSession.Status.INCOMPLETE).order_by(
        "check_in_at"
    )
    total_seconds = sum(
        (session.duration.total_seconds() for session in completed_today if session.duration), 0
    )
    return render(
        request,
        "dashboard/admin.html",
        {
            "current_sessions": current_sessions,
            "today_sessions": today_sessions,
            "completed_today": completed_today[:50],
            "incomplete_sessions": incomplete_sessions[:20],
            "summary": {
                "currently_in_hub": current_sessions.count(),
                "visitors_today": today_sessions.values("innovator_id").distinct().count(),
                "checked_out_today": completed_today.values("innovator_id").distinct().count(),
                "incomplete": incomplete_sessions.count(),
                "hours_today": total_seconds / 3600,
                "active_innovators": User.objects.filter(
                    role=User.Role.INNOVATOR,
                    account_status=User.AccountStatus.ACTIVE,
                    is_active=True,
                ).count(),
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
