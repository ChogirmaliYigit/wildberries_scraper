from collections import OrderedDict

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
from scraper.utils.queryset import get_comments, get_products


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
    search_fields = ["title", "category__title", "image_link", "source_id", "id"]

    def filter_queryset(self, queryset):
        # Get the filtered and annotated queryset
        base_queryset = super().filter_queryset(queryset)

        # Separate promoted products
        promoted_product = (
            base_queryset.filter(promoted=True).distinct().order_by("?").first()
        )

        # Fetch the first two products from the base queryset
        first_two_products = base_queryset.exclude(
            pk=promoted_product.pk if promoted_product else None
        )[:2]

        # Fetch the remaining products excluding the promoted one and first two
        remaining_products = base_queryset.exclude(
            pk__in=list(first_two_products.values_list("pk", flat=True))
            + ([promoted_product.pk] if promoted_product else [])
        )

        # Combine the final queryset ensuring no duplicates
        combined_products = list(first_two_products)

        if promoted_product:
            combined_products.append(promoted_product)

        combined_products.extend(remaining_products)

        # Use OrderedDict to remove duplicates and maintain order
        unique_combined_products = list(OrderedDict.fromkeys(combined_products))

        return unique_combined_products

    def get_queryset(self):
        return get_products()


class ProductDetailView(views.APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = ProductsSerializer

    def get(self, request, pk):
        product = get_products().filter(pk=pk).first()
        if not product:
            raise exceptions.ValidationError({"message": "Товар недоступен"})
        serializer = self.serializer_class(instance=product)
        return response.Response(serializer.data, status.HTTP_200_OK)


class CommentsListView(BaseListCreateAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter

    def get_queryset(self):
        return get_comments(comment=True, reply_to__isnull=False)

    def get_serializer_context(self):
        """
        Pass extra context for both GET and POST.
        """
        context = super().get_serializer_context()
        context["replies"] = True
        context["comment"] = True
        return context


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentDetailSerializer
    permission_classes = [
        permissions.IsAuthenticated,
    ]
    ordering = []

    def get_queryset(self):
        return get_comments(comment=True, user=self.request.user)

    def get_object(self):
        obj = Comment.objects.filter(
            pk=self.kwargs["pk"], user=self.request.user
        ).first()
        if not obj:
            raise exceptions.ValidationError({"message": "Комментарий не найден"})
        return obj


class UserCommentsListView(BaseListAPIView):
    serializer_class = CommentsSerializer

    def get_queryset(self):
        return get_comments(
            comment=True, reply_to__isnull=False, user=self.request.user
        )


class FeedbacksListView(BaseListCreateAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter

    def get_queryset(self):
        return get_comments(reply_to__isnull=True)


class UserFeedbacksListView(BaseListAPIView):
    serializer_class = CommentsSerializer

    def get_queryset(self):
        return get_comments(reply_to__isnull=True, user=self.request.user)


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
        return (
            Favorite.objects.filter(user=self.request.user, product__in=get_products())
            .select_related("product")
            .prefetch_related("user")
            .order_by("-id")
        )


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
