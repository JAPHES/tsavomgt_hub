import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import User
from accounts.services import (
    TemporaryCredentialDeliveryError,
    TemporaryCredentialError,
    issue_temporary_credentials,
)
from auditlog.models import AuditLog
from auditlog.services import record_audit
from core.permissions import admin_required, innovator_required

from .forms import (
    InnovatorAdminUpdateForm,
    InnovatorCreateForm,
    InnovatorProjectForm,
    InnovatorSelfUpdateForm,
)
from .models import InnovatorProfile
from .services import (
    InnovatorDeletionError,
    ProjectError,
    create_innovator,
    create_project,
    permanently_delete_innovator,
    send_deactivation_email,
    update_innovator,
)


def _spreadsheet_safe(value):
    text = str(value or "")
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


@admin_required
def innovator_list(request):
    profiles = InnovatorProfile.objects.select_related("user")
    query = request.GET.get("q", "").strip()
    if query:
        profiles = profiles.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(registration_number__icontains=query)
            | Q(innovation_project_name__icontains=query)
            | Q(projects__name__icontains=query)
            | Q(projects__area_of_focus__icontains=query)
        ).distinct()
    page_obj = Paginator(profiles, 20).get_page(request.GET.get("page"))
    return render(request, "innovators/manage.html", {"page_obj": page_obj, "query": query})


@admin_required
def export_innovators(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"tsavo_hub_innovators_{timezone.localdate():%Y-%m-%d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(["Full name", "Email", "Projects", "Areas of focus"])
    profiles = (
        InnovatorProfile.objects.select_related("user")
        .prefetch_related("projects")
        .order_by("user__last_name", "user__first_name", "user__email")
    )
    for profile in profiles:
        projects = list(profile.projects.all())
        writer.writerow(
            [
                _spreadsheet_safe(profile.user.get_full_name()),
                _spreadsheet_safe(profile.user.email),
                _spreadsheet_safe("; ".join(project.name for project in projects)),
                _spreadsheet_safe("; ".join(project.area_of_focus for project in projects)),
            ]
        )
    return response


@admin_required
def innovator_create(request):
    form = InnovatorCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            profile = create_innovator(
                form.cleaned_data,
                actor=request.user,
                request=request,
            )
        except TemporaryCredentialDeliveryError as exc:
            profile = InnovatorProfile.objects.filter(
                user__email__iexact=form.cleaned_data["email"]
            ).first()
            messages.error(request, str(exc))
            if profile is not None:
                return redirect("innovators:detail", pk=profile.pk)
            form.add_error(None, str(exc))
            return render(request, "innovators/create.html", {"form": form})
        messages.success(
            request,
            f"Account added for {profile.user.get_full_name()}. Temporary login credentials were emailed.",
        )
        return redirect("innovators:create-success", pk=profile.pk)
    return render(request, "innovators/create.html", {"form": form})


@admin_required
def create_success(request, pk):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
    return render(request, "innovators/create_success.html", {"profile": profile})


@admin_required
def innovator_detail(request, pk):
    profile = get_object_or_404(
        InnovatorProfile.objects.select_related("user").prefetch_related("projects"), pk=pk
    )
    bookings = profile.user.hub_bookings.order_by("-visit_date", "-arrival_time")
    recent_bookings = list(bookings[:10])
    return render(
        request,
        "innovators/detail.html",
        {
            "profile": profile,
            "recent_bookings": recent_bookings,
            "booking_count": bookings.count(),
            "projects": profile.projects.all(),
        },
    )


@admin_required
def innovator_update(request, pk):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
    form = InnovatorAdminUpdateForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        try:
            _, email_changed = update_innovator(
                form,
                actor=request.user,
                request=request,
            )
        except TemporaryCredentialDeliveryError as exc:
            messages.error(request, str(exc))
            return redirect("innovators:detail", pk=profile.pk)
        if email_changed:
            messages.success(
                request,
                "Innovator information updated. New temporary login credentials were sent to the changed email.",
            )
        else:
            messages.success(request, "Innovator information updated.")
        return redirect("innovators:detail", pk=profile.pk)
    return render(request, "innovators/update.html", {"form": form, "profile": profile})


@admin_required
@require_http_methods(["GET", "POST"])
def innovator_delete(request, pk):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
    if request.method == "POST":
        if request.POST.get("confirmation") != "permanently-delete":
            messages.error(request, "Confirm the permanent deletion before continuing.")
        else:
            try:
                permanently_delete_innovator(
                    profile,
                    actor=request.user,
                    request=request,
                )
            except InnovatorDeletionError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    "The innovator account and all associated records were permanently deleted.",
                )
                return redirect("innovators:manage")
    return render(
        request,
        "innovators/confirm_delete.html",
        {
            "profile": profile,
            "project_count": profile.projects.count(),
            "booking_count": profile.user.hub_bookings.count(),
            "attendance_count": profile.user.attendance_sessions.count(),
        },
    )


