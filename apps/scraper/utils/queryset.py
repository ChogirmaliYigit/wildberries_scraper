import random

from django.conf import settings
from django.db.models import Case, Count, DateTimeField, Exists, OuterRef, Q, When
from django.db.models.functions import Coalesce
from scraper.models import (
    Comment,
    CommentFiles,
    CommentStatuses,
    ProductVariantImage,
    RequestedComment,
)


def get_filtered_products(queryset, promo=False):
    # Subquery to check for valid comments related to a product
    valid_comments_subquery = base_comment_filter(
        Comment.objects.filter(product=OuterRef("pk")), not_list=True
    )

    # Subquery to check for promoted comments related to a product
    promoted_comments_subquery = Comment.objects.filter(
        product=OuterRef("pk"), promo=True
    )

    # Annotate the products with valid comments and promoted status
    products = (
        queryset.annotate(
            has_valid_comments=Exists(valid_comments_subquery),
            is_promoted=Exists(promoted_comments_subquery),
        )
        .filter(has_valid_comments=True)  # Only products with valid comments
        .order_by("?")  # Shuffle products randomly
        .distinct()
    )

    # Add logic to filter products that have an image
    products_with_images = []
    for product in products:
        image = get_product_image(product)  # Check if the product has an image
        if image:  # Only include products with an image
            products_with_images.append(product)

    if not promo:
        return products_with_images  # Return products with images

    # Separate promoted and non-promoted products
    promoted_products = [
        product for product in products_with_images if product.is_promoted
    ]
    non_promoted_products = [
        product for product in products_with_images if not product.is_promoted
    ]

    # Randomly select one promoted product if available
    selected_promo_product = None
    if promoted_products:
        selected_promo_product = random.choice(promoted_products)

    # Insert the selected promoted product at index 2 if it exists
    if selected_promo_product:
        if len(non_promoted_products) > 2:
            non_promoted_products.insert(2, selected_promo_product)
        else:
            non_promoted_products.append(selected_promo_product)

    return non_promoted_products


def base_comment_filter(queryset, has_file=True, not_list=False):
    if has_file:
        # Filter the main comments with files (either in the 'file' field or related 'files' objects)
        queryset = (
            queryset.filter(
                status=CommentStatuses.ACCEPTED,
                content__isnull=False,
                content__gt="",  # Ensures the content is not an empty string
            )
            .filter(Q(files__isnull=False) | Q(file__isnull=False, file__gt=""))
            .annotate(num_files=Count("files"))  # Annotate with number of related files
            .filter(
                Q(num_files__gt=0)
                | Q(
                    file__isnull=False, file__gt=""
                )  # Filter out comments without files
            )
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

    if not_list:
        return queryset

    # Fetch all comments and apply distinct manually in Python
    comment_list = list(queryset)

    # Use a set to track seen (content, ordering_date) pairs and filter duplicates
    seen = set()
    distinct_comments = []
    for comment in comment_list:
        identifier = (comment.content, comment.ordering_date)
        if identifier not in seen:
            distinct_comments.append(comment)
            seen.add(identifier)

    return distinct_comments


def get_filtered_comments(queryset=None, promo=False, has_file=True):
    if queryset is None:
        queryset = Comment.objects.filter(status=CommentStatuses.ACCEPTED)

    base_queryset = base_comment_filter(queryset, has_file)

    # Randomly select one promoted comment
    selected_promo_comment = None
    promotes = [comment for comment in base_queryset if comment.promo]
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


def get_product_image(instance):
    # Check for image from comment files
    comments = base_comment_filter(
        Comment.objects.filter(status=CommentStatuses.ACCEPTED, product=instance)
    )
    first_comment = comments[0] if len(comments) > 0 else None
    # Initialize image variable
    image = None
    # Check if first_comment exists before trying to access its fields
    if first_comment:
        # Try getting the image from the comment's file
        if first_comment.file:
            image = {
                "link": f"{settings.BACKEND_DOMAIN}{settings.MEDIA_URL}{first_comment.file}",
                "type": first_comment.file_type,
            }
        # If no image from the first_comment, check comment files
        if not image:
            comment_file = CommentFiles.objects.filter(comment=first_comment.pk).first()
            if comment_file and comment_file.file_link:
                image = {
                    "link": comment_file.file_link,
                    "type": comment_file.file_type,
                }
    # If no image from comments, check product variant images
    if not image:
        variant_image = ProductVariantImage.objects.filter(
            variant__product=instance
        ).first()
        # If a variant image exists, use it
        if variant_image:
            image = {
                "link": variant_image.image_link,
                "type": variant_image.file_type,
            }
        else:
            # Exclude the product if no image is found
            return None
    return image
