from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import exceptions, serializers
from users.models import Token, User, UserOTP


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
        data["profile_photo"] = f"{settings.BACKEND_DOMAIN}{data.get('profile_photo')}"
        return data

    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "profile_photo",
        )


class SignInResponseSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=40)
    user = UserSerializer()
    permissions = serializers.ListField()


class ConfirmationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=10)

    def create(self, validated_data):
        user = User.objects.filter(email=validated_data.get("email")).first()
        if not user:
            raise exceptions.ValidationError({"message": "User not exists"})
        user_otp = UserOTP.objects.filter(
            user=user, code=validated_data.get("code")
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
