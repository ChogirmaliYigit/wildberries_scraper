from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
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
from django.http import JsonResponse
from scraper.filters import filter_by_category
from scraper.models import (
    Comment,
    CommentStatuses,
    Favorite,
    FileTypeChoices,
    Like,
    Product,
    RequestedComment,
)

from celery import shared_task


def get_all_products(_product_id=None):
    sql_query = """
    WITH valid_comments AS (
        SELECT
            c.product_id,
            c.promo,
            MAX(CASE WHEN c.file_type = 'image' THEN c.file END) AS comment_image_link,
            MAX(CASE WHEN f.file_link NOT LIKE '%index.m3u8%' THEN f.file_link END) AS file_link
        FROM
            scraper_comment c
        LEFT JOIN
            scraper_commentfiles f ON c.id = f.comment_id
        WHERE
            c.status = 'accepted'
            AND c.content IS NOT NULL
            AND c.content <> ''
            AND c.product_id IS NOT NULL
            AND (
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
        SELECT
            p.id AS product_id,
            EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id) AS has_valid_comments,
            EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id AND vc.promo = TRUE) AS is_promoted
        FROM
            scraper_product p
        WHERE EXISTS (SELECT 1 FROM valid_comments vc WHERE vc.product_id = p.id)
    ),
    products_with_image_links AS (
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
                if not image_link.startswith("http"):
                    image_link = f'{settings.BACKEND_DOMAIN.strip("/")}{settings.MEDIA_URL}{image_link}'
                image_link_cases.append(When(id=product_id, then=Value(image_link)))

            ordering_cases.append(When(id=product_id, then=index))

        if _product_id:
            product_ids = [_product_id]

    # Use the ordered product IDs to retrieve the actual Product instances
    products = (
        Product.objects.filter(id__in=product_ids)
        .annotate(
            img_link=Case(*image_link_cases, output_field=CharField()),
            likes_count=Count("product_likes"),
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

    queryset = (
        queryset.only(
            "id",
            "source_id",
            "content",
            "rating",
            "replies",
            "file",
            "file_type",
            "files",
            "reply_to",
            "wb_user",
            "user",
            "user__id",
            "user__full_name",
            "user__email",
            "source_date",
            "created_at",
            "product",
            "product__title",
            "promo",
        )
        .annotate(
            ordering_date=Coalesce(
                "source_date", "created_at", output_field=DateTimeField()
            ),
            product_image_link=Coalesce(
                "status",
                "wb_user",
                output_field=CharField(),
            ),
        )
        .order_by("-ordering_date", "content")
    )

    return queryset


def get_filtered_comments(product_id=None, **filters):
    cache_key = f"comment_products_{product_id}"
    products = cache.get(cache_key)
    if not products:
        products = get_all_products(product_id)
        cache.set(cache_key, products, timeout=settings.CACHE_DEFAULT_TIMEOUT)
    products_with_img_link = products.filter(id=OuterRef("product_id")).values(
        "img_link"
    )[:1]
    base_queryset = (
        Comment.objects.filter(
            **filters,
            status=CommentStatuses.ACCEPTED,
            product__in=Subquery(products.values_list("id", flat=True)),
            requestedcomment__isnull=True,
        )
        .select_related("product", "user", "reply_to")
        .prefetch_related("files", "replies")
        .annotate(
            ordering_date=Coalesce(
                "source_date", "created_at", output_field=DateTimeField()
            ),
            product_img_link=Subquery(products_with_img_link, output_field=CharField()),
        )
        .order_by("-ordering_date")
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


def paginate_queryset(request, queryset):
    # Pagination logic moved to a separate function
    page_number = request.GET.get("page", 1)
    page_size = request.GET.get("count", 10)

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page_number)
    return (
        paginator.count,
        page_obj.next_page_number() if page_obj.has_next() else None,
        page_obj.previous_page_number() if page_obj.has_previous() else None,
        page_obj.number,
        page_obj,
    )


def get_paginated_response(data, total, _next=None, previous=None, current=1):
    return JsonResponse(
        {
            "total": total,
            "next": _next,
            "previous": previous,
            "current": current,
            "results": data,
        },
        safe=False,
    )


def filter_products(request):
    cache_key = "all_products"
    queryset = cache.get(cache_key)
    if not queryset:
        queryset = get_all_products()
        cache.set(cache_key, queryset, timeout=settings.CACHE_DEFAULT_TIMEOUT)

    # Extracting filter parameters from the request
    category_id = request.GET.get("category_id", None)
    source_id = request.GET.get("source_id", None)
    search_key = request.GET.get("search", None)

    if category_id:
        category_cache_key = f"filter_by_category_{category_id}"
        category_queryset = cache.get(category_cache_key)
        if not category_queryset:
            category_queryset = filter_by_category(queryset, category_id)
            cache.set(
                category_cache_key,
                category_queryset,
                timeout=settings.CACHE_DEFAULT_TIMEOUT,
            )
        queryset = category_queryset

    if source_id:
        queryset = queryset.filter(source_id=source_id)

    if search_key:
        queryset = queryset.filter(
            Q(title__icontains=search_key) | Q(category__title__icontains=search_key)
        )

    return queryset


def cache_feedback_for_product(product_id):
    cache_key = f"all_comments_{product_id}"
    queryset = cache.get(cache_key)
    if not queryset:
        queryset = get_filtered_comments(product_id)
        cache.set(cache_key, queryset, timeout=settings.CACHE_DEFAULT_TIMEOUT)
    return queryset


@shared_task
def cache_feedbacks_task(product_ids):
    for product_id in product_ids:
        cache_feedback_for_product(product_id)


def get_products_response(request, page_obj):
    data = []
    product_ids = []
    for product in page_obj.object_list:
        product_ids.append(product.id)
        liked, favorite = False, False
        if request.user.is_authenticated:
            liked, favorite = get_user_likes_and_favorites(request.user, product)
        data.append(
            {
                "id": product.id,
                "title": product.title,
                "category": product.category.title if product.category else "",
                "source_id": product.source_id,
                "liked": liked,
                "favorite": favorite,
                "likes": product.likes_count,
                "image": {
                    "link": product.img_link,
                    "type": FileTypeChoices.IMAGE,
                    "stream": False,
                },
                "link": (
                    f"https://wildberries.ru/catalog/{product.source_id}/detail.aspx"
                    if product.source_id
                    else None
                ),
            }
        )
    if product_ids:
        cache_feedbacks_task.delay(product_ids)
    return data


def filter_comments(request, **filters):
    # Extracting filter parameters from the request
    product_id = request.GET.get("product_id", None)
    source_id = request.GET.get("source_id", None)
    feedback_id = request.GET.get("feedback_id", None)

    queryset = cache_feedback_for_product(product_id)

    queryset = queryset.filter(**filters)

    # Apply filtering based on source ID
    if source_id:
        queryset = queryset.filter(source_id=source_id)

    # Apply filtering based on feedback (reply to) ID
    if feedback_id:
        feedback_cache_key = f"filter_by_feedback_{feedback_id}"
        feedback_queryset = cache.get(feedback_cache_key)
        if not feedback_queryset:
            feedback_queryset = queryset.filter(reply_to_id=feedback_id)
            cache.set(
                feedback_cache_key,
                feedback_queryset,
                timeout=settings.CACHE_DEFAULT_TIMEOUT,
            )
        queryset = feedback_queryset

    return queryset


def get_comments_response(request, objects, replies=False, user_feedback=False):
    data = []
    for comment in objects:
        files = get_files(comment)
        if not files:
            continue
        response = {}
        if replies:
            # Flatten replies
            flattened_replies = get_all_replies(comment)
            response["replied_comments"] = (
                get_comments_response(
                    request,
                    flattened_replies,
                    replies=False,
                    user_feedback=user_feedback,
                )
                if flattened_replies
                else []
            )
        if comment.wb_user:
            user = comment.wb_user
        elif comment.user:
            user = comment.user.full_name or comment.user.email
        else:
            user = "Anonymous"
        if request and comment.user:
            is_own = request.user.id == comment.user.id
        else:
            is_own = False
        if user_feedback:
            response["product_name"] = (
                comment.product.title if comment.product else None
            )
            response["product_image"] = {
                "link": getattr(comment, "product_img_link", None),
                "type": FileTypeChoices.IMAGE,
                "stream": False,
            }
        else:
            response["product_name"] = ""
            response["product_image"] = {}
        response.update(
            {
                "id": comment.id,
                "files": files,
                "user": user,
                "source_date": (
                    comment.source_date if comment.source_date else comment.created_at
                ),
                "is_own": is_own,
                "promo": comment.promo,
                "product": comment.product.id,
                "source_id": comment.source_id,
                "content": comment.content,
                "rating": comment.rating,
                "file_type": comment.file_type,
                "reply_to": comment.reply_to,
            }
        )
        data.append(response)
    return data
