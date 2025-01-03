"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Wildberries scraper API",
        default_version="v1",
        description="Wildberries scraper backend",
        contact=openapi.Contact(
            email="chogirmali.yigit@gmail.com", url="https://t.me/chogirmali_yigit"
        ),
    ),
    public=True,
    permission_classes=[
        permissions.AllowAny,
    ],
    url=settings.BACKEND_DOMAIN,
)

urlpatterns = [
    path(
        "api/",
        include(
            [
                path(
                    "v1/",
                    include(
                        [
                            path("users/", include("users.urls")),
                            path("wildberries/", include("scraper.urls")),
                        ]
                    ),
                ),
            ]
        ),
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("silk/", include("silk.urls", namespace="silk")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


urlpatterns.append(path("", admin.site.urls))
