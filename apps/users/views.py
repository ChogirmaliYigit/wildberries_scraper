from django.shortcuts import get_object_or_404
from drf_yasg import openapi, utils
from rest_framework import permissions, response, status, views
from users.models import OTPTypes, Token, User
from users.serializers import (
    ConfirmationSerializer,
    ForgotPasswordSerializer,
    SendOTPSerializer,
    SignInResponseSerializer,
    SignInSerializer,
    SignUpSerializer,
    UserSerializer,
)
from users.utils import send_otp, sign_in_response


class SignUpView(views.APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = SignUpSerializer

    @utils.swagger_auto_schema(request_body=serializer_class, responses={200: "{}"})
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_otp(user, OTPTypes.REGISTER)
        return response.Response({}, status.HTTP_200_OK)


class ResendCodeView(views.APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = SendOTPSerializer

    @utils.swagger_auto_schema(request_body=serializer_class, responses={200: "{}"})
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_otp(serializer.save(), OTPTypes.REGISTER)
        return response.Response({}, status.HTTP_200_OK)


class SignInView(views.APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = SignInSerializer

    @utils.swagger_auto_schema(
        request_body=serializer_class, responses={200: SignInResponseSerializer()}
    )
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return response.Response(sign_in_response(user), status.HTTP_200_OK)


class SignOutView(views.APIView):
    token_class = Token

    def delete(self, request):
        self.token_class.objects.filter(
            user=request.user, key=request.auth.key
        ).delete()
        return response.Response({}, status.HTTP_204_NO_CONTENT)


class ConfirmationView(views.APIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ConfirmationSerializer

    @utils.swagger_auto_schema(
        request_body=serializer_class, responses={200: SignInResponseSerializer()}
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return response.Response(
            sign_in_response(serializer.save()), status.HTTP_200_OK
        )


class UserDetailView(views.APIView):
    serializer_class = UserSerializer

    @utils.swagger_auto_schema(responses={200: serializer_class()})
    def get(self, request):
        serializer = self.serializer_class(request.user)
        return response.Response(serializer.data, status.HTTP_200_OK)

    @utils.swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "full_name": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL
                ),
                "profile_photo": openapi.Schema(type=openapi.TYPE_FILE),
            },
        ),
        responses={200: "{}"},
    )
    def put(self, request):
        serializer = self.serializer_class(
            instance=request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response({}, status.HTTP_200_OK)

    @utils.swagger_auto_schema(responses={200: "{}"})
    def delete(self, request):
        user = get_object_or_404(User, pk=request.user.pk)
        user.delete()
        return response.Response({}, status.HTTP_200_OK)


class ForgotPasswordView(views.APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = ForgotPasswordSerializer

    @utils.swagger_auto_schema(request_body=serializer_class, responses={200: "{}"})
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response({}, status.HTTP_200_OK)


class SendForgotPasswordOTPView(views.APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = SendOTPSerializer

    @utils.swagger_auto_schema(request_body=serializer_class, responses={200: "{}"})
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_otp(serializer.save(), OTPTypes.FORGOT_PASSWORD)
        return response.Response({}, status.HTTP_200_OK)
