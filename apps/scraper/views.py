from core.pagination import CustomPageNumberPagination
from core.views import BaseListAPIView
from django.db.models import Case, IntegerField, Q, Value, When
from drf_yasg import utils
from rest_framework import exceptions, generics, permissions, response, status, views
from rest_framework.permissions import AllowAny
from scraper.filters import (
    ProductFilter,
    filter_by_category,
    filter_by_feedback,
    filter_by_product_or_variant,
)
from scraper.models import Category, Comment, Favorite, Like, Product
from scraper.serializers import (
    CategoriesSerializer,
    CommentDetailSerializer,
    CommentsSerializer,
    FavoritesSerializer,
    ProductsSerializer,
)
from scraper.utils.queryset import (
    get_all_replies,
    get_filtered_comments,
    get_filtered_products,
)
from users.utils import CustomTokenAuthentication


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


class ProductsListView(views.APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = ProductsSerializer
    filterset_class = ProductFilter
    search_fields = ["title", "variants__color", "variants__price"]
    pagination_class = CustomPageNumberPagination

    def get(self, request):
        queryset = Product.objects.all()
        # Apply search filters
        search_query = request.query_params.get("search", "").strip()
        if search_query:
            filters = Q()
            for field in self.search_fields:
                filters |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(filters)

        category_id = str(request.query_params.get("category_id", ""))
        if category_id.isdigit():
            queryset = filter_by_category(queryset, category_id)
        source_id = str(request.query_params.get("source_id", ""))
        if source_id.isdigit():
            queryset = queryset.filter(source_id=source_id)
        # Paginate the queryset
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(
            get_filtered_products(queryset, True), request
        )
        serializer = self.serializer_class(
            result_page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)


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


class CommentsListView(views.APIView):
    authentication_classes = (CustomTokenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = CommentsSerializer
    pagination_class = CustomPageNumberPagination

    def get(self, request):
        # Paginate the queryset
        paginator = self.pagination_class()
        queryset = Comment.objects.filter(reply_to__isnull=False)
        if not queryset.exists():
            return response.Response({})
        product_id = str(request.query_params.get("product_id", ""))
        if product_id.isdigit():
            queryset = filter_by_product_or_variant(queryset, product_id)
        feedback_id = str(request.query_params.get("feedback_id", ""))
        if feedback_id.isdigit():
            comment = Comment.objects.filter(id=feedback_id).first()
            if not comment:
                return paginator.get_paginated_response({})
            queryset = get_all_replies(comment)
        else:
            queryset = get_filtered_comments(queryset, True)
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(
            result_page, many=True, context={"request": request, "comment": True}
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not request.user.is_authenticated:
            raise exceptions.ValidationError({"message": "Не аутентифицирован"})
        serializer = self.serializer_class(
            data=request.data, context={"request": request, "comment": True}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(serializer.data, status.HTTP_201_CREATED)


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentDetailSerializer
    permission_classes = [
        permissions.IsAuthenticated,
    ]
    ordering = []

    def get_queryset(self):
        return Comment.objects.filter(user=self.request.user)

    def get_object(self):
        queryset = self.get_queryset()
        if queryset:
            queryset = get_filtered_comments(queryset, False)
            obj = queryset.filter(pk=self.kwargs["pk"]).first()
            if not obj:
                raise exceptions.ValidationError({"message": "Комментарий не найден"})
            return obj
        raise exceptions.ValidationError({"message": "Комментарий не найден"})


class UserCommentsListView(views.APIView):
    serializer_class = CommentsSerializer
    pagination_class = CustomPageNumberPagination

    def get(self, request):
        queryset = Comment.objects.filter(reply_to__isnull=False, user=request.user)
        if not queryset.exists():
            return response.Response({})
        product_id = str(request.query_params.get("product_id", ""))
        if product_id.isdigit():
            queryset = filter_by_product_or_variant(queryset, product_id)
        feedback_id = str(request.query_params.get("feedback_id", ""))
        if feedback_id.isdigit():
            queryset = filter_by_feedback(queryset, feedback_id)
        queryset = get_filtered_comments(queryset, True)
        # Paginate the queryset
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(
            result_page, many=True, context={"request": request, "replies": True}
        )
        return paginator.get_paginated_response(serializer.data)


class FeedbacksListView(views.APIView):
    authentication_classes = (CustomTokenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = CommentsSerializer
    pagination_class = CustomPageNumberPagination

    def get(self, request):
        queryset = Comment.objects.filter(reply_to__isnull=True)
        if not queryset.exists():
            return response.Response({})
        product_id = str(request.query_params.get("product_id", ""))
        if product_id.isdigit():
            queryset = filter_by_product_or_variant(queryset, product_id)
        queryset = get_filtered_comments(queryset, True)
        # Paginate the queryset
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(
            result_page, many=True, context={"request": request, "replies": True}
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not request.user.is_authenticated:
            raise exceptions.ValidationError({"message": "Не аутентифицирован"})
        serializer = self.serializer_class(
            data=request.data, context={"request": request, "comment": False}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(serializer.data, status.HTTP_201_CREATED)


class UserFeedbacksListView(views.APIView):
    serializer_class = CommentsSerializer
    pagination_class = CustomPageNumberPagination

    def get(self, request):
        queryset = Comment.objects.filter(reply_to__isnull=True, user=request.user)
        if not queryset.exists():
            return response.Response({})
        product_id = str(request.query_params.get("product_id", ""))
        if product_id.isdigit():
            queryset = filter_by_product_or_variant(queryset, product_id)
        queryset = get_filtered_comments(queryset, True)
        # Paginate the queryset
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(
            result_page, many=True, context={"request": request, "replies": True}
        )
        return paginator.get_paginated_response(serializer.data)


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
