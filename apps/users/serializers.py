from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from rest_framework import exceptions, serializers
from scraper.models import Favorite
from scraper.utils.queryset import get_comments
from users.models import OTPTypes, Token, User, UserOTP


class SignUpSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, trim_whitespace=True)

    def create(self, validated_data):
        email = validated_data.get("email")
        if User.objects.filter(email=email).exists():
            raise exceptions.ValidationError(
                {
                    "message": "Пользователь с таким адресом электронной почты уже существует"
                }
            )
        user = User.objects.create_user(
            email=email,
            password=validated_data.get("password"),
            full_name=validated_data.get("full_name"),
            is_active=False,
        )
        return user

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "full_name",
        )
        extra_kwargs = {
            "password": {"write_only": True},
        }


class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, trim_whitespace=True)
    password = serializers.CharField(required=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            email=attrs.get("email").lower(),
            password=attrs.get("password"),
        )

        if not user:
            raise serializers.ValidationError(
                {"message": "Неправильный адрес электронной почты или пароль"},
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {"message": "Пользователь неактивен"},
            )

        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if isinstance(instance, User):
            photo = f"{settings.BACKEND_DOMAIN.strip('/')}{settings.MEDIA_URL}{instance.profile_photo}"
            data["favorites_count"] = Favorite.objects.filter(user=instance).count()
            data["feedbacks_count"] = get_comments(
                reply_to__isnull=True, user=instance
            ).count()
            data["comments_count"] = get_comments(
                comment=True, reply_to__isnull=False, user=instance
            ).count()
        elif isinstance(instance, dict):
            photo = instance.get("profile_photo", "")
        else:
            photo = None
        if photo:
            data["profile_photo"] = photo
        return data

    def update(self, instance, validated_data):
        email = validated_data.pop("email", None)
        password = validated_data.pop("password", None)

        # Update the instance fields if they are not None
        if email is not None or email != "":
            validated_data["email"] = email
        else:
            validated_data["email"] = instance.email
        if password is not None or password != "":
            # Set password only if it's not None and not empty string
            if password:
                instance.set_password(password)

        return super().update(instance, validated_data)

    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "profile_photo",
            "password",
        )


class SignInResponseSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=40)
    user = UserSerializer()


class ConfirmationSerializer(serializers.Serializer):
    email = serializers.EmailField(trim_whitespace=True)
    code = serializers.CharField(max_length=10)

    def create(self, validated_data):
        user = User.objects.filter(email=validated_data.get("email")).first()
        if not user:
            raise exceptions.ValidationError({"message": "Пользователь не существует"})
        user_otp = UserOTP.objects.filter(
            user=user, code=validated_data.get("code"), type=OTPTypes.REGISTER
        ).last()
        if not user_otp or validated_data.get("code") == settings.DEFAULT_OTP_CODE:
            raise exceptions.ValidationError({"message": "Неправильный код"})
        user_otp.delete()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return user


class TokenSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["token"] = instance.key
        data["user"] = UserSerializer(instance.user).data
        return data

    class Meta:
        model = Token
        fields = []


class ForgotPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(required=True)
    re_password = serializers.CharField(required=True)
    code = serializers.CharField()
    email = serializers.EmailField(trim_whitespace=True)

    def create(self, validated_data):
        password = validated_data.get("password", None)
        re_password = validated_data.get("re_password", None)
        user = User.objects.filter(email=validated_data.get("email")).first()
        if not user:
            raise exceptions.ValidationError({"message": "Пользователь не существует"})
        if (not password or not re_password) or password != re_password:
            raise exceptions.ValidationError({"message": "Пароль не совпал"})
        otp_code = UserOTP.objects.filter(
            user=user,
            code=validated_data.get("code"),
            type=OTPTypes.FORGOT_PASSWORD,
        ).last()
        if not otp_code or validated_data.get("code") == settings.DEFAULT_OTP_CODE:
            raise exceptions.ValidationError({"message": "Неправильный код"})
        user.password = make_password(password)
        user.save(update_fields=["password"])
        otp_code.delete()
        return user


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(trim_whitespace=True)

    def create(self, validated_data):
        user = User.objects.filter(email=validated_data.get("email")).first()
        if not user:
            raise exceptions.ValidationError({"message": "Пользователь не существует"})
        user_otp = UserOTP.objects.filter(
            user=user, code=validated_data.get("code"), type=OTPTypes.REGISTER
        ).last()
        if user_otp:
            user_otp.delete()
        return user
