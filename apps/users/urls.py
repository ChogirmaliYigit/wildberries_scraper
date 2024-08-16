from django.urls import path
from users.views import (
    ConfirmationView,
    ForgotPasswordView,
    ResendCodeView,
    SendForgotPasswordOTPView,
    SignInView,
    SignOutView,
    SignUpView,
    UserDetailView,
)

urlpatterns = [
    path("login", SignInView.as_view(), name="user-sign-in"),
    path("register", SignUpView.as_view(), name="user-sign-up"),
    path("resend-code", ResendCodeView.as_view(), name="resend-code"),
    path("logout", SignOutView.as_view(), name="user-logout"),
    path("confirmation", ConfirmationView.as_view(), name="otp-confirmation"),
    path("user", UserDetailView.as_view(), name="user-detail"),
    path("reset-password", ForgotPasswordView.as_view(), name="forgot-password"),
    path("code", SendForgotPasswordOTPView.as_view(), name="send-forgot-password-otp"),
]
