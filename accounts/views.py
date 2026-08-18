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
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST

from .forms import (
    EmailAuthenticationForm,
    FirstLoginPasswordChangeForm,
    TsavoPasswordChangeForm,
    TsavoPasswordResetForm,
)
from .services import (
    TemporaryCredentialError,
    complete_first_login_password_change,
)


class TsavoLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.must_change_password:
            return reverse("accounts:first-login-password-change")
        return super().get_success_url()


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out safely.")
    return redirect("accounts:login")


@login_required
def first_login_password_change(request):
    if not request.user.must_change_password:
        return redirect("dashboard:index")
    form = FirstLoginPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_first_login_password_change(
                request.user.pk,
                form.cleaned_data["new_password1"],
                request=request,
            )
        except TemporaryCredentialError as exc:
            form.add_error(None, str(exc))
        else:
            logout(request)
            messages.success(
                request,
                "Your personal password is ready. Sign in again using your email and new password.",
            )
            return redirect("accounts:login")
    return render(request, "accounts/first_login_password_change.html", {"form": form})


class TsavoPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    form_class = TsavoPasswordResetForm
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
    form_class = TsavoPasswordChangeForm
    success_url = reverse_lazy("accounts:password-change-done")


class TsavoPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"
