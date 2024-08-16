from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from rest_framework import exceptions, serializers
from users.models import OTPTypes, Token, User, UserOTP


class SignUpSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        email = validated_data.get("email")
        if User.objects.filter(email=email).exists():
            raise exceptions.ValidationError(
                {"message": "User with this email already exists"}
            )
        user = User.objects.create_user(
            email=email,
            password=validated_data.get("password"),
            full_name=validated_data.get("full_name"),
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
            request=self.context.get("request"),
            email=attrs.get("email").lower(),
            password=attrs.get("password"),
        )

        if not user:
            raise serializers.ValidationError({"message": "Wrong email or password"})

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
        extra_kwargs = {"password": {"write_only": True}}


class SignInResponseSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=40)
    user = UserSerializer()
    permissions = serializers.ListField()


class ConfirmationSerializer(serializers.Serializer):
    email = serializers.EmailField(trim_whitespace=True)
    code = serializers.CharField(max_length=10)

    def create(self, validated_data):
        user = User.objects.filter(email=validated_data.get("email")).first()
        if not user:
            raise exceptions.ValidationError({"message": "User not exists"})
        user_otp = UserOTP.objects.filter(
            user=user, code=validated_data.get("code"), type=OTPTypes.REGISTER
        ).first()
        if not user_otp:
            raise exceptions.ValidationError({"message": "Wrong OTP"})
        user_otp.delete()
        return user


class TokenSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["token"] = instance.key
        data["user"] = UserSerializer(instance.user).data
        data["permissions"] = list(instance.user.get_all_permissions())
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
            raise exceptions.ValidationError({"message": "User not exists"})
        if (not password or not re_password) or password != re_password:
            raise exceptions.ValidationError({"message": "Password didn't match"})
        otp_code = UserOTP.objects.filter(
            user=user,
            code=validated_data.get("code"),
            type=OTPTypes.FORGOT_PASSWORD,
        ).last()
        if not otp_code:
            raise exceptions.ValidationError({"message": "Wrong OTP"})
        user.password = make_password(password)
        user.save(update_fields=["password"])
        otp_code.delete()
        return user


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(trim_whitespace=True)

    def create(self, validated_data):
        user = User.objects.filter(email=validated_data.get("email")).first()
        if not user:
            raise exceptions.ValidationError({"message": "User not exists"})
        return user
