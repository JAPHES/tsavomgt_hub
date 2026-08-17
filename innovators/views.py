from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.services import OTPResendCooldown, OTPVerificationError, issue_activation_otp
from auditlog.models import AuditLog
from auditlog.services import record_audit
from core.permissions import admin_required, innovator_required

from .forms import InnovatorAdminUpdateForm, InnovatorCreateForm, InnovatorSelfUpdateForm
from .models import InnovatorProfile
from .services import create_innovator, send_deactivation_email, update_innovator


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
        )
    page_obj = Paginator(profiles, 20).get_page(request.GET.get("page"))
    return render(request, "innovators/manage.html", {"page_obj": page_obj, "query": query})


@admin_required
def innovator_create(request):
    form = InnovatorCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        profile = create_innovator(form.cleaned_data, actor=request.user, request=request)
        messages.success(
            request,
            f"Account created for {profile.user.get_full_name()}. The activation code was emailed.",
        )
        return redirect("innovators:create-success", pk=profile.pk)
    return render(request, "innovators/create.html", {"form": form})


@admin_required
def create_success(request, pk):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
    return render(request, "innovators/create_success.html", {"profile": profile})


@admin_required
def innovator_detail(request, pk):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
    recent_sessions = profile.user.attendance_sessions.order_by("-check_in_at")[:10]
    return render(
        request,
        "innovators/detail.html",
        {"profile": profile, "recent_sessions": recent_sessions},
    )


@admin_required
def innovator_update(request, pk):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
    form = InnovatorAdminUpdateForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        _, email_changed = update_innovator(form, actor=request.user, request=request)
        if email_changed:
            messages.success(
                request,
                "Innovator information updated. The changed email must be activated with the new code sent.",
            )
        else:
            messages.success(request, "Innovator information updated.")
        return redirect("innovators:detail", pk=profile.pk)
    return render(request, "innovators/update.html", {"form": form, "profile": profile})


@admin_required
@require_POST
def toggle_status(request, pk):
    with transaction.atomic():
        profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
        user = User.objects.select_for_update().get(pk=profile.user_id)
        previous = user.account_status
        if user.account_status == User.AccountStatus.INACTIVE:
            user.account_status = (
                User.AccountStatus.ACTIVE if user.activation_completed else User.AccountStatus.PENDING
            )
            user.is_active = user.activation_completed
            action = AuditLog.Action.ACCOUNT_UPDATED
            message = "Account access restored."
        else:
            user.account_status = User.AccountStatus.INACTIVE
            user.is_active = False
            user.activation_otps.filter(
                used_at__isnull=True, invalidated_at__isnull=True
            ).update(invalidated_at=timezone.now())
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
def admin_resend_otp(request, pk):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), pk=pk)
    try:
        issue_activation_otp(profile.user, resent=True, actor=request.user, request=request)
    except OTPResendCooldown as exc:
        messages.warning(request, str(exc))
    except OTPVerificationError:
        messages.error(request, "An activation code cannot be sent for this account.")
    else:
        messages.success(request, "A new activation code was emailed.")
    return redirect("innovators:detail", pk=profile.pk)


@innovator_required
def my_profile(request):
    profile = get_object_or_404(InnovatorProfile.objects.select_related("user"), user=request.user)
    return render(request, "innovators/profile.html", {"profile": profile})


@innovator_required
def edit_my_profile(request):
    profile = get_object_or_404(InnovatorProfile, user=request.user)
    form = InnovatorSelfUpdateForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile was updated.")
        return redirect("innovators:profile")
    return render(request, "innovators/profile_edit.html", {"form": form})
