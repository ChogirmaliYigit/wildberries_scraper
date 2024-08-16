from core.models import BaseModel
from django.db import models
from django.db.models import Q, UniqueConstraint
from users.models import User


class Category(BaseModel):
    title: str = models.TextField(null=True, blank=True)
    parent: "Category" = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sub_categories",
    )
    image_link: str = models.TextField(null=True, blank=True)
    source_id: int = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    slug_name: str = models.TextField(null=True, blank=True)
    shard: str = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return self.title

    class Meta:
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
            )
        ]


class Product(BaseModel):
    title: str = models.TextField(null=True, blank=True)
    category: Category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="products",
    )
    root: int = models.IntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return self.title

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["title"],
                condition=~Q(title=None),
                name="unique_title_exclude_null_product",
            )
        ]


class ProductVariant(BaseModel):
    color: str = models.TextField(null=True, blank=True)
    price: str = models.TextField(null=True, blank=True)
    source_id: int = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    product: Product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="variants",
    )

    def __str__(self) -> str:
        return f"{self.product.title} ({self.color}) - {self.price}"

    class Meta:
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
    )
    image_link: str = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return self.image_link


class CommentStatuses(models.TextChoices):
    ACCEPTED: tuple[str] = "accepted", "Accepted"
    NOT_ACCEPTED: tuple[str] = "not_accepted", "Not accepted"
    NOT_REVIEWED: tuple[str] = "not_reviewed", "Not reviewed"


class Comment(BaseModel):
    product: Product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="product_comments",
    )
    source_id: int = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    content: str = models.TextField(null=True, blank=True)
    rating: int = models.IntegerField()
    status: str = models.CharField(
        max_length=50,
        choices=CommentStatuses.choices,
        default=CommentStatuses.NOT_REVIEWED,
    )
    user: User = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_comments",
    )
    wb_user: str = models.TextField(null=True, blank=True)
    reply_to: "Comment" = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True
    )
    file = models.FileField(upload_to="comments/files/", null=True, blank=True)

    def __str__(self) -> str:
        return self.content

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["source_id"],
                condition=~Q(source_id=None),
                name="unique_source_id_exclude_null_comment",
            )
        ]


class CommentFiles(BaseModel):
    comment: Comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="files")
    file_link: str = models.TextField(null=True, blank=True)


class Favorite(BaseModel):
    product: Product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_favorites"
    )
    user: User = models.ForeignKey(User, on_delete=models.CASCADE)
