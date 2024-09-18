import random

from django.conf import settings
from django.db.models import Case, Count, DateTimeField, Exists, F, OuterRef, Q, When
from django.db.models.functions import Coalesce
from scraper.models import (
    Comment,
    CommentStatuses,
    FileTypeChoices,
    ProductVariantImage,
    RequestedComment,
)


def get_filtered_products(queryset, promo=False, for_list=False):
    # Subquery to check for valid comments related to a product
    valid_comments_subquery = base_comment_filter(
        Comment.objects.filter(product=OuterRef("pk")),
        product_list=for_list,
    )

    # Subquery to check for promoted comments related to a product
    promoted_comments_subquery = valid_comments_subquery.filter(promo=True)

    # Annotate the products with valid comments and promoted status
    products = (
        queryset.annotate(
            has_valid_comments=Exists(valid_comments_subquery),
            is_promoted=Exists(promoted_comments_subquery),
        )
        .filter(
            has_valid_comments=True
        )  # Only products with valid comments and has image
        .order_by("?")  # Shuffle products randomly
        .distinct()
    )

    if not promo:
        return products

    # Separate the promoted and non-promoted products
    promoted_products = products.filter(is_promoted=True)
    non_promoted_products = products.filter(is_promoted=False)

    non_promoted_products_list = list(non_promoted_products)

    # Randomly select one promoted product if available
    selected_promo_product = None
    if promoted_products.exists():
        selected_promo_product = random.choice(list(promoted_products))

    # Insert the selected promoted product into the list if it exists
    if selected_promo_product:
        if len(non_promoted_products_list) > 2:
            non_promoted_products_list.insert(2, selected_promo_product)
        else:
            non_promoted_products_list.append(selected_promo_product)

        # Convert the list back to a queryset
        # Note: Preserve the original order by creating a custom order
        ordered_ids = non_promoted_products.values_list("id", flat=True)
        return queryset.filter(id__in=ordered_ids)
    return products


def base_comment_filter(queryset, has_file=True, product_list=False):
    if has_file:
        # Filter the main comments with files (either in the 'file' field or related 'files' objects)
        queryset = (
            queryset.filter(
                status=CommentStatuses.ACCEPTED,
                content__isnull=False,
                content__gt="",  # Ensures the content is not an empty string
            )
            .annotate(num_files=Count("files"))  # Annotate with number of related files
            .filter(Q(num_files__gt=0) | Q(file__isnull=False, file__gt=""))
        )

    # Apply the file_type filter if product_list is True
    if product_list:
        queryset = queryset.filter(
            Q(files__file_type=FileTypeChoices.IMAGE)
            | Q(file_type=FileTypeChoices.IMAGE)
        )

    # Exclude comments where the id exists in the RequestedComment model
    requested_comment_ids = RequestedComment.objects.values_list("id", flat=True)
    queryset = queryset.exclude(id__in=requested_comment_ids)

    # Annotate with ordering_date
    queryset = queryset.annotate(
        ordering_date=Coalesce(
            "source_date", "created_at", output_field=DateTimeField()
        )
    ).order_by("-ordering_date", "content")

    # Use distinct on specific fields if database supports it
    # Django does not support DISTINCT ON directly; use group by instead

    # This approach assumes `comment` is not `id`
    distinct_comments = (
        queryset.values("content", "ordering_date")
        .annotate(id=F("id"))
        .values_list("id", flat=True)
    )

    return queryset.filter(id__in=distinct_comments)


def get_filtered_comments(queryset=None, promo=False, has_file=True):
    if queryset is None:
        queryset = Comment.objects.filter(status=CommentStatuses.ACCEPTED)

    base_queryset = base_comment_filter(queryset, has_file)

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

    # Process the single `comment.file` if it exists
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


def get_all_replies(comment, _replies=True):
    # Initialize a list to store all replies
    all_replies = []

    # Collect replies iteratively
    replies_to_process = [comment]
    while replies_to_process:
        current_comment = replies_to_process.pop()

        # Fetch replies for the current comment
        replies = (
            current_comment.replies.prefetch_related("user", "reply_to", "product")
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

        # Add replies to the list
        all_replies.extend(replies)

        if _replies:
            # Add replies to the processing list for further exploration
            replies_to_process.extend(replies)

    return all_replies


def get_product_image(instance):
    # Check if the product has an image in the comments
    queryset = Comment.objects.filter(
        product=instance,
        status=CommentStatuses.ACCEPTED,
    ).prefetch_related("files")
    queryset = base_comment_filter(queryset, product_list=True)
    image = queryset.first()

    if image:
        if image.file and image.file_type == FileTypeChoices.IMAGE:
            return {
                "link": f"{settings.BACKEND_DOMAIN}{settings.MEDIA_URL}{image.file}",
                "type": image.file_type,
                "stream": False,
            }
        # Find the image file from related files
        for file in image.files.all():
            if file.file_type == FileTypeChoices.IMAGE:
                return {
                    "link": file.file_link,
                    "type": file.file_type,
                    "stream": False,
                }

    # If no image found in comments, check product variant images
    variant_image = ProductVariantImage.objects.filter(
        variant__product=instance
    ).first()

    if variant_image:
        return {
            "link": variant_image.image_link,
            "type": variant_image.file_type,
            "stream": False,
        }

    return None
