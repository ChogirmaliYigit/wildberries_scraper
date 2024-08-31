from core.views import BaseListAPIView, BaseListCreateAPIView
from drf_yasg import utils
from rest_framework import exceptions, generics, permissions, response, status, views
from scraper.filters import CommentsFilter, ProductFilter
from scraper.models import Category, Comment, Favorite, Like, Product
from scraper.serializers import (
    CategoriesSerializer,
    CommentDetailSerializer,
    CommentsSerializer,
    FavoritesSerializer,
    ProductsSerializer,
)
from scraper.utils.queryset import get_filtered_comments, get_filtered_products


class CategoriesListView(BaseListAPIView):
    queryset = (
        Category.objects.filter(parent__isnull=True)
        .prefetch_related("parent")
        .order_by("-id")
    )
    serializer_class = CategoriesSerializer
    search_fields = [
        "title",
    ]


class ProductsListView(BaseListAPIView):
    serializer_class = ProductsSerializer
    filterset_class = ProductFilter
    search_fields = ["title", "variants__color", "variants__price"]

    def get_queryset(self):
        return get_filtered_products()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductsSerializer

    def get_queryset(self):
        return get_filtered_products()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class CommentsListView(BaseListCreateAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]

    def get_queryset(self):
        return get_filtered_comments(Comment.objects.filter(reply_to__isnull=False))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        context["comment"] = True
        return context


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentDetailSerializer
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get_queryset(self):
        return (
            get_filtered_comments(Comment.objects.filter(user=self.request.user)) or []
        )


class UserCommentsListView(generics.ListAPIView):
    serializer_class = CommentDetailSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get_queryset(self):
        return get_filtered_comments(Comment.objects.filter(user=self.request.user))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class FeedbacksListView(BaseListCreateAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]

    def get_queryset(self):
        return get_filtered_comments(Comment.objects.filter(reply_to__isnull=True))


class UserFeedbacksListView(generics.ListAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]

    def get_queryset(self):
        if self.request.user.is_authenticated:
            queryset = Comment.objects.filter(
                user=self.request.user, reply_to__isnull=True
            )
            return get_filtered_comments(queryset)
        return Comment.objects.none()


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


def make_favorite(request, product_id, model):
    if not request.user.is_authenticated:
        raise exceptions.ValidationError({"message": "Пользователь не авторизован"})
    product = Product.objects.filter(pk=product_id).first()
    if not product:
        raise exceptions.ValidationError({"message": "Товар не найден"})
    _object = model.objects.filter(user=request.user, product=product).first()
    if _object:
        _object.delete()
        favorite = False
    else:
        model.objects.create(user=request.user, product=product)
        favorite = True
    return favorite


class FavoriteView(views.APIView):
    @utils.swagger_auto_schema(responses={200: "{'favorite': true'"})
    def post(self, request, product_id):
        return response.Response(
            {"favorite": make_favorite(request, product_id, Favorite)},
            status.HTTP_200_OK,
        )


class LikeView(views.APIView):
    @utils.swagger_auto_schema(responses={200: "{'liked': true'"})
    def post(self, request, product_id):
        return response.Response(
            {"liked": make_favorite(request, product_id, Like)},
            status.HTTP_200_OK,
        )
