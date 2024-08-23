import django_filters
from scraper.models import Category, Comment, CommentStatuses, Product, ProductVariant


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
    product_id = django_filters.NumberFilter(method="filter_by_product_or_variant")
    source_id = django_filters.NumberFilter(field_name="source_id")
    rating = django_filters.NumberFilter(field_name="rating")
    status = django_filters.ChoiceFilter(
        field_name="status", choices=CommentStatuses.choices
    )
    user_id = django_filters.NumberFilter(field_name="user_id")

    def filter_by_product_or_variant(self, queryset, name, value):
        # First, try to filter comments by product_id
        filtered_comments = queryset.filter(product_id=value)

        # If no comments found, filter by ProductVariants related to the product
        if not filtered_comments.exists():
            product_variant = (
                ProductVariant.objects.filter(product_id=value)
                .select_related("product")
                .first()
            )
            if product_variant:
                filtered_comments = queryset.filter(product=product_variant.product)

        return filtered_comments

    class Meta:
        model = Comment
        fields = [
            "product_id",
            "source_id",
            "rating",
            "status",
            "user_id",
        ]
