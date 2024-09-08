from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from rest_framework import exceptions, serializers
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
            # request=self.context.get("request"),
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
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["profile_photo"] = (
            f"{settings.BACKEND_DOMAIN}{data.get('profile_photo')}"
            if data.get("profile_photo")
            else ""
        )
        return data

    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "profile_photo",
            "password",
        )
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "email": {"required": False},
        }


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
        if not user_otp:
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
        if not otp_code:
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
