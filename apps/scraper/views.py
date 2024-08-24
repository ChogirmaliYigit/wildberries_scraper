from core.views import BaseListAPIView, BaseListCreateAPIView
from django.db.models import Count
from drf_yasg import utils
from rest_framework import exceptions, generics, response, status, views
from scraper.filters import CategoryFilter, CommentsFilter, ProductFilter
from scraper.models import Category, Comment, CommentStatuses, Favorite, Like, Product
from scraper.serializers import (
    CategoriesSerializer,
    CommentsSerializer,
    FavoritesSerializer,
    ProductsSerializer,
)


class CategoriesListView(BaseListAPIView):
    queryset = (
        Category.objects.filter(parent__isnull=True)
        .prefetch_related("parent")
        .order_by("-id")
    )
    serializer_class = CategoriesSerializer
    filterset_class = CategoryFilter
    search_fields = [
        "title",
    ]


class ProductsListView(BaseListAPIView):
    queryset = (
        Product.objects.annotate(images_count=Count("variants__images"))
        .filter(images_count__gt=0, product_comments__isnull=False)
        .prefetch_related("category", "variants__images")
        .distinct()
        .order_by("-id")
    )
    serializer_class = ProductsSerializer
    filterset_class = ProductFilter
    search_fields = ["title", "variants__color", "variants__price"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class ProductDetailView(generics.RetrieveAPIView):
    queryset = (
        Product.objects.annotate(images_count=Count("variants__images"))
        .filter(images_count__gt=0, product_comments__isnull=False)
        .prefetch_related("category", "variants__images")
        .distinct()
        .order_by("-id")
    )
    serializer_class = ProductsSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class CommentsListView(BaseListCreateAPIView):
    queryset = (
        Comment.objects.prefetch_related("product", "user", "reply_to")
        .filter(status=CommentStatuses.ACCEPTED, reply_to__isnull=False)
        .order_by("-id")
    )
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        context["comment"] = True
        return context


class UserCommentsListView(generics.ListAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]

    def get_queryset(self):
        queryset = Comment.objects.all()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
        return (
            queryset.prefetch_related("product", "user", "reply_to")
            .filter(
                status=CommentStatuses.ACCEPTED,
                reply_to__isnull=False,
            )
            .order_by("-id")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class FeedbacksListView(BaseListCreateAPIView):
    queryset = (
        Comment.objects.prefetch_related("product", "user", "reply_to")
        .filter(reply_to__isnull=True, status=CommentStatuses.ACCEPTED)
        .order_by("-id")
    )
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]


class UserFeedbacksListView(generics.ListAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]

    def get_queryset(self):
        queryset = Comment.objects.all()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
        return (
            queryset.prefetch_related("product", "user", "reply_to")
            .filter(
                status=CommentStatuses.ACCEPTED,
                reply_to__isnull=True,
            )
            .order_by("-id")
        )


class FavoritesListView(BaseListAPIView):
    serializer_class = FavoritesSerializer
    search_fields = [
        "product__title",
    ]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        queryset = Favorite.objects.all()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
        return queryset.prefetch_related("product", "user").order_by("-id")


class FavoriteView(views.APIView):
    @utils.swagger_auto_schema(responses={200: "{'favorite': true'"})
    def post(self, request, product_id):
        if not request.user.is_authenticated:
            raise exceptions.ValidationError({"message": "Пользователь не авторизован"})
        product = Product.objects.filter(pk=product_id).first()
        if not product:
            raise exceptions.ValidationError({"message": "Товар не найден"})
        favorite = Favorite.objects.filter(user=request.user, product=product).first()
        if favorite:
            favorite.delete()
            is_favorite = False
        else:
            Favorite.objects.create(user=request.user, product=product)
            is_favorite = True
        return response.Response({"favorite": is_favorite}, status.HTTP_200_OK)


class LikeView(views.APIView):
    @utils.swagger_auto_schema(responses={200: "{'liked': true'"})
    def post(self, request, product_id):
        if not request.user.is_authenticated:
            raise exceptions.ValidationError({"message": "Пользователь не авторизован"})
        product = Product.objects.filter(pk=product_id).first()
        if not product:
            raise exceptions.ValidationError({"message": "Товар не найден"})
        like = Like.objects.filter(user=request.user, product=product).first()
        if like:
            like.delete()
            liked = False
        else:
            Like.objects.create(user=request.user, product=product)
            liked = True
        return response.Response({"liked": liked}, status.HTTP_200_OK)
