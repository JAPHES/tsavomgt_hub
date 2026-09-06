import csv
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Min, Q
from django.http import FileResponse, Http404, HttpResponse
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
    InnovatorProfileCompletionForm,
    InnovatorProjectForm,
    InnovatorSelfUpdateForm,
    ProjectDirectoryFilterForm,
)
from .models import InnovatorProfile, InnovatorProject, ProjectFocusArea
from .services import (
    InnovatorDeletionError,
    ProjectError,
    create_innovator,
    create_project,
    permanently_delete_innovator,
    send_deactivation_email,
    update_innovator,
    update_project,
)


logger = logging.getLogger(__name__)


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
            | Q(projects__focus_areas__name__icontains=query)
        ).distinct()
    page_obj = Paginator(profiles, 20).get_page(request.GET.get("page"))
    return render(request, "innovators/manage.html", {"page_obj": page_obj, "query": query})


def filter_project_directory(queryset, cleaned_data):
    for term in cleaned_data.get("query", "").split():
        queryset = queryset.filter(
            Q(name__icontains=term)
            | Q(focus_areas__name__icontains=term)
            | Q(profile__user__first_name__icontains=term)
            | Q(profile__user__last_name__icontains=term)
            | Q(profile__user__email__icontains=term)
            | Q(profile__registration_number__icontains=term)
        )

    if technology_focus := cleaned_data.get("technology_focus"):
        queryset = queryset.filter(focus_areas__name=technology_focus)
    if county := cleaned_data.get("county"):
        queryset = queryset.filter(profile__county=county)

    for term in cleaned_data.get("area_of_study", "").split():
        queryset = queryset.filter(
            Q(profile__school__icontains=term)
            | Q(profile__department__icontains=term)
        )
    if school := cleaned_data.get("school"):
        queryset = queryset.filter(profile__school__icontains=school)
    if department := cleaned_data.get("department"):
        queryset = queryset.filter(profile__department__icontains=department)

    ordering = {
        "newest": ("-created_at", "name"),
        "project": ("name", "profile__user__last_name", "profile__user__first_name"),
        "innovator": ("profile__user__last_name", "profile__user__first_name", "name"),
        "county": ("profile__county", "name"),
        "school": ("profile__school", "name"),
        "department": ("profile__department", "name"),
    }
    if cleaned_data.get("sort_by") == "technology":
        return queryset.annotate(primary_focus=Min("focus_areas__name")).order_by(
            "primary_focus", "name"
        )
    selected_order = ordering.get(cleaned_data.get("sort_by"), ordering["newest"])
    return queryset.order_by(*selected_order).distinct()


