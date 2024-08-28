from django.db.models import Case, Count, DateTimeField, F, Q, When
from scraper.models import Comment, CommentStatuses, Product


def get_filtered_products():
    products_with_image_count = Product.objects.annotate(
        variants_with_images=Count(
            "variants__images", distinct=True, filter=Q(variants__images__isnull=False)
        )
    )

    products_with_total_variants = products_with_image_count.annotate(
        total_variants=Count("variants", distinct=True)
    )

    products_with_all_images = products_with_total_variants.filter(
        variants_with_images=F("total_variants")
    )

    filtered_products = products_with_all_images.filter(
        product_comments__isnull=False
    ).distinct()
    return filtered_products


def get_filtered_comments(queryset=None):
    if not queryset:
        queryset = Comment.objects.all()
    annotated_query = queryset.annotate(
        annotated_source_date=Case(
            When(source_date__isnull=False, then="source_date"),
            default="created_at",
            output_field=DateTimeField(),
        )
    )

    # Step 2: Apply select_related for single-valued relationships
    optimized_query = annotated_query.select_related("product", "user", "reply_to")

    # Step 3: Filter by accepted status and non-null reply_to
    optimized_query = optimized_query.filter(
        status=CommentStatuses.ACCEPTED, content__isnull=False
    )

    # Step 4: Use distinct after filtering and annotating
    optimized_query = optimized_query.distinct("user", "product", "content")

    # Step 5: Order by the annotated source date and other fields
    optimized_query = optimized_query.order_by(
        "user", "product", "content", "-annotated_source_date"
    )
    return optimized_query
