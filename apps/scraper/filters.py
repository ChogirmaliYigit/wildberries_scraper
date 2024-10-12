from datetime import timedelta

import django_filters
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from scraper.models import Category, Comment, Product


class ProductFilter(django_filters.FilterSet):
    category_id = django_filters.NumberFilter(method="filter_by_category_id")
    source_id = django_filters.NumberFilter(field_name="source_id")

    def filter_by_category_id(self, queryset, name, value):
        return filter_by_category(queryset, value)

    class Meta:
        model = Product
        fields = [
            "category_id",
            "source_id",
        ]


class CommentsFilter(django_filters.FilterSet):
    product_id = django_filters.NumberFilter(field_name="product_id")
    source_id = django_filters.NumberFilter(field_name="source_id")
    feedback_id = django_filters.NumberFilter(field_name="reply_to_id")

    class Meta:
        model = Comment
        fields = [
            "product_id",
            "source_id",
            "feedback_id",
        ]


def filter_by_category(queryset, value):
    # Fetch category and its child categories in a single query
    category_qs = Category.objects.filter(Q(pk=value) | Q(parent_id=value)).only(
        "id", "shard"
    )

    # Check if the primary category exists
    if not category_qs.exists():
        return Category.objects.none()

    # Separate primary category from child categories
    primary_category = category_qs.filter(pk=value).first()

    # Apply shard-based filtering if primary category has a shard
    if primary_category:
        if primary_category.shard == "popular":
            return get_popular_products(queryset)
        elif primary_category.shard == "new":
            return get_new_products(queryset)

    # Get all category IDs (primary and child categories)
    category_ids = list(category_qs.values_list("id", flat=True))

    # Filter products by these category IDs
    return queryset.filter(category_id__in=category_ids)


def get_popular_products(queryset):
    # Using a threshold for "likes_count" to filter popular products and applying an index on this field will help
    return (
        queryset.annotate(likes_count=Count("product_likes"))
        .filter(likes_count__gte=3)
        .order_by("-likes_count")
    )


def get_new_products(queryset):
    # Use the indexed "created_at" field to filter for new products
    limit_date = timezone.now() - timedelta(days=settings.NEW_PRODUCTS_DAYS)
    return queryset.filter(created_at__gte=limit_date).order_by("-created_at")
