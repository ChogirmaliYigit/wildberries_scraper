from django.db.models import DateTimeField, Exists, OuterRef, Q
from django.db.models.functions import Coalesce, Random
from scraper.models import Comment, CommentStatuses, Product


def get_filtered_products():
    # Subquery to check for valid comments related to a product
    valid_comments_subquery = Comment.objects.filter(
        product=OuterRef("pk"),
        content__isnull=False,  # Ensure content is not null
        content__gt="",  # Ensure content is not empty
    ).filter(
        Q(files__isnull=False)  # Check for related CommentFiles
        | Q(file__isnull=False, file__gt="")  # Check if the Comment has a valid file
    )

    # Main query to filter products
    filtered_products = (
        Product.objects.annotate(has_valid_comments=Exists(valid_comments_subquery))
        .filter(has_valid_comments=True)
        .distinct("title")
    )  # Ensure products have unique titles

    return filtered_products


def get_filtered_comments(queryset=None, promo=False):
    if queryset is None:
        queryset = Comment.objects.filter(status=CommentStatuses.ACCEPTED)

    # Filter the main comments
    base_queryset = queryset.filter(
        status=CommentStatuses.ACCEPTED, content__isnull=False, content__gt=""
    ).filter(Q(files__isnull=False) | Q(file__isnull=False, file__gt=""))

    # Annotate with ordering_date
    base_queryset = base_queryset.annotate(
        ordering_date=Coalesce(
            "source_date", "created_at", output_field=DateTimeField()
        )
    ).order_by("-ordering_date")

    # Randomly select one promoted comment
    selected_promo_comment = base_queryset.filter(promo=True).order_by(Random()).first()

    if selected_promo_comment and promo:
        # Get all comments excluding the selected promoted one
        other_comments = Comment.objects.exclude(
            id=selected_promo_comment.id
        ).distinct()

        all_comments = list(other_comments)  # Convert QuerySet to list
        all_comments.insert(2, selected_promo_comment)  # Insert at index 2

        return all_comments
    return queryset
