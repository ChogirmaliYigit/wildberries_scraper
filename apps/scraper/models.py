from core.models import BaseModel
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils.translation import gettext_lazy as _
from scraper.utils.notify import send_comment_notification
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
    image_link: str = models.TextField(null=True, blank=True, verbose_name=_("Image"))
    source_id: int = models.PositiveBigIntegerField(
        unique=True, null=True, blank=True, verbose_name=_("Source ID")
    )
    slug_name: str = models.TextField(
        null=True, blank=True, verbose_name=_("Slug name")
    )
    shard: str = models.TextField(null=True, blank=True, verbose_name=_("Shard"))

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


class Product(BaseModel):
    title: str = models.TextField(null=True, blank=True, verbose_name=_("Title"))
    category: Category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="products",
        verbose_name=_("Category"),
    )
    root: int = models.IntegerField(null=True, blank=True, verbose_name=_("Root"))

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
            )
        ]


class ProductVariant(BaseModel):
    color: str = models.TextField(null=True, blank=True, verbose_name=_("Color"))
    price: str = models.TextField(null=True, blank=True, verbose_name=_("Price"))
    source_id: int = models.PositiveBigIntegerField(
        unique=True, null=True, blank=True, verbose_name=_("Source ID")
    )
    product: Product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="variants",
        verbose_name=_("Product"),
    )

    def __str__(self) -> str:
        return f"{self.product.title} ({self.color}) - {self.price}"

    class Meta:
        verbose_name = _("Product variant")
        verbose_name_plural = _("Product variants")
        constraints = [
            UniqueConstraint(
                fields=["source_id"],
                condition=~Q(source_id=None),
                name="unique_source_id_exclude_null_product_variant",
            )
        ]


class ProductVariantImage(BaseModel):
    variant: ProductVariant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="images",
        verbose_name=_("Product variant"),
    )
    image_link: str = models.TextField(unique=True, verbose_name=_("Image link"))

    def __str__(self) -> str:
        return self.image_link

    class Meta:
        verbose_name = _("Product variant image")
        verbose_name_plural = _("Product variant images")


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

    def __str__(self) -> str:
        return self.content

    def save(self, *args, **kwargs):
        if self.pk:
            send_comment_notification(self)
        return super().save(*args, **kwargs)

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


class CommentFiles(BaseModel):
    comment: Comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name=_("Comment"),
    )
    file_link: str = models.TextField(
        null=True, blank=True, verbose_name=_("File link")
    )

    class Meta:
        verbose_name = _("Comment file")
        verbose_name_plural = _("Comment files")


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
