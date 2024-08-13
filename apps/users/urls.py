from django.urls import include, path
from users.views import (
    ConfirmationView,
    ForgotPasswordView,
    SendForgotPasswordOTPView,
    SignInView,
    SignOutView,
    SignUpView,
    UserDetailView,
    VerifyForgotPasswordOTPView,
)

urlpatterns = [
    path("login", SignInView.as_view(), name="user-sign-in"),
    path("register", SignUpView.as_view(), name="user-sign-up"),
    path("logout", SignOutView.as_view(), name="user-logout"),
    path("confirmation", ConfirmationView.as_view(), name="otp-confirmation"),
    path("user", UserDetailView.as_view(), name="user-detail"),
    path(
        "reset-password/",
        include(
            [
                path("", ForgotPasswordView.as_view(), name="forgot-password"),
                path(
                    "code",
                    SendForgotPasswordOTPView.as_view(),
                    name="send-forgot-password-otp",
                ),
                path(
                    "verify",
                    VerifyForgotPasswordOTPView.as_view(),
                    name="verify-forgot-password-otp",
                ),
            ]
        ),
    ),
]
