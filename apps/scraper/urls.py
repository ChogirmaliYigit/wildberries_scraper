from django.urls import path  # noqa
from scraper.views import CategoriesListView, CommentsListView, ProductsListView  # noqa

urlpatterns = [
    # path("categories", CategoriesListView.as_view(), name="categories-list"),
    # path("products", ProductsListView.as_view(), name="products-list"),
    # path("comments", CommentsListView.as_view(), name="comments-list"),
]
