from django.db.models import DateTimeField, Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from scraper.models import Comment, CommentStatuses, Product


def get_filtered_products():
    return (
        Product.objects.annotate(
            has_valid_comments=Exists(
                Comment.objects.filter(
                    product=OuterRef("pk"),
                    content__isnull=False,  # Ensure content is not null
                    content__gt="",  # Ensure content is not empty
                ).filter(
                    Q(files__isnull=False)  # Check for related CommentFiles
                    | Q(
                        file__isnull=False, file__gt=""
                    )  # Check if the Comment has a valid file
                )
            )
        )
        .filter(has_valid_comments=True)
        .distinct()
    )


def get_filtered_comments(queryset=None):
    if queryset is None:
        queryset = Comment.objects.all()
    queryset = queryset.filter(
        status=CommentStatuses.ACCEPTED,
        content__isnull=False,
        content__gt="",
    ).filter(
        Q(files__isnull=False)  # Check for related CommentFiles
        | Q(file__isnull=False, file__gt="")  # Check if the Comment has a valid file
    )
    queryset = queryset.annotate(
        ordering_date=Coalesce(
            "source_date", "created_at", output_field=DateTimeField()
        )
    ).order_by("-ordering_date")
    return queryset
