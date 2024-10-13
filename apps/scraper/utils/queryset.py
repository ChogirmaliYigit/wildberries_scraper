from django.conf import settings
from django.db.models import Count, DateTimeField, F, Q
from django.db.models.functions import Coalesce
from scraper.models import (
    Comment,
    CommentStatuses,
    Favorite,
    FileTypeChoices,
    Like,
    Product,
    RequestedComment,
)


def get_products():
    return (
        Product.objects.annotate(
            likes_count=Count("product_likes", distinct=True),
            promoted=F("product_comments__promo"),
            valid_comments_count=Count(
                "product_comments",
                filter=Q(
                    Q(
                        product_comments__file__isnull=False,
                        product_comments__file_type=FileTypeChoices.IMAGE,
                    )
                    | Q(
                        product_comments__files__isnull=False,
                        product_comments__files__file_type=FileTypeChoices.IMAGE,
                    ),
                    product_comments__status=CommentStatuses.ACCEPTED,
                    product_comments__content__isnull=False,
                ),
            ),
        )
        .filter(
            image_link__isnull=False,
            valid_comments_count__gt=0,  # Only products with valid comments
        )
        .prefetch_related("product_likes")
        .order_by("?")
    )


def get_comments(comment=False, **filters):
    requested_comment_ids = RequestedComment.objects.values_list("id", flat=True)

    queryset = (
        Comment.objects.filter(
            status=CommentStatuses.ACCEPTED,
            content__isnull=False,
            **filters,
        )
        .exclude(id__in=requested_comment_ids)
        .annotate(
            ordering_date=Coalesce(
                "source_date", "created_at", output_field=DateTimeField()
            )
        )
        .select_related("product", "user", "reply_to")
        .prefetch_related("files", "replies")
    )
    if not comment:
        queryset = queryset.filter(Q(file__isnull=False) | Q(files__isnull=False))
    return queryset


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
        file_link = f"{settings.BACKEND_DOMAIN.rstrip('/')}{comment.file.url}"
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


def get_all_replies(comment, _replies=True):
    # Initialize a list to store all replies
    all_replies = []

    # Collect replies iteratively
    replies_to_process = [comment]
    while replies_to_process:
        current_comment = replies_to_process.pop()

        # Fetch replies for the current comment
        replies = current_comment.replies.filter(
            requestedcomment__isnull=True
        ).prefetch_related("user", "reply_to", "product")

        # Add replies to the list
        all_replies.extend(replies)

        if _replies:
            # Add replies to the processing list for further exploration
            replies_to_process.extend(replies)

    return all_replies


def get_user_likes_and_favorites(user, product):
    liked = Like.objects.filter(user=user, product=product).exists()
    favorite = Favorite.objects.filter(user=user, product=product).exists()

    return liked, favorite
