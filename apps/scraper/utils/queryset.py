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

    # Fetch the promoted comment
    promoted_comment = base_queryset.filter(promo=True).order_by("?").first()

    if promoted_comment:
        # Exclude the promoted comment from the main queryset
        main_queryset = base_queryset.exclude(pk=promoted_comment.id)

        # Annotate main queryset with priority to ensure promoted comment can be inserted
        main_queryset = main_queryset.annotate(
            priority=Case(
                When(pk=promoted_comment.id, then=1),
                default=0,
                output_field=IntegerField(),
            )
        ).order_by("-priority", "-ordering_date")

        # Convert to list to insert the promoted comment manually
        main_comments_list = list(main_queryset)

        # Insert the promoted comment at the third position if there are at least 2 comments
        if len(main_comments_list) >= 2:
            main_comments_list.insert(2, promoted_comment)
        else:
            main_comments_list.append(promoted_comment)

        # Convert list back to a QuerySet-like structure
        from django.db.models.query import QuerySet

        queryset_with_promoted_comment = QuerySet(
            model=base_queryset.model, query=base_queryset.query
        )
        queryset_with_promoted_comment = queryset_with_promoted_comment.none()
        queryset_with_promoted_comment = queryset_with_promoted_comment | QuerySet(
            model=base_queryset.model, query=base_queryset.query
        )
        queryset_with_promoted_comment = queryset_with_promoted_comment | QuerySet(
            model=base_queryset.model, query=base_queryset.query
        )

        return queryset_with_promoted_comment.distinct()
    else:
        # Return the queryset with proper ordering if no promoted comment exists
        return base_queryset.order_by("-ordering_date").distinct()
