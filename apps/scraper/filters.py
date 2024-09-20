from datetime import timedelta

import django_filters
from django.conf import settings
from django.core.cache import cache
from django.db.models import Case, Count, DateTimeField, When
from django.utils import timezone
from scraper.models import Category, Comment, CommentStatuses, Product, ProductVariant


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
    product_id = django_filters.NumberFilter(method="filter_by_product_or_variant")
    source_id = django_filters.NumberFilter(field_name="source_id")
    rating = django_filters.NumberFilter(field_name="rating")
    status = django_filters.ChoiceFilter(
        field_name="status", choices=CommentStatuses.choices
    )
    user_id = django_filters.NumberFilter(field_name="user_id")
    feedback_id = django_filters.NumberFilter(method="filter_by_feedback")

    def filter_by_product_or_variant(self, queryset, name, value):
        cache_key = f"filtered_comments_by_product_or_variant_{value}"
        cached_comments = cache.get(cache_key)

        if cached_comments is not None:
            # If we have cached results, return them
            return cached_comments

        # First, try to filter comments by product_id
        filtered_comments = queryset.filter(product_id=value)

        # If no comments found, filter by ProductVariants
        if not filtered_comments.exists():
            product_variants = ProductVariant.objects.filter(id=value)
            if product_variants.exists():
                product_ids = product_variants.values_list(
                    "product_id", flat=True
                ).distinct()
                filtered_comments = queryset.filter(product_id__in=product_ids)

        # Annotate and order the results
        filtered_comments = filtered_comments.annotate(
            annotated_source_date=Case(
                When(source_date__isnull=False, then="source_date"),
                default="created_at",
                output_field=DateTimeField(),
            )
        ).order_by("user", "product", "content", "-annotated_source_date")

        # Cache the result
        cache.set(cache_key, filtered_comments, timeout=300)
        return filtered_comments

    def filter_by_feedback(self, queryset, name, value):
        if value:
            cache_key = f"feedback_replies_{value}"
            cached_queryset = cache.get(cache_key)
            if cached_queryset:
                return cached_queryset
            queryset = queryset.filter(reply_to_id=value)
            cache.set(cache_key, queryset, timeout=600)
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
    queryset_key = f"category_products_{value}"
    cached_queryset = cache.get(queryset_key)
    if cached_queryset:
        return cached_queryset

    category_key = f"category_{value}"
    category_ids_key = f"category_ids_{value}"
    timeout = 60 * 60 * 24 * 3

    category = cache.get(category_key)
    if not category:
        category = Category.objects.filter(pk=value).first()
        cache.set(category_key, category, timeout=timeout)
    if category:
        if category.shard == "popular":
            return get_popular_products(queryset)
        elif category.shard == "new":
            return get_new_products(queryset)
    category_ids = cache.get(category_ids_key)
    if not category_ids:
        category_ids = [value]
        category_ids.extend(
            list(Category.objects.filter(parent_id=value).values_list("id", flat=True))
        )
        cache.set(category_ids_key, category_ids, timeout=timeout)
    queryset = queryset.filter(category_id__in=category_ids)
    cache.set(queryset_key, queryset, timeout=600)
    return queryset


def get_popular_products(queryset):
    return (
        queryset.annotate(likes_count=Count("product_likes", distinct=True))
        .filter(likes_count__gte=2)
        .order_by("-likes_count")
    )


def get_new_products(queryset):
    limit_date = timezone.now() - timedelta(days=settings.NEW_PRODUCTS_DAYS)
    cache_key = "new_products"
    cached_new_products = cache.get(cache_key)
    if cached_new_products:
        return cached_new_products
    queryset = queryset.filter(created_at__gte=limit_date).order_by("-created_at")
    cache.set(cache_key, queryset, timeout=60 * 60 * 24)
    return queryset
