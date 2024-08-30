from django.db.models import Case, DateTimeField, Exists, OuterRef, When
from scraper.models import Comment, CommentStatuses, Product, ProductVariantImage


def get_filtered_products():
    return Product.objects.annotate(
        has_comments=Exists(Comment.objects.filter(product=OuterRef("pk"))),
        has_images=Exists(
            ProductVariantImage.objects.filter(variant__product=OuterRef("pk"))
        ),
    ).filter(has_comments=True, has_images=True)


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
