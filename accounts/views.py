from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import (
    ActivationPasswordForm,
    ActivationVerificationForm,
    EmailAuthenticationForm,
    ResendOTPForm,
)
from .models import AccountActivationOTP, User
from .services import (
    OTPResendCooldown,
    OTPVerificationError,
    complete_activation,
    issue_activation_otp,
    verify_activation_otp,
)


class TsavoLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out safely.")
    return redirect("accounts:login")


def activate_account(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    form = ActivationVerificationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user, otp = verify_activation_otp(form.cleaned_data["email"], form.cleaned_data["otp"])
        except OTPVerificationError as exc:
            form.add_error(None, str(exc))
        else:
            request.session["activation_user_id"] = user.pk
            request.session["activation_otp_id"] = otp.pk
            request.session.set_expiry(15 * 60)
            return redirect("accounts:activation-password")
    return render(request, "accounts/activate.html", {"form": form})


def create_activation_password(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    user_id = request.session.get("activation_user_id")
    otp_id = request.session.get("activation_otp_id")
    try:
        user = User.objects.get(pk=user_id)
        otp = AccountActivationOTP.objects.get(pk=otp_id, user=user)
    except (User.DoesNotExist, AccountActivationOTP.DoesNotExist, TypeError, ValueError):
        messages.error(request, "Verify a valid activation code before creating your password.")
        return redirect("accounts:activate")
    if not otp.is_usable:
        request.session.pop("activation_user_id", None)
        request.session.pop("activation_otp_id", None)
        messages.error(request, "Your activation session expired. Request a new code.")
        return redirect("accounts:activate")
    form = ActivationPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_activation(user.pk, otp.pk, form.cleaned_data["new_password1"], request=request)
        except OTPVerificationError as exc:
            form.add_error(None, str(exc))
        else:
            request.session.flush()
            messages.success(request, "Your account is active. You can now log in.")
            return redirect("accounts:login")
    return render(request, "accounts/activation_password.html", {"form": form})


def resend_otp(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    form = ResendOTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.filter(
            email__iexact=form.cleaned_data["email"], activation_completed=False
        ).first()
        if user:
            try:
                issue_activation_otp(user, resent=True, request=request)
            except (OTPResendCooldown, OTPVerificationError):
                pass
        messages.success(
            request,
            "If the account is eligible, a new activation code has been sent. Please also check spam.",
        )
        return redirect("accounts:activate")
    return render(request, "accounts/resend_otp.html", {"form": form})


class TsavoPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "emails/password_reset.txt"
    html_email_template_name = "emails/password_reset.html"
    subject_template_name = "emails/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password-reset-done")


class TsavoPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class TsavoPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password-reset-complete")


class TsavoPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class TsavoPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("accounts:password-change-done")


class TsavoPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"
