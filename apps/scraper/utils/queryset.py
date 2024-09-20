import random

from django.conf import settings
from django.core.cache import cache
from django.db.models import (
    Case,
    Count,
    DateTimeField,
    Exists,
    OuterRef,
    Q,
    Subquery,
    When,
)
from django.db.models.functions import Coalesce
from scraper.models import (
    Comment,
    CommentStatuses,
    Favorite,
    FileTypeChoices,
    Like,
    ProductVariantImage,
    RequestedComment,
)


def get_filtered_products(queryset, promo=False, for_list=False):
    cache_key = f"filtered_products_{promo}_{for_list}"
    cached_products = cache.get(cache_key)
    if cached_products:
        return cached_products

    # Use only relevant fields in the subquery to improve performance
    valid_comments_subquery = base_comment_filter(
        Comment.objects.filter(product=OuterRef("pk")),
        product_list=for_list,
    ).values(
        "id"
    )  # Limit to necessary fields

    promoted_comments_subquery = valid_comments_subquery.filter(promo=True)

    products = (
        queryset.annotate(
            has_valid_comments=Exists(valid_comments_subquery),
            is_promoted=Exists(promoted_comments_subquery),
        )
        .filter(has_valid_comments=True)
        .distinct()
    )

    # If not promo, return immediately
    if not promo:
        cache.set(cache_key, products, timeout=600)
        return products

    # Separate promoted and non-promoted products
    promoted_products = products.filter(is_promoted=True)
    non_promoted_products = products.filter(is_promoted=False)

    if promoted_products.exists():
        selected_promo_product = random.choice(list(promoted_products))

        # Insert promo product into the non-promoted list at index 2
        non_promoted_products_list = list(non_promoted_products)
        if len(non_promoted_products_list) > 2:
            non_promoted_products_list.insert(2, selected_promo_product)
        else:
            non_promoted_products_list.append(selected_promo_product)

        # Convert back to queryset
        products = queryset.filter(
            id__in=[product.id for product in non_promoted_products_list]
        )

    cache.set(cache_key, products, timeout=600)
    return products


def base_comment_filter(queryset, has_file=True, product_list=False):
    if has_file:
        queryset = (
            queryset.filter(
                status=CommentStatuses.ACCEPTED,
                content__isnull=False,
                content__gt="",
            )
            .annotate(num_files=Count("files"))
            .filter(Q(num_files__gt=0) | Q(file__isnull=False, file__gt=""))
        )

    if product_list:
        queryset = queryset.filter(
            Q(files__file_type=FileTypeChoices.IMAGE)
            | Q(file_type=FileTypeChoices.IMAGE)
        )
        return queryset

    # Exclude comments where the id exists in the RequestedComment model
    requested_comment_ids = RequestedComment.objects.values_list("id", flat=True)
    queryset = queryset.exclude(id__in=requested_comment_ids)

    # Annotate with ordering_date
    annotated_queryset = queryset.annotate(
        ordering_date=Coalesce(
            "source_date", "created_at", output_field=DateTimeField()
        )
    ).values("id")

    # Filter the original queryset using the subquery
    queryset = (
        queryset.filter(id__in=Subquery(annotated_queryset))
        .annotate(
            ordering_date=Coalesce(
                "source_date", "created_at", output_field=DateTimeField()
            )
        )
        .order_by("-ordering_date", "content")
    )

    return queryset


def get_filtered_comments(queryset, has_file=True):
    cache_key = f"filtered_comments_{has_file}"
    cached_comments = cache.get(cache_key)
    if cached_comments:
        return cached_comments

    base_queryset = base_comment_filter(queryset, has_file)

    cache.set(cache_key, base_queryset, timeout=500)
    return base_queryset


def get_files(comment):
    cache_key = f"comment_files_{comment.pk}"
    cached_comment_files = cache.get(cache_key)
    if cached_comment_files:
        return cached_comment_files

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

    cache.set(cache_key, files, timeout=100)
    return files


def get_all_replies(comment, _replies=True):
    cache_key = f"comment_replies_{comment.pk}_{_replies}"
    cached_comment_replies = cache.get(cache_key)
    if cached_comment_replies:
        return cached_comment_replies

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

    cache.set(cache_key, all_replies, timeout=180)
    return all_replies


def get_product_image(instance):
    cache_key = f"product_image_{instance.pk}"
    cached_image = cache.get(cache_key)
    if cached_image:
        return cached_image

    image = (
        Comment.objects.filter(product=instance, status=CommentStatuses.ACCEPTED)
        .prefetch_related("files")
        .annotate(num_files=Count("files"))
        .filter(Q(num_files__gt=0) | Q(file__isnull=False, file__gt=""))
        .first()
    )

    if image:
        if image.file and image.file_type == FileTypeChoices.IMAGE:
            result = {
                "link": f"{settings.BACKEND_DOMAIN}{settings.MEDIA_URL}{image.file}",
                "type": image.file_type,
                "stream": False,
            }
            cache.set(cache_key, result, timeout=60)
            return result
        file = image.files.filter(file_type=FileTypeChoices.IMAGE).first()
        if file and file.file_link:
            result = {
                "link": file.file_link,
                "type": file.file_type,
                "stream": False,
            }
            cache.set(cache_key, result, timeout=60)
            return result

    # Fallback to product variants
    variant_image = ProductVariantImage.objects.filter(
        variant__product=instance
    ).first()
    result = (
        {
            "link": variant_image.image_link,
            "type": variant_image.file_type,
            "stream": False,
        }
        if variant_image
        else None
    )
    if result:
        cache.set(cache_key, result, timeout=60)
    return result


def get_user_likes_and_favorites(user):
    cache_key_liked = f"user_likes_{user.pk}"
    cache_key_favorite = f"user_favorites_{user.pk}"

    liked_products = cache.get(cache_key_liked)
    favorite_products = cache.get(cache_key_favorite)

    if liked_products is None:
        liked_products = set(
            Like.objects.filter(user=user).values_list("product_id", flat=True)
        )
        cache.set(cache_key_liked, liked_products, timeout=600)

    if favorite_products is None:
        favorite_products = set(
            Favorite.objects.filter(user=user).values_list("product_id", flat=True)
        )
        cache.set(cache_key_favorite, favorite_products, timeout=600)

    return liked_products, favorite_products
