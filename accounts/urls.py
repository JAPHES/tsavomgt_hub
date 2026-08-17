from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.TsavoLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("activate/", views.activate_account, name="activate"),
    path("activate/password/", views.create_activation_password, name="activation-password"),
    path("resend-otp/", views.resend_otp, name="resend-otp"),
    path("password-reset/", views.TsavoPasswordResetView.as_view(), name="password-reset"),
    path("password-reset/done/", views.TsavoPasswordResetDoneView.as_view(), name="password-reset-done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.TsavoPasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password-reset/complete/",
        views.TsavoPasswordResetCompleteView.as_view(),
        name="password-reset-complete",
    ),
    path("password-change/", views.TsavoPasswordChangeView.as_view(), name="password-change"),
    path(
        "password-change/done/",
        views.TsavoPasswordChangeDoneView.as_view(),
        name="password-change-done",
    ),
]
