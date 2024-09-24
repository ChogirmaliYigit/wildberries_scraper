from core.models import BaseModel
from django.db import models
from django.db.models import Index, Q, UniqueConstraint
from django.db.models.functions import Upper
from django.utils.translation import gettext_lazy as _
from users.models import User


class Category(BaseModel):
    title: str = models.TextField(verbose_name=_("Title"), null=True, blank=True)
    parent: "Category" = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sub_categories",
        verbose_name=_("Parent category"),
    )
    source_id: int = models.PositiveBigIntegerField(
        unique=True, null=True, blank=True, verbose_name=_("Source ID")
    )
    slug_name: str = models.TextField(
        null=True, blank=True, verbose_name=_("Slug name")
    )
    shard: str = models.TextField(null=True, blank=True, verbose_name=_("Shard"))
    position: int = models.IntegerField(default=0)

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        constraints = [
            UniqueConstraint(
                fields=["title"],
                condition=~Q(title=None),
                name="unique_title_exclude_null_category",
            ),
            UniqueConstraint(
                fields=["source_id"],
                condition=~Q(source_id=None),
                name="unique_source_id_exclude_null_category",
            ),
        ]
        indexes = [
            Index(
                Upper("title"),
                name="category_title_upper_index",
            ),
        ]


class Product(BaseModel):
    title: str = models.TextField(null=True, blank=True, verbose_name=_("Title"))
    category: Category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name=_("Category"),
    )
    root: int = models.IntegerField(null=True, blank=True, verbose_name=_("Root"))
    source_id: int = models.PositiveBigIntegerField(
        unique=True, null=True, blank=True, verbose_name=_("Source ID")
    )
    image_link = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        constraints = [
            UniqueConstraint(
                fields=["title"],
                condition=~Q(title=None),
                name="unique_title_exclude_null_product",
            ),
            UniqueConstraint(
                fields=["source_id"],
                condition=~Q(source_id=None),
                name="unique_source_id_exclude_null_product",
            ),
        ]
        indexes = [
            Index(
                Upper("title"),
                name="product_title_upper_index",
            ),
        ]


class FileTypeChoices(models.TextChoices):
    IMAGE: tuple[str] = "image", _("Image")
    VIDEO: tuple[str] = "video", _("Video")


class CommentStatuses(models.TextChoices):
    ACCEPTED: tuple[str] = "accepted", _("Accepted")
    NOT_ACCEPTED: tuple[str] = "not_accepted", _("Not accepted")
    NOT_REVIEWED: tuple[str] = "not_reviewed", _("Not reviewed")


class Comment(BaseModel):
    product: Product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="product_comments",
        verbose_name=_("Product"),
    )
    source_id: int = models.PositiveBigIntegerField(
        unique=True, null=True, blank=True, verbose_name=_("Source ID")
    )
    product_source_id: int = models.PositiveBigIntegerField(null=True, blank=True)
    content: str = models.TextField(null=True, blank=True, verbose_name=_("Content"))
    rating: int = models.IntegerField(verbose_name=_("Rating"))
    status: str = models.CharField(
        max_length=50,
        verbose_name=_("Status"),
        choices=CommentStatuses.choices,
        default=CommentStatuses.NOT_REVIEWED,
    )
    user: User = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_comments",
        verbose_name=_("User"),
    )
    wb_user: str = models.TextField(
        null=True, blank=True, verbose_name=_("Wildberries user")
    )
    reply_to: "Comment" = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="replies",
        null=True,
        blank=True,
        verbose_name=_("Reply to"),
    )
    file = models.FileField(
        upload_to="comments/files/", null=True, blank=True, verbose_name=_("File")
    )
    file_type = models.CharField(
        max_length=20, choices=FileTypeChoices.choices, default=FileTypeChoices.IMAGE
    )
    source_date = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True, verbose_name=_("Reason"))
    promo = models.BooleanField(default=False, verbose_name=_("Promo"))

    def __str__(self) -> str:
        return str(self.pk)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["source_id"],
                condition=~Q(source_id=None),
                name="unique_source_id_exclude_null_comment",
            )
        ]
        verbose_name = _("Comment")
        verbose_name_plural = _("Comments")


class RequestedComment(Comment):
    class Meta:
        verbose_name = _("Requested comment")
        verbose_name_plural = _("Requested comments")


class CommentFiles(BaseModel):
    comment: Comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name=_("Comment"),
    )
    file_link: str = models.TextField(unique=True, verbose_name=_("File link"))
    file_type = models.CharField(
        max_length=20, choices=FileTypeChoices.choices, default=FileTypeChoices.IMAGE
    )

    class Meta:
        verbose_name = _("Comment file")
        verbose_name_plural = _("Comment files")


class RequestedCommentFile(CommentFiles):
    requested_comment: RequestedComment = models.ForeignKey(
        RequestedComment,
        on_delete=models.CASCADE,
        related_name="requested_files",
        verbose_name=_("Comment"),
    )

    class Meta:
        verbose_name = _("Requested comment file")
        verbose_name_plural = _("Requested comment files")


class Favorite(BaseModel):
    product: Product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="product_favorites",
        verbose_name=_("Product"),
    )
    user: User = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_("User")
    )

    class Meta:
        verbose_name = _("Favorite")
        verbose_name_plural = _("Favorites")


class Like(BaseModel):
    product: Product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="product_likes",
        verbose_name=_("Product"),
    )
    user: User = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_("User")
    )

    class Meta:
        verbose_name = _("Like")
        verbose_name_plural = _("Likes")
