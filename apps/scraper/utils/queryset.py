from django.db.models import (
    Case,
    DateTimeField,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    When,
)
from django.db.models.functions import Coalesce
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


def get_filtered_comments(queryset=None):
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
    )

    # Prioritize promoted comments
    queryset_with_priority = base_queryset.annotate(
        priority=Case(When(promo=True, then=1), default=0, output_field=IntegerField())
    ).order_by("-priority", "-ordering_date")

    # Fetch the promoted comment
    promoted_comment = base_queryset.filter(promo=True).order_by("?").first()

    if promoted_comment:
        # Add the promoted comment manually to the result set while ordering
        # This approach will place it at the third position in the final result
        promoted_id = promoted_comment.id
        queryset_with_priority = queryset_with_priority.filter(~Q(id=promoted_id))

        # Annotate with priority for ordering
        queryset_with_priority = queryset_with_priority.annotate(
            position=Case(
                When(
                    id=promoted_id, then=2
                ),  # Promoted comment should be at position 2 (third position if 0-indexed)
                default=3,  # Default position for other comments
                output_field=IntegerField(),
            )
        ).order_by("position", "-ordering_date")

        return queryset_with_priority
    else:
        return queryset_with_priority
