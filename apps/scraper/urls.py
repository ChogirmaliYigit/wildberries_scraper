from django.urls import path
from scraper.views import (
    CategoriesListView,
    CommentsListView,
    FavoritesListView,
    FeedbacksListView,
    LikeView,
    ProductsListView,
    UserCommentsListView,
    UserFeedbacksListView,
)

urlpatterns = [
    path("categories", CategoriesListView.as_view(), name="categories-list"),
    path("products", ProductsListView.as_view(), name="products-list"),
    path("comments", CommentsListView.as_view(), name="comments-list"),
    path("user-comments", UserCommentsListView.as_view(), name="user-comments-list"),
    path("feedbacks", FeedbacksListView.as_view(), name="feedbacks-list"),
    path("user-feedbacks", UserFeedbacksListView.as_view(), name="user-feedbacks-list"),
    path("favorites", FavoritesListView.as_view(), name="favorites-list"),
    path("like/<int:product_id>", LikeView.as_view(), name="like-a-product"),
]
