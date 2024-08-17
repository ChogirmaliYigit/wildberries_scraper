from core.views import BaseListAPIView, BaseListCreateAPIView
from rest_framework import generics
from scraper.filters import CategoryFilter, CommentsFilter, ProductFilter
from scraper.models import Category, Comment, CommentStatuses, Favorite, Product
from scraper.serializers import (
    CategoriesSerializer,
    CommentsSerializer,
    FavoritesSerializer,
    ProductsSerializer,
)


class CategoriesListView(BaseListAPIView):
    queryset = Category.objects.prefetch_related("parent").all()
    serializer_class = CategoriesSerializer
    filterset_class = CategoryFilter
    search_fields = [
        "title",
    ]


class ProductsListView(BaseListAPIView):
    queryset = Product.objects.prefetch_related("category").all()
    serializer_class = ProductsSerializer
    filterset_class = ProductFilter
    search_fields = ["title", "variants__color", "variants__price"]


class CommentsListView(BaseListCreateAPIView):
    queryset = Comment.objects.prefetch_related("product", "user", "reply_to").filter(
        status=CommentStatuses.ACCEPTED, reply_to__isnull=False
    )
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class UserCommentsListView(generics.ListAPIView):
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]

    def get_queryset(self):
        return Comment.objects.prefetch_related("product", "user", "reply_to").filter(
            status=CommentStatuses.ACCEPTED,
            reply_to__isnull=False,
            user=self.request.user,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class FeedbacksListView(BaseListAPIView):
    queryset = Comment.objects.prefetch_related("product", "user", "reply_to").filter(
        reply_to__isnull=True, status=CommentStatuses.ACCEPTED
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
        return Comment.objects.prefetch_related("product", "user", "reply_to").filter(
            reply_to__isnull=True,
            status=CommentStatuses.ACCEPTED,
            user=self.request.user,
        )


class FavoritesListView(BaseListCreateAPIView):
    serializer_class = FavoritesSerializer
    search_fields = [
        "product__title",
    ]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        return Favorite.objects.prefetch_related("product", "user").filter(
            user=self.request.user
        )
