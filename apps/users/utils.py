import binascii
import os
import random
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from users.models import Token, User, UserOTP
from users.serializers import SignInResponseSerializer, UserSerializer


def sign_in_response(user):
    permissions = list(user.get_all_permissions())
    token, created = Token.objects.update_or_create(
        user=user,
        defaults={
            "key": binascii.hexlify(os.urandom(20)).decode(),
            "expires_at": timezone.now() + timedelta(days=30),
        },
    )
    user_data = UserSerializer(user).data
    data = {"token": token.key, "user": user_data, "permissions": permissions}
    return SignInResponseSerializer(data).data


class CustomTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        token = (
            Token.objects.select_related("user")
            .filter(key=key, expires_at__gte=timezone.now())
            .first()
        )

        if token is None:
            raise AuthenticationFailed(
                {"detail": "Недействительный или просроченный токен.", "logout": "true"}
            )

        if not token.user.is_active:
            raise AuthenticationFailed(
                {"detail": "Пользователь неактивен или удален.", "logout": "true"}
            )

        if not token.is_active:
            raise AuthenticationFailed(
                {"detail": "Ваш токен не активен.", "logout": "true"}
            )

        return token.user, token


def generate_otp_code(length: int = 6) -> str:
    return "".join(random.choices(range(1, 10), k=length))


def send_email(users: list[str], subject: str, message: str):
    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=users,
    )


def send_otp(user: User, type_: str):
    code = generate_otp_code() if not settings.DEBUG else "000000"
    UserOTP.objects.create(user=user, code=code, type=type_)
    if not settings.DEBUG:
        return send_email(
            [user.email],
            "Подтверждение по электронной почте для Озро",
            f"Ваш код: {code}",
        )
    return None
