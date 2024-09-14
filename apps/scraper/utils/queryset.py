import random

from django.conf import settings
from django.db.models import Case, DateTimeField, Exists, OuterRef, Q, When
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
        .order_by("?")
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


def base_comment_filter(queryset):
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
    return base_queryset


def get_filtered_comments(queryset=None, promo=False):
    if queryset is None:
        queryset = Comment.objects.filter(status=CommentStatuses.ACCEPTED)

    base_queryset = base_comment_filter(queryset)

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


def get_files(comment):
    files = []

    # Helper function to process files
    def process_file(_link, file_type):
        return {
            "link": _link,
            "type": file_type,
            "stream": _link.endswith(".m3u8"),
        }

    # Process the single `comment.file`
    if comment.file:
        file_link = f"{settings.BACKEND_DOMAIN}{settings.MEDIA_URL}{comment.file}"
        file = process_file(file_link, comment.file_type)
        if file not in files:
            files.append(file)

    # Process files from `comment.files.all()`
    for file in comment.files.all():
        if file.file_link:  # Ensure the file has a link
            processed_file = process_file(file.file_link, file.file_type)
            if processed_file not in files:
                files.append(processed_file)

    return files


# Collect all replies in a single list
def get_all_replies(comment, _replies=True):
    replies = (
        comment.replies.prefetch_related("user", "reply_to", "product")
        .distinct("user", "product", "content")
        .annotate(
            annotated_source_date=Case(
                When(source_date__isnull=False, then="source_date"),
                default="created_at",
                output_field=DateTimeField(),
            )
        )
        .order_by("user", "product", "content", "-annotated_source_date")
    )

    all_replies = []
    for reply in replies:
        all_replies.append(reply)
        if _replies:
            all_replies.extend(get_all_replies(reply))  # Recursively collect replies

    return all_replies
