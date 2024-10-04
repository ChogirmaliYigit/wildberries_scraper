from django.urls import path
from scraper.views import (
    CategoriesListView,
    CommentDetailView,
    CommentsListView,
    FavoritesListView,
    FavoriteView,
    FeedbacksListView,
    LikeView,
    ProductDetailView,
    UserCommentsListView,
    UserFeedbacksListView,
    products_list,
)

urlpatterns = [
    path("categories", CategoriesListView.as_view(), name="categories-list"),
    path("products", products_list, name="products-list"),
    path("product/<int:pk>", ProductDetailView.as_view(), name="product-detail"),
    path("comments", CommentsListView.as_view(), name="comments-list"),
    path("user-comments", UserCommentsListView.as_view(), name="user-comments-list"),
    path(
        "user-comments/<int:pk>",
        CommentDetailView.as_view(),
        name="user-comment-detail",
    ),
    path("feedbacks", FeedbacksListView.as_view(), name="feedbacks-list"),
    path("user-feedbacks", UserFeedbacksListView.as_view(), name="user-feedbacks-list"),
    path("favorites", FavoritesListView.as_view(), name="favorites-list"),
    path("like/<int:product_id>", LikeView.as_view(), name="like-a-product"),
    path(
        "favorite/<int:product_id>", FavoriteView.as_view(), name="favorite-a-product"
    ),
]
