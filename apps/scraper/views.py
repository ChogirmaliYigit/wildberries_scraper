from core.views import BaseListAPIView, BaseListCreateAPIView
from django.db.models import Case, IntegerField, Value, When
from drf_yasg import utils
from rest_framework import exceptions, generics, permissions, response, status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
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
        .annotate(
            custom_order=Case(
                When(
                    position=0, then=Value(1)
                ),  # Categories with position=0 are treated as lower priority
                default=Value(
                    0
                ),  # Categories with position > 0 are treated as higher priority
                output_field=IntegerField(),
            )
        )
        .order_by(
            "custom_order", "-position"
        )  # Order by custom_order first, then by position in descending order
    )
    serializer_class = CategoriesSerializer
    search_fields = [
        "title",
    ]


class ProductsListView(BaseListAPIView):
    serializer_class = ProductsSerializer
    filterset_class = ProductFilter
    search_fields = ["title", "variants__color", "variants__price"]
    ordering = []

    def get_queryset(self):
        queryset = get_filtered_products()
        return queryset


class ProductDetailView(views.APIView):
    serializer_class = ProductsSerializer
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request, pk):
        product = Product.objects.filter(pk=pk).first()
        if not product:
            raise exceptions.ValidationError({"message": "Товар недоступен"})
        serializer = self.serializer_class(product, context={"request": request})
        return response.Response(serializer.data, status.HTTP_200_OK)


class CommentsListView(BaseListCreateAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    ordering = []

    def get_queryset(self):
        queryset = (
            Comment.objects.filter(reply_to__isnull=False)
            .select_related("product", "user", "reply_to")
            .prefetch_related("files", "replies")
        )
        return get_filtered_comments(queryset, has_file=False)


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentDetailSerializer
    permission_classes = [
        permissions.IsAuthenticated,
    ]
    ordering = []

    def get_queryset(self):
        return Comment.objects.filter(user=self.request.user)

    def get_object(self):
        obj = self.get_queryset().filter(pk=self.kwargs["pk"]).first()
        if not obj:
            raise exceptions.ValidationError({"message": "Комментарий не найден"})
        return obj


class UserCommentsListView(BaseListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter

    def get_queryset(self):
        queryset = Comment.objects.filter(
            reply_to__isnull=False, user=self.request.user
        )
        return get_filtered_comments(queryset, False)


class FeedbacksListView(BaseListCreateAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter

    def get_queryset(self):
        queryset = Comment.objects.filter(reply_to__isnull=True)
        return get_filtered_comments(queryset, True)


class UserFeedbacksListView(BaseListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter

    def get_queryset(self):
        queryset = Comment.objects.filter(reply_to__isnull=True, user=self.request.user)
        return get_filtered_comments(queryset, True)


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
