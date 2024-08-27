import binascii
import os
from datetime import timedelta
from typing import Literal

from core.models import BaseModel
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.users.queryset.user import UserManager


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    full_name = models.CharField(
        max_length=1000, null=True, blank=True, verbose_name=_("Full name")
    )
    username = None
    email = models.EmailField(
        unique=True,
        verbose_name=_("Email"),
        error_messages={
            "unique": "Пользователь с таким адресом электронной почты уже существует"
        },
    )
    profile_photo = models.ImageField(
        upload_to="users/profile_photos/",
        null=True,
        blank=True,
        verbose_name=_("Profile photo"),
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False, verbose_name=_("Is blocked"))

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users_users"
        verbose_name = _("User")
        verbose_name_plural = _("Users")


class Token(BaseModel):
    key = models.CharField(max_length=40, unique=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, models.CASCADE, related_name="tokens")
    expires_at = models.DateTimeField(null=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = binascii.hexlify(os.urandom(20)).decode()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.key

    class Meta:
        db_table = "user_tokens"


class OTPTypes(models.TextChoices):
    REGISTER = "register", _("Register")
    FORGOT_PASSWORD = "forgot_password", _("Forgot password")


class UserOTP(BaseModel):
    user: User = models.ForeignKey(User, on_delete=models.CASCADE)
    code: str = models.CharField(max_length=10)
    type: Literal[OTPTypes.REGISTER, OTPTypes.FORGOT_PASSWORD] = models.CharField(
        max_length=20, choices=OTPTypes.choices, default=OTPTypes.REGISTER
    )
