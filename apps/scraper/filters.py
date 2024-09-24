from datetime import timedelta

import django_filters
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from scraper.models import Category, Comment, CommentStatuses, Product


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
    rating = django_filters.NumberFilter(field_name="rating")
    status = django_filters.ChoiceFilter(
        field_name="status", choices=CommentStatuses.choices
    )
    user_id = django_filters.NumberFilter(field_name="user_id")
    feedback_id = django_filters.NumberFilter(method="filter_by_feedback")

    def filter_by_feedback(self, queryset, name, value):
        if value:
            queryset = queryset.filter(reply_to_id=value)
        return queryset

    class Meta:
        model = Comment
        fields = [
            "product_id",
            "source_id",
            "rating",
            "status",
            "user_id",
            "feedback_id",
        ]


def filter_by_category(queryset, value):
    category = Category.objects.filter(pk=value).first()
    if category:
        if category.shard == "popular":
            return get_popular_products(queryset)
        elif category.shard == "new":
            return get_new_products(queryset)
    category_ids = [value]
    category_ids.extend(
        list(Category.objects.filter(parent_id=value).values_list("id", flat=True))
    )
    queryset = queryset.filter(category_id__in=category_ids)
    return queryset


def get_popular_products(queryset):
    return (
        queryset.annotate(likes_count=Count("product_likes", distinct=True))
        .filter(likes_count__gte=2)
        .order_by("-likes_count")
    )


def get_new_products(queryset):
    limit_date = timezone.now() - timedelta(days=settings.NEW_PRODUCTS_DAYS)
    queryset = queryset.filter(created_at__gte=limit_date).order_by("-created_at")
    return queryset
