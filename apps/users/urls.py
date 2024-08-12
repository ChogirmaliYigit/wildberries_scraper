from django.urls import path
from users.views import ConfirmationView, SignInView, SignUpView, UserDetailView

urlpatterns = [
    path("login", SignInView.as_view(), name="user-sign-in"),
    path("register", SignUpView.as_view(), name="user-sign-up"),
    path("confirmation", ConfirmationView.as_view(), name="otp-confirmation"),
    path("user", UserDetailView.as_view(), name="user-detail"),
]
