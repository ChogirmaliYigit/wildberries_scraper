from datetime import datetime

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
    Prefetch,
    Q,
    When,
)
from django.db.models.expressions import F, Subquery, Value
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
    # Ensure the product_id is an integer if passed
    _product_id = int(_product_id) if _product_id else None

    sql_query = f"""
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
            AND (c.file IS NOT NULL AND c.file_type = 'image')
            {f"AND c.product_id = {_product_id}" if _product_id else ""}
        GROUP BY
            c.product_id, c.promo
    ),
    ranked_products AS (
        SELECT
            p.id AS product_id,
            COALESCE(vc.promo, FALSE) AS is_promoted,
            vc.file_link AS image_link,
            ROW_NUMBER() OVER (ORDER BY (CASE WHEN vc.promo THEN 1 ELSE 2 END), RANDOM()) AS rank
        FROM
            scraper_product p
        LEFT JOIN valid_comments vc ON p.id = vc.product_id
        {f"WHERE vc.product_id = {_product_id}" if _product_id else ""}
    ),
    final_products AS (
        SELECT
            rp.product_id,
            rp.image_link,
            CASE
                WHEN rp.is_promoted THEN 3  -- Place promoted product in 3rd position
                ELSE rp.rank + (CASE WHEN rp.rank >= 3 THEN 1 ELSE 0 END)  -- Shift other products
            END AS final_rank
        FROM
            ranked_products rp
    )
    SELECT
        product_id,
        image_link
    FROM
        final_products
    ORDER BY
        final_rank
    """

    # Execute the raw SQL query to get the product details including image_link
    with connection.cursor() as cursor:
        cursor.execute(sql_query)
        rows = cursor.fetchall()

        # Create product IDs, image_link_cases, and ordering_cases in one go
        product_ids = [row[0] for row in rows]
        image_link_cases = [
            When(
                id=row[0],
                then=Value(
                    f'{settings.BACKEND_DOMAIN.strip("/")}{settings.MEDIA_URL}{row[1]}'
                    if row[1] and not row[1].startswith("http")
                    else row[1]
                ),
            )
            for row in rows
            if row[1] is not None
        ]
        ordering_cases = [When(id=row[0], then=index) for index, row in enumerate(rows)]

    # Use the ordered product IDs to retrieve the actual Product instances
    products = (
        Product.objects.filter(id__in=product_ids)
        .only(
            "id",
            "title",
            "category",
            "source_id",
        )
        .annotate(
            img_link=Case(*image_link_cases, output_field=CharField()),
            likes_count=Count("product_likes"),
            category_title=F("category__title"),
        )
        .filter(img_link__isnull=False)
        .order_by(Case(*ordering_cases, output_field=IntegerField()))
        .select_related("category")
        .prefetch_related(Prefetch("product_likes", queryset=Like.objects.only("id")))
        .values(
            "id",
            "category_title",
            "title",
            "source_id",
            "likes_count",
            "img_link",
        )
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


def get_filtered_comments(product_id=None, no_cache=False, **filters):
    print("get products starts at", datetime.now())
    if product_id:
        cache_key = f"comment_products_{product_id}"
    else:
        cache_key = "all_products"
    print("cache key", cache_key)
    if no_cache:
        if product_id:
            products = get_all_products(product_id)
        else:
            products = get_all_products()
        print("products is not from cache, no_cache=True")
    else:
        products = cache.get(cache_key)
        if not products:
            products = get_all_products(product_id)
            cache.set(cache_key, products, timeout=settings.CACHE_DEFAULT_TIMEOUT * 3)
            print("products is not from cache")
        else:
            print("products is from cache")
    print("get products ends at", datetime.now())
    print("products_with_img_link subquery started at", datetime.now())
    products_with_img_link = products.values("img_link")[:1]
    print("products_with_img_link subquery ended at", datetime.now())
    print("base_queryset started at", datetime.now())
    base_queryset = (
        Comment.objects.filter(
            **filters,
            status=CommentStatuses.ACCEPTED,
            product__in=Subquery(products.values_list("id", flat=True)),
            requestedcomment__isnull=True,
            content__isnull=True,
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
    print("base_queryset ended at", datetime.now())
    return base_queryset


def get_files(comment):
    # Prefetch all related files at the queryset level, before calling this function
    files = []

    # Process the single `comment.file` if it exists
    if comment.file:
        file_link = f"{settings.BACKEND_DOMAIN}{settings.MEDIA_URL}{comment.file}"
        files.append(
            {
                "link": file_link,
                "type": comment.file_type,
                "stream": file_link.endswith(".m3u8"),
            }
        )

    # Process files from the `comment.files.all()` prefetched queryset
    for file in comment.files.all():
        if file.file_link:  # Ensure the file has a link
            files.append(
                {
                    "link": file.file_link,
                    "type": file.file_type,
                    "stream": file.file_link.endswith(".m3u8"),
                }
            )

    # Use set to remove duplicates
    return list({frozenset(item.items()): item for item in files}.values())


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
        cache.set(cache_key, queryset, timeout=settings.CACHE_DEFAULT_TIMEOUT * 3)

    # Extracting filter parameters from the request
    page = int(request.GET.get("page") or 1)
    count = int(request.GET.get("count") or 10)
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

    total_count = len(queryset)
    total_pages = (total_count + count - 1) // count
    next_page = page + 1 if page < total_pages else None
    previous_page = page - 1 if page > 1 else None

    # Implement pagination
    start_index = (page - 1) * count
    end_index = start_index + count
    paginated_queryset = queryset[start_index:end_index]  # Slicing the queryset

    return total_count, next_page, previous_page, page, paginated_queryset


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


def get_products_response(request, queryset):
    user_likes, user_favorites = set(), set()
    if request.user.is_authenticated:
        user_likes = Like.objects.filter(
            user=request.user,
        ).values_list("product_id", flat=True)
        user_favorites = Favorite.objects.filter(
            user=request.user,
        ).values_list("product_id", flat=True)
    data = [
        {
            "id": product.get("id"),
            "title": product.get("title"),
            "category": product.get("category_title"),
            "source_id": product.get("source_id"),
            "liked": product.get("id") in user_likes,
            "favorite": product.get("id") in user_favorites,
            "likes": product.get("likes_count"),
            "image": {
                "link": product.get("img_link"),
                "type": FileTypeChoices.IMAGE,
                "stream": False,
            },
            "link": (
                f"https://wildberries.ru/catalog/{product.get('source_id')}/detail.aspx"
                if product.get("source_id")
                else None
            ),
        }
        for product in queryset
    ]
    product_ids = [item["id"] for item in data]
    if product_ids:
        cache_feedbacks_task.apply_async(args=[product_ids])
    return data


def filter_comments(request, **filters):
    # Extracting filter parameters from the request
    product_id = request.GET.get("product_id", None)
    feedback_id = request.GET.get("feedback_id", None)

    if product_id:
        print(f"get product ({product_id}) feedbacks started at", datetime.now())
        queryset = cache_feedback_for_product(product_id)
        print(f"get product ({product_id}) feedbacks ended at", datetime.now())
    if feedback_id:
        queryset = get_filtered_comments(product_id, no_cache=True).filter(
            reply_to_id=int(feedback_id)
        )
    if not feedback_id and not product_id:
        print("getting all comments")
        cache_key = "all_comments"
        queryset = cache.get(cache_key)
        if not queryset:
            print("get_filtered_comments starts at", datetime.now())
            queryset = get_filtered_comments()
            # cache.set(cache_key, queryset, timeout=settings.CACHE_DEFAULT_TIMEOUT)
            print("get_filtered_comments came at", datetime.now())
        else:
            print("get_filtered_comments came from cache")

    print("queryset filter starts at", datetime.now())
    queryset = (
        queryset.filter(**filters)
        .select_related("user", "product", "reply_to")
        .prefetch_related("files")
    )
    print("queryset filtered at", datetime.now())

    return queryset


def get_comments_response(
    request, objects, replies=False, user_feedback=False, for_comment=False
):
    print("get_comments_response started at", datetime.now())
    user_id = request.user.id if request and request.user else None
    data = []
    print("comment objects loop started at", datetime.now())
    for comment in objects:
        files = get_files(comment)
        if not files and not for_comment:
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
                    for_comment=for_comment,
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
                "is_own": user_id == comment.user.id if comment.user else False,
                "promo": comment.promo,
                "product": comment.product.id if comment.product else None,
                "source_id": comment.source_id,
                "content": comment.content,
                "rating": comment.rating,
                "file_type": comment.file_type,
                "reply_to": comment.reply_to.id if comment.reply_to else None,
            }
        )
        data.append(response)
    print("get_comments_response ended at", datetime.now())
    return data