@admin_required
@require_POST
def toggle_status(request, pk):
    with transaction.atomic():
        profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
        user = User.objects.select_for_update().get(pk=profile.user_id)
        previous = user.account_status
        if user.account_status == User.AccountStatus.INACTIVE:
            user.account_status = (
                User.AccountStatus.PENDING
                if user.must_change_password
                else User.AccountStatus.ACTIVE
            )
            user.is_active = True
            action = AuditLog.Action.ACCOUNT_UPDATED
            message = "Account access restored."
        else:
            user.account_status = User.AccountStatus.INACTIVE
            user.is_active = False
            action = AuditLog.Action.ACCOUNT_DEACTIVATED
            message = "Account deactivated."
        user.save(update_fields=["account_status", "is_active", "date_updated"])
        record_audit(
            actor=request.user,
            action=action,
            target=user,
            previous_values={"account_status": previous},
            new_values={"account_status": user.account_status},
            reason=request.POST.get("reason", "Administrator account status change"),
            request=request,
        )
        if user.account_status == User.AccountStatus.INACTIVE:
            transaction.on_commit(lambda: send_deactivation_email(user), robust=True)
    messages.success(request, message)
    return redirect("innovators:detail", pk=profile.pk)


@admin_required
@require_POST
def admin_reissue_credentials(request, pk):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
    try:
        issue_temporary_credentials(
            profile.user,
            reissued=True,
            actor=request.user,
            request=request,
        )
    except TemporaryCredentialError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "New temporary login credentials were emailed.")
    return redirect("innovators:detail", pk=profile.pk)


@innovator_required
def my_profile(request):
    profile = get_object_or_404(
        InnovatorProfile.objects.select_related("user").prefetch_related("projects"),
        user=request.user,
    )
    return render(
        request,
        "innovators/profile.html",
        {"profile": profile, "projects": profile.projects.all()},
    )


@innovator_required
def my_projects(request):
    profile = get_object_or_404(
        InnovatorProfile.objects.select_related("user").prefetch_related("projects"),
        user=request.user,
    )
    form = InnovatorProjectForm(request.POST or None, profile=profile)
    if request.method == "POST" and form.is_valid():
        try:
            project = create_project(
                profile,
                **form.cleaned_data,
                actor=request.user,
                request=request,
            )
        except ProjectError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f'Project "{project.name}" was added to your portfolio.')
            return redirect("innovators:projects")
    return render(
        request,
        "innovators/projects.html",
        {
            "form": form,
            "projects": profile.projects.all(),
            "project_count": profile.projects.count(),
        },
    )
@innovator_required
def edit_my_profile(request):
    profile = get_object_or_404(InnovatorProfile, user=request.user)
    form = InnovatorSelfUpdateForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile was updated.")
        return redirect("innovators:profile")
    return render(request, "innovators/profile_edit.html", {"form": form})
