import django_filters
from scraper.models import Category, Comment, CommentStatuses, Product


class CategoryFilter(django_filters.FilterSet):
    parent_id = django_filters.NumberFilter(field_name="parent_id")
    source_id = django_filters.NumberFilter(field_name="source_id")

    class Meta:
        model = Category
        fields = [
            "parent_id",
            "source_id",
        ]


class ProductFilter(django_filters.FilterSet):
    category_id = django_filters.NumberFilter(field_name="category_id")
    source_id = django_filters.NumberFilter(field_name="source_id")

    class Meta:
        model = Product
        fields = [
            "category_id",
            "source_id",
        ]


class CommentsFilter(django_filters.FilterSet):
    product_id = django_filters.NumberFilter(field_name="product_id")
    source_id = django_filters.NumberFilter(field_name="source_id")
    rating = django_filters.NumberFilter(field_name="rating")
    status = django_filters.ChoiceFilter(
        field_name="status", choices=CommentStatuses.choices
    )
    user_id = django_filters.NumberFilter(field_name="user_id")

    class Meta:
        model = Comment
        fields = [
            "product_id",
            "source_id",
            "rating",
            "status",
            "user_id",
        ]
