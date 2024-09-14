import random

from django.db.models import DateTimeField, Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from scraper.models import Comment, CommentStatuses, RequestedComment


def get_filtered_products(queryset, promo=False):
    # Subquery to check for valid comments related to a product
    valid_comments_subquery = Comment.objects.filter(
        product=OuterRef("pk"),
        content__isnull=False,  # Ensure content is not null
        content__gt="",  # Ensure content is not empty
    ).filter(
        Q(files__isnull=False)  # Check for related CommentFiles
        | Q(file__isnull=False, file__gt="")  # Check if the Comment has a valid file
    )

    # Subquery to check for promoted comments related to a product
    promoted_comments_subquery = Comment.objects.filter(
        product=OuterRef("pk"), promo=True
    )

    # Main query to filter products
    products = (
        queryset.annotate(
            has_valid_comments=Exists(valid_comments_subquery),
            is_promoted=Exists(promoted_comments_subquery),
        )
        .filter(has_valid_comments=True)
        .distinct()
    )

    if not promo:
        return products

    # Separate promoted and non-promoted products
    promoted_products = list(products.filter(is_promoted=True))
    non_promoted_products = list(products.filter(is_promoted=False))

    # Randomly select one promoted product if available
    selected_promo_product = None
    if promoted_products:
        selected_promo_product = random.choice(promoted_products)

    # Insert the selected promoted product at index 2 if it exists
    if selected_promo_product:
        non_promoted_products.insert(2, selected_promo_product)

    return non_promoted_products


def get_filtered_comments(queryset=None, promo=False):
    if queryset is None:
        queryset = Comment.objects.filter(status=CommentStatuses.ACCEPTED)

    # Filter the main comments
    base_queryset = queryset.filter(
        status=CommentStatuses.ACCEPTED, content__isnull=False, content__gt=""
    ).filter(Q(files__isnull=False) | Q(file__isnull=False, file__gt=""))

    # Exclude comments where the id exists in the RequestedComment model
    requested_comment_ids = RequestedComment.objects.values_list("id", flat=True)
    base_queryset = base_queryset.exclude(id__in=requested_comment_ids)

    # Annotate with ordering_date
    base_queryset = (
        base_queryset.annotate(
            ordering_date=Coalesce(
                "source_date", "created_at", output_field=DateTimeField()
            )
        )
        .distinct("content", "ordering_date")
        .order_by("-ordering_date", "content")
    )

    # Randomly select one promoted comment
    selected_promo_comment = None
    promotes = list(base_queryset.filter(promo=True))
    if promotes:
        selected_promo_comment = random.choice(promotes)

    if selected_promo_comment and promo:
        # Get all comments excluding the selected promoted one
        other_comments = Comment.objects.exclude(id=selected_promo_comment.id)

        all_comments = list(other_comments)  # Convert QuerySet to list
        all_comments.insert(2, selected_promo_comment)  # Insert at index 2

        return all_comments

    return base_queryset
