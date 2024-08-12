import binascii
import os
from datetime import timedelta

from core.models import BaseModel
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.users.queryset.user import UserManager


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    full_name = models.CharField(max_length=1000, null=True, blank=True)
    username = None
    email = models.EmailField(unique=True)
    profile_photo = models.ImageField(
        upload_to="users/profile_photos/", null=True, blank=True
    )

    is_staff = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"


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


class UserOTP(BaseModel):
    user: User = models.ForeignKey(User, on_delete=models.CASCADE)
    code: str = models.CharField(max_length=10)
