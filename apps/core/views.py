from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated


class BaseListCreateAPIView(generics.ListCreateAPIView):
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_permissions(self):
        if self.request.method in ["GET"]:
            return [AllowAny()]
        return [IsAuthenticated()]


class BaseListAPIView(generics.ListAPIView):
    permission_classes = (AllowAny,)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
