from django.db.models import DateTimeField, Exists, OuterRef
from django.db.models.functions import Coalesce
from scraper.models import (
    Comment,
    CommentFiles,
    CommentStatuses,
    Product,
    ProductVariantImage,
)


def get_filtered_products():
    return Product.objects.annotate(
        has_comments=Exists(Comment.objects.filter(product=OuterRef("pk"))),
        has_images=Exists(
            ProductVariantImage.objects.filter(variant__product=OuterRef("pk"))
        ),
    ).filter(has_comments=True, has_images=True)


def get_filtered_comments(queryset=None):
    if queryset is None:
        queryset = Comment.objects.all()
    queryset = queryset.annotate(
        has_files=Exists(CommentFiles.objects.filter(comment=OuterRef("pk")))
    ).filter(has_files=True, status=CommentStatuses.ACCEPTED, content__isnull=False)
    queryset = queryset.annotate(
        ordering_date=Coalesce(
            "source_date", "created_at", output_field=DateTimeField()
        )
    ).order_by("-ordering_date")
    return queryset
