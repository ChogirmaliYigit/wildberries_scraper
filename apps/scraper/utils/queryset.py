from django.conf import settings
from django.db import connection
from django.db.models import (
    Case,
    CharField,
    Count,
    DateTimeField,
    IntegerField,
    Q,
    When,
)
from django.db.models.expressions import OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from scraper.models import (
    CommentStatuses,
    Favorite,
    FileTypeChoices,
    Like,
    Product,
    RequestedComment,
)


def get_filtered_products():
    sql_query = """
    WITH valid_comments AS (
        -- Same logic to filter valid comments and join scraper_commentfiles
        SELECT
            c.product_id,
            c.promo,
            MAX(CASE
                WHEN c.file_type = 'image' THEN c.file
                ELSE NULL
            END) AS comment_image_link,
            MAX(CASE
                WHEN f.file_link NOT LIKE '%index.m3u8%' THEN f.file_link
                ELSE NULL
            END) AS file_link
        FROM
            scraper_comment c
        LEFT JOIN
            scraper_commentfiles f ON c.id = f.comment_id
        WHERE
            c.status = 'accepted' AND
            c.content IS NOT NULL AND c.content <> '' AND
            c.product_id IS NOT NULL AND (
                (c.file IS NOT NULL AND c.file_type = 'image') OR
                EXISTS (
                    SELECT 1 FROM scraper_commentfiles f2
                    WHERE f2.comment_id = c.id
                    AND f2.file_type = 'image'
                    AND f2.file_link NOT LIKE '%index.m3u8%'
                )
            )
        GROUP BY
            c.product_id, c.promo
    ),
    products_with_comments AS (
        -- Flag products with comments and promotions
        SELECT
            p.id AS product_id,
            EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id) AS has_valid_comments,
            EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id AND vc.promo = TRUE) AS is_promoted
        FROM
            scraper_product p
        WHERE EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id)
    ),
    products_with_image_links AS (
        -- Select image links for products
        SELECT
            pwc.product_id,
            COALESCE(
                NULLIF((SELECT vc.comment_image_link FROM valid_comments vc WHERE vc.product_id = pwc.product_id LIMIT 1), ''),
                NULLIF((SELECT vc.file_link FROM valid_comments vc WHERE vc.product_id = pwc.product_id LIMIT 1), '')
            ) AS image_link
        FROM
            products_with_comments pwc
    ),
    ranked_products AS (
        -- Rank products with random order
        SELECT
            np.product_id,
            np.has_valid_comments,
            np.is_promoted,
            pil.image_link,
            ROW_NUMBER() OVER (
                ORDER BY RANDOM()
            ) AS rank
        FROM
            products_with_comments np
        LEFT JOIN
            products_with_image_links pil ON np.product_id = pil.product_id
    ),
    promoted_products AS (
        -- Select one random promoted product
        SELECT
            product_id
        FROM
            ranked_products
        WHERE
            is_promoted = TRUE
        ORDER BY RANDOM()
        LIMIT 1
    ),
    final_products AS (
        SELECT
            rp.product_id,
            rp.has_valid_comments,
            rp.is_promoted,
            rp.image_link,
            CASE
                WHEN rp.product_id = (SELECT product_id FROM promoted_products) THEN 3  -- Place one promoted product in 3rd position
                WHEN rp.rank >= 3 THEN rp.rank + 1  -- Shift other products down to make room for the 3rd position
                ELSE rp.rank  -- Leave products ranked before 3 untouched
            END AS final_rank
        FROM
            ranked_products rp
    )
    SELECT
        product_id, has_valid_comments, is_promoted, image_link
    FROM
        final_products
    ORDER BY
        final_rank;
    """

    # Execute the raw SQL query to get the product details including image_link
    with connection.cursor() as cursor:
        cursor.execute(sql_query)

        # Create a mapping of product IDs to their image links
        image_link_cases = []
        product_ids = []
        ordering_cases = []
        for index, row in enumerate(cursor.fetchall()):
            product_id = row[0]
            image_link = row[3]

            if image_link is not None:
                product_ids.append(product_id)
                if image_link.startswith("comments"):
                    image_link = f'{settings.BACKEND_DOMAIN.strip("/")}{settings.MEDIA_URL}{image_link}'
                image_link_cases.append(When(id=product_id, then=Value(image_link)))

            ordering_cases.append(When(id=product_id, then=index))

    # Use the ordered product IDs to retrieve the actual Product instances
    products = (
        Product.objects.filter(id__in=product_ids)
        .annotate(
            img_link=Case(*image_link_cases, output_field=CharField()),
        )
        .order_by(Case(*ordering_cases, output_field=IntegerField()))
        .select_related("category")
        .prefetch_related("product_likes")
    )

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

    # Exclude comments where the id exists in the RequestedComment model
    requested_comment_ids = RequestedComment.objects.values_list("id", flat=True)
    queryset = queryset.exclude(id__in=requested_comment_ids)

    if product_list:
        queryset = queryset.filter(
            Q(files__file_type=FileTypeChoices.IMAGE)
            | Q(file_type=FileTypeChoices.IMAGE)
        )

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

    filtered_products = get_filtered_products()

    queryset = queryset.annotate(
        product_image_link=Subquery(
            filtered_products.filter(id=OuterRef("product_id")).values("img_link")[:1],
            output_field=CharField(),
        )
    )

    return queryset


def get_filtered_comments(queryset, has_file=True):
    base_queryset = base_comment_filter(
        queryset.filter(status=CommentStatuses.ACCEPTED)
        .select_related("product", "user", "reply_to")
        .prefetch_related("files", "replies"),
        has_file,
    )
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
        replies = current_comment.replies.filter(
            requestcomment__isnull=True
        ).prefetch_related("user", "reply_to", "product")

        # Add replies to the list
        all_replies.extend(replies)

        if _replies:
            # Add replies to the processing list for further exploration
            replies_to_process.extend(replies)

    return all_replies


def get_user_likes_and_favorites(user):
    liked_products = set(
        Like.objects.filter(user=user).values_list("product_id", flat=True)
    )
    favorite_products = set(
        Favorite.objects.filter(user=user).values_list("product_id", flat=True)
    )

    return liked_products, favorite_products