@admin_required
def project_directory(request):
    technology_focuses = (
        ProjectFocusArea.objects.filter(projects__isnull=False)
        .order_by("name")
        .values_list("name", flat=True)
        .distinct()
    )
    form = ProjectDirectoryFilterForm(
        request.GET or None,
        technology_focuses=technology_focuses,
    )
    projects = InnovatorProject.objects.select_related("profile__user").prefetch_related(
        "focus_areas"
    )
    form_is_valid = form.is_valid()
    if form_is_valid:
        projects = filter_project_directory(projects, form.cleaned_data)
    elif form.is_bound:
        projects = projects.none()
    else:
        projects = projects.order_by("-created_at", "name")

    matched_count = projects.count()
    matching_profile_ids = projects.order_by().values_list("profile_id", flat=True).distinct()
    matched_innovator_count = matching_profile_ids.count()
    result_view = "projects"
    if form_is_valid:
        result_view = form.cleaned_data.get("result_view") or result_view

    if result_view == "innovators":
        innovator_ordering = {
            "county": ("county", "user__last_name", "user__first_name"),
            "school": ("school", "user__last_name", "user__first_name"),
            "department": ("department", "user__last_name", "user__first_name"),
        }
        selected_sort = form.cleaned_data.get("sort_by")
        results = (
            InnovatorProfile.objects.select_related("user")
            .filter(pk__in=matching_profile_ids)
            .order_by(
                *innovator_ordering.get(
                    selected_sort,
                    ("user__last_name", "user__first_name", "registration_number"),
                )
            )
        )
    else:
        results = projects

    page_obj = Paginator(results, 30).get_page(request.GET.get("page"))
    if result_view == "innovators":
        profiles_on_page = list(page_obj.object_list)
        project_counts = {
            row["profile_id"]: row["total"]
            for row in projects.filter(profile_id__in=[profile.pk for profile in profiles_on_page])
            .order_by()
            .values("profile_id")
            .annotate(total=Count("pk"))
        }
        for profile in profiles_on_page:
            profile.matching_project_count = project_counts.get(profile.pk, 0)
        page_obj.object_list = profiles_on_page

    pagination_parameters = request.GET.copy()
    pagination_parameters.pop("page", None)
    project_view_parameters = pagination_parameters.copy()
    project_view_parameters["result_view"] = "projects"
    innovator_view_parameters = pagination_parameters.copy()
    innovator_view_parameters["result_view"] = "innovators"
    filter_fields = (
        "query",
        "technology_focus",
        "county",
        "area_of_study",
        "school",
        "department",
    )
    return render(
        request,
        "innovators/project_directory.html",
        {
            "form": form,
            "page_obj": page_obj,
            "result_view": result_view,
            "matched_count": matched_count,
            "matched_innovator_count": matched_innovator_count,
            "total_projects": InnovatorProject.objects.count(),
            "filter_applied": bool(
                form.is_bound
                and form_is_valid
                and any(form.cleaned_data.get(field) for field in filter_fields)
            ),
            "pagination_query": pagination_parameters.urlencode(),
            "project_view_query": project_view_parameters.urlencode(),
            "innovator_view_query": innovator_view_parameters.urlencode(),
        },
    )


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
        .prefetch_related("projects__focus_areas")
        .order_by("user__last_name", "user__first_name", "user__email")
    )
    for profile in profiles:
        projects = list(profile.projects.all())
        writer.writerow(
            [
                _spreadsheet_safe(profile.user.get_full_name()),
                _spreadsheet_safe(profile.user.email),
                _spreadsheet_safe("; ".join(project.name for project in projects)),
                _spreadsheet_safe(
                    "; ".join(project.focus_area_names for project in projects)
                ),
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
        InnovatorProfile.objects.select_related("user").prefetch_related(
            "projects__focus_areas"
        ),
        pk=pk,
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
@require_http_methods(["GET", "POST"])
def complete_my_profile(request):
    profile = get_object_or_404(InnovatorProfile, user=request.user)
    if profile.has_completed_required_details:
        return redirect("innovators:profile")

    form = InnovatorProfileCompletionForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        previous_values = {
            field: getattr(profile, field)
            for field in ("gender", "school", "department", "county")
        }
        with transaction.atomic():
            profile = form.save()
            record_audit(
                actor=request.user,
                action=AuditLog.Action.ACCOUNT_UPDATED,
                target=request.user,
                previous_values=previous_values,
                new_values={
                    "gender": profile.gender,
                    "school": profile.school,
                    "department": profile.department,
                    "county": profile.county,
                },
                reason="Innovator completed required profile details",
                request=request,
            )
        messages.success(request, "Your profile is complete. Welcome to your dashboard.")
        return redirect("dashboard:innovator")
    return render(
        request,
        "innovators/profile_complete.html",
        {"form": form, "profile": profile},
    )


@innovator_required
def my_profile(request):
    profile = get_object_or_404(
        InnovatorProfile.objects.select_related("user").prefetch_related(
            "projects__focus_areas"
        ),
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
        InnovatorProfile.objects.select_related("user").prefetch_related(
            "projects__focus_areas"
        ),
        user=request.user,
    )
    form = InnovatorProjectForm(
        request.POST or None,
        request.FILES or None,
        profile=profile,
    )
    if request.method == "POST" and form.is_valid():
        try:
            project = create_project(
                profile,
                name=form.cleaned_data["name"],
                focus_areas=form.cleaned_data["focus_areas"],
                proposal=form.cleaned_data["proposal"],
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
def update_my_project(request, pk):
    profile = get_object_or_404(InnovatorProfile, user=request.user)
    project = get_object_or_404(
        InnovatorProject.objects.prefetch_related("focus_areas"),
        pk=pk,
        profile=profile,
    )
    form = InnovatorProjectForm(
        request.POST or None,
        request.FILES or None,
        instance=project,
        profile=profile,
    )
    if request.method == "POST" and form.is_valid():
        try:
            updated_project = update_project(
                project,
                name=form.cleaned_data["name"],
                focus_areas=form.cleaned_data["focus_areas"],
                proposal=request.FILES.get("proposal"),
                actor=request.user,
                request=request,
            )
        except ProjectError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f'Project "{updated_project.name}" was updated.',
            )
            return redirect("innovators:projects")
    return render(
        request,
        "innovators/project_update.html",
        {"form": form, "project": project},
    )


@login_required
def download_project_proposal(request, pk):
    project = get_object_or_404(
        InnovatorProject.objects.select_related("profile__user"),
        pk=pk,
    )
    if (
        request.user.role != User.Role.ADMIN
        and request.user.pk != project.profile.user_id
    ):
        raise PermissionDenied
    if not project.proposal:
        raise Http404("This project does not have an uploaded proposal.")
    try:
        proposal_file = project.proposal.open("rb")
    except OSError:
        logger.exception(
            "Project proposal delivery failed for project_id=%s and user_id=%s.",
            project.pk,
            request.user.pk,
        )
        messages.error(
            request,
            "The project proposal could not be downloaded right now. "
            "Please try again shortly or contact the hub administrator.",
        )
        if request.user.role == User.Role.ADMIN:
            return redirect("innovators:detail", pk=project.profile_id)
        return redirect("innovators:projects")
    return FileResponse(
        proposal_file,
        as_attachment=True,
        filename=f"{project.name} proposal.pdf",
        content_type="application/pdf",
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
