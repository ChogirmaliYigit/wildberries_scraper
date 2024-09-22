from django.conf import settings
from django.db import connection
from django.db.models import Case, Count, DateTimeField, IntegerField, Q, When
from django.db.models.expressions import Subquery
from django.db.models.functions import Coalesce
from scraper.models import (
    Comment,
    CommentStatuses,
    Favorite,
    FileTypeChoices,
    Like,
    Product,
    ProductVariantImage,
    RequestedComment,
)


def get_filtered_products():
    sql_query = """
    WITH valid_comments AS (
        SELECT
            c.product_id,
            c.promo
        FROM
            scraper_comment c
        WHERE
            c.product_id IS NOT NULL AND
            (c.file IS NOT NULL OR EXISTS (
                SELECT 1 FROM scraper_commentfiles f
                WHERE f.comment_id = c.id
            ))
    ),
    filtered_comments AS (
        SELECT
            c.product_id,
            c.file,
            c.file_type,
            COUNT(f.id) AS num_files
        FROM
            scraper_comment c
        LEFT JOIN
            scraper_commentfiles f ON c.id = f.comment_id
        WHERE
            c.status = 'ACCEPTED' AND
            (c.content IS NOT NULL AND c.content <> '') AND
            c.product_id IS NOT NULL
        GROUP BY
            c.product_id, c.file, c.file_type
    ),
    products_with_comments AS (
        SELECT
            p.id AS product_id,
            EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id) AS has_valid_comments,
            EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id AND vc.promo = TRUE) AS is_promoted
        FROM
            scraper_product p
        WHERE
            EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id)
        ORDER BY
            RANDOM()
    ),
    products_with_image_links AS (
        SELECT
            pwc.product_id,
            (SELECT CONCAT('{BACKEND_DOMAIN}', '{MEDIA_URL}', f.file_link)
             FROM filtered_comments fc
             JOIN scraper_commentfiles f ON fc.product_id = pwc.product_id
             WHERE f.file_type = 'IMAGE'
             LIMIT 1) AS image_link
        FROM
            products_with_comments pwc
    ),
    promoted_products AS (
        SELECT product_id
        FROM products_with_comments
        WHERE is_promoted = TRUE
    ),
    non_promoted_products AS (
        SELECT product_id
        FROM products_with_comments
        WHERE is_promoted = FALSE
    ),
    final_products AS (
        SELECT product_id, ROW_NUMBER() OVER () AS rn
        FROM non_promoted_products

        UNION ALL

        SELECT product_id, ROW_NUMBER() OVER () AS rn
        FROM promoted_products
    )
    SELECT
        fp.product_id,
        pwc.has_valid_comments,
        pwc.is_promoted,
        pil.image_link
    FROM
        final_products fp
    JOIN
        products_with_comments pwc ON fp.product_id = pwc.product_id
    LEFT JOIN
        products_with_image_links pil ON fp.product_id = pil.product_id
    ORDER BY
        CASE
            WHEN fp.rn = 3 THEN 0  -- Custom logic for ordering
            ELSE fp.rn
        END
    """

    # Execute the raw SQL query to get the list of product IDs
    with connection.cursor() as cursor:
        cursor.execute(sql_query)
        product_ids = [row[0] for row in cursor.fetchall()]

    # Create a custom ordering for the products based on the SQL result
    ordering = Case(
        *[When(id=product_id, then=pos) for pos, product_id in enumerate(product_ids)],
        output_field=IntegerField(),
    )

    # Use the ordered product IDs to retrieve the actual Product instances
    return Product.objects.filter(id__in=product_ids).order_by(ordering)


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


def get_product_image(instance, product_list=False):
    image = base_comment_filter(
        Comment.objects.filter(product=instance, status=CommentStatuses.ACCEPTED)
        .prefetch_related("files")
        .annotate(num_files=Count("files"))
        .filter(Q(num_files__gt=0) | Q(file__isnull=False, file__gt="")),
        has_file=True,
        product_list=product_list,
    ).first()

    if image:
        if image.file and image.file_type == FileTypeChoices.IMAGE:
            result = {
                "link": f"{settings.BACKEND_DOMAIN}{settings.MEDIA_URL}{image.file}",
                "type": image.file_type,
                "stream": False,
            }
            return result
        file = image.files.filter(file_type=FileTypeChoices.IMAGE).first()
        if file and file.file_link:
            result = {
                "link": file.file_link,
                "type": file.file_type,
                "stream": False,
            }
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
    return result


def get_user_likes_and_favorites(user):
    liked_products = set(
        Like.objects.filter(user=user).values_list("product_id", flat=True)
    )
    favorite_products = set(
        Favorite.objects.filter(user=user).values_list("product_id", flat=True)
    )

    return liked_products, favorite_products
