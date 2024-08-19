from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated


class BaseListCreateAPIView(generics.ListCreateAPIView):
    def get_permissions(self):
        if self.request.method in ["GET"]:
            return [AllowAny()]
        return [IsAuthenticated()]


class BaseListAPIView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
