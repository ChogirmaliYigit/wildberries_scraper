from rest_framework import generics
from scraper.filters import CategoryFilter, CommentsFilter, ProductFilter
from scraper.models import Category, Comment, CommentStatuses, Favorite, Product
from scraper.serializers import (
    CategoriesSerializer,
    CommentsSerializer,
    FavoritesSerializer,
    ProductsSerializer,
)


class CategoriesListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategoriesSerializer
    filterset_class = CategoryFilter
    search_fields = [
        "title",
    ]


class ProductsListView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductsSerializer
    filterset_class = ProductFilter
    search_fields = ["title", "variants__color", "variants__price"]


class CommentsListView(generics.ListAPIView):
    queryset = Comment.objects.filter(status=CommentStatuses.ACCEPTED)
    serializer_class = CommentsSerializer
    filterset_class = CommentsFilter
    search_fields = [
        "content",
    ]


class FavoritesListView(generics.ListAPIView):
    serializer_class = FavoritesSerializer
    search_fields = [
        "product__title",
    ]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)
