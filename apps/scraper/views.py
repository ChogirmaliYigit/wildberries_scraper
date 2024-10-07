from core.views import BaseListAPIView
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
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from scraper.models import Category, Comment, Favorite, Like, Product
from scraper.serializers import (
    CategoriesSerializer,
    CommentDetailSerializer,
    CommentsSerializer,
    FavoritesSerializer,
    ProductsSerializer,
)
from scraper.utils.queryset import (
    filter_comments,
    filter_products,
    get_all_products,
    get_comments_response,
    get_paginated_response,
    get_products_response,
    paginate_queryset,
)


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


def products_list(request):
    total, _next, previous, current, page_obj = paginate_queryset(
        request, filter_products(request)
    )
    return get_paginated_response(
        get_products_response(request, page_obj), total, _next, previous, current
    )


class ProductDetailView(views.APIView):
    serializer_class = ProductsSerializer
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request, pk):
        product = get_all_products().filter(pk=pk).first()
        if not product:
            raise exceptions.ValidationError({"message": "Товар недоступен"})
        serializer = self.serializer_class(product, context={"request": request})
        return response.Response(serializer.data, status.HTTP_200_OK)


class CommentsListView(GenericAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests: List comments.
        """
        return comments_list(
            request, replies=True, for_comment=True, reply_to__isnull=False
        )

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: Create a new comment.
        """
        serializer = CommentsSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({}, status=status.HTTP_201_CREATED)

    def get_serializer_context(self):
        """
        Pass extra context for both GET and POST.
        """
        context = super().get_serializer_context()
        context["replies"] = True
        return context

    def perform_create(self, serializer):
        """
        Save the newly created comment. You can also add custom logic here.
        """
        serializer.save(user=self.request.user)


def comments_list(
    request, replies=False, user_feedback=False, for_comment=False, **filters
):
    total, _next, previous, current, page_obj = paginate_queryset(
        request, filter_comments(request, **filters)
    )
    return get_paginated_response(
        get_comments_response(
            request,
            page_obj.object_list,
            replies=replies,
            user_feedback=user_feedback,
            for_comment=for_comment,
        ),
        total,
        _next,
        previous,
        current,
    )


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


class UserCommentsListView(GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        return comments_list(
            request,
            replies=True,
            user_feedback=True,
            reply_to__isnull=False,
            user=self.request.user,
        )


class FeedbacksListView(GenericAPIView):
    permission_classes = (IsAuthenticatedOrReadOnly,)

    def get(self, request, *args, **kwargs):
        return comments_list(request, reply_to__isnull=True)

    def post(self, request, *args, **kwargs):
        serializer = CommentsSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status.HTTP_201_CREATED)


class UserFeedbacksListView(GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return comments_list(
            request, user_feedback=True, reply_to__isnull=True, user=self.request.user
        )


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
        filtered_products = get_all_products()

        # Annotate the img_link from the filtered_products into the Favorite queryset
        products_with_img_link = filtered_products.filter(
            id=OuterRef("product_id")
        ).values("img_link")[:1]

        return (
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
