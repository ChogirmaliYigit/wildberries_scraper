from datetime import timedelta

import django_filters
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from scraper.models import Category, Product, ProductVariant


class ProductFilter(django_filters.FilterSet):
    category_id = django_filters.NumberFilter(method="filter_by_category")
    source_id = django_filters.NumberFilter(field_name="source_id")

    def filter_by_category(self, queryset, name, value):
        category = Category.objects.filter(pk=value).first()
        if category:
            if category.shard == "popular":
                return self.get_popular_products(queryset)
            elif category.shard == "new":
                return self.get_new_products(queryset)
        category_ids = [value]
        category_ids.extend(
            list(Category.objects.filter(parent_id=value).values_list("id", flat=True))
        )
        return queryset.filter(category_id__in=category_ids)

    def get_popular_products(self, queryset):
        return (
            queryset.annotate(likes_count=Count("product_likes", distinct=True))
            .filter(likes_count__gt=1)
            .order_by("-likes_count")
        )

    def get_new_products(self, queryset):
        limit_date = timezone.now() - timedelta(days=settings.NEW_PRODUCTS_DAYS)
        return queryset.filter(created_at__gte=limit_date).order_by("-created_at")

    class Meta:
        model = Product
        fields = [
            "category_id",
            "source_id",
        ]


def filter_by_product_or_variant(queryset, value):
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

    return filtered_comments


def filter_by_feedback(queryset, value):
    if value:
        return queryset.filter(reply_to_id=value)
    return queryset
