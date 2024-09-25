from core.views import BaseListAPIView, BaseListCreateAPIView
from django.core.cache import cache
from django.db.models import (
    Case,
    CharField,
    IntegerField,
    OuterRef,
    Subquery,
    Value,
    When,
)
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
    search_fields = ["title", "category__title"]
    ordering = []

    def get_queryset(self):
        cache_key = "filtered_products"
        queryset = cache.get(cache_key)
        if not queryset:
            queryset = get_filtered_products()
            cache.set(cache_key, queryset, timeout=300)
        return queryset


class ProductDetailView(views.APIView):
    serializer_class = ProductsSerializer
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request, pk):
        product = get_filtered_products().filter(pk=pk).first()
        if not product:
            raise exceptions.ValidationError({"message": "Товар недоступен"})
        serializer = self.serializer_class(product, context={"request": request})
        return response.Response(serializer.data, status.HTTP_200_OK)


class CommentsListView(BaseListCreateAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    ordering = []

    def get_queryset(self):
        cache_key = "comments_list"
        queryset = cache.get(cache_key)
        if not queryset:
            queryset = get_filtered_comments(
                Comment.objects.filter(reply_to__isnull=False), has_file=False
            )
            cache.set(cache_key, queryset, timeout=300)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["replies"] = True
        return context


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
        cache_key = f"user_comments_list_{self.request.user.id}"
        queryset = cache.get(cache_key)
        if not queryset:
            queryset = get_filtered_comments(
                Comment.objects.filter(reply_to__isnull=False, user=self.request.user),
                False,
            )
            cache.set(cache_key, queryset, timeout=300)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user_feedback"] = True
        context["replies"] = True
        return context


class FeedbacksListView(BaseListCreateAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter

    def get_queryset(self):
        cache_key = "feedbacks_list"
        queryset = cache.get(cache_key)
        if not queryset:
            queryset = get_filtered_comments(
                Comment.objects.filter(reply_to__isnull=True),
                True,
            )
            cache.set(cache_key, queryset, timeout=300)
        return queryset


class UserFeedbacksListView(BaseListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter

    def get_queryset(self):
        cache_key = f"user_feedbacks_list_{self.request.user.id}"
        queryset = cache.get(cache_key)
        if not queryset:
            queryset = get_filtered_comments(
                Comment.objects.filter(reply_to__isnull=True, user=self.request.user),
                True,
            )
            cache.set(cache_key, queryset, timeout=300)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user_feedback"] = True
        return context


class FavoritesListView(BaseListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = FavoritesSerializer
    search_fields = [
        "product__title",
    ]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        # Get filtered products with img_link annotation
        filtered_products = get_filtered_products()

        # Annotate the img_link from the filtered_products into the Favorite queryset
        products_with_img_link = filtered_products.filter(
            id=OuterRef("product_id")
        ).values("img_link")[:1]

        queryset = (
            Favorite.objects.filter(
                user=self.request.user, product__in=filtered_products
            )
            .select_related("product")
            .prefetch_related("user")
            .annotate(
                img_link=Subquery(products_with_img_link, output_field=CharField())
            )
            .order_by("-id")
        )

        return queryset


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
    permission_classes = (IsAuthenticated,)

    @utils.swagger_auto_schema(responses={200: "{'favorite': true'"})
    def post(self, request, product_id):
        return response.Response(
            {"favorite": make_favorite(request, product_id, Favorite)},
            status.HTTP_200_OK,
        )


class LikeView(views.APIView):
    permission_classes = (IsAuthenticated,)

    @utils.swagger_auto_schema(responses={200: "{'liked': true'"})
    def post(self, request, product_id):
        return response.Response(
            {"liked": make_favorite(request, product_id, Like)},
            status.HTTP_200_OK,
        )
