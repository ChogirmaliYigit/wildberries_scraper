from django.conf import settings
from django.db.models import Case, DateTimeField, When
from rest_framework import exceptions, serializers
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    CommentStatuses,
    Favorite,
    Like,
    Product,
    ProductVariant,
    RequestedComment,
)
from scraper.tasks import scrape_product_by_source_id


def get_files(comment):
    files = []
    if comment.file:
        files.append(
            {
                "link": f"{settings.BACKEND_DOMAIN}{settings.MEDIA_URL}{comment.file}",
                "type": comment.file_type,
            }
        )
    for file in comment.files.all():
        if file.file_link:
            files.append({"link": file.file_link, "type": file.file_type})
    return files


# Collect all replies in a single list
def get_all_replies(comment):
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
        all_replies.extend(get_all_replies(reply))  # Recursively collect replies

    return all_replies


class CategoriesSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["parent"] = (
            CategoriesSerializer(instance=instance.parent).data
            if instance.parent
            else {}
        )
        return data

    class Meta:
        model = Category
        fields = (
            "id",
            "title",
            "parent",
            "source_id",
        )


class ProductVariantsSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["link"] = (
            f"https://wildberries.ru/catalog/{instance.source_id}/detail.aspx"
        )
        return data

    def get_images(self, variant):
        return [
            {"link": pv.image_link, "type": pv.file_type}
            for pv in variant.images.prefetch_related("variant").all()
        ]

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "color",
            "price",
            "source_id",
            "images",
        )


class ProductsSerializer(serializers.ModelSerializer):
    variants = ProductVariantsSerializer(many=True)
    liked = serializers.BooleanField(read_only=True, default=False)
    favorite = serializers.BooleanField(read_only=True, default=False)
    likes = serializers.IntegerField(read_only=True)

    def to_representation(self, instance):
        request = self.context.get("request")
        data = super().to_representation(instance)
        data["variants"] = ProductVariantsSerializer(
            instance.variants.all(), many=True
        ).data
        data["category"] = instance.category.title if instance.category else ""
        if request and request.user.is_authenticated:
            data["liked"] = Like.objects.filter(
                user=request.user, product=instance
            ).exists()
            data["favorite"] = Favorite.objects.filter(
                user=request.user, product=instance
            ).exists()
        data["likes"] = Like.objects.filter(product=instance).count()
        comment = CommentFiles.objects.filter(
            comment=instance.product_comments.first()
        ).first()
        data["image"] = {
            "link": comment.file_link,
            "type": comment.file_type,
        }
        return data

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "category",
            "variants",
            "liked",
            "favorite",
            "likes",
        )


class CommentsSerializer(serializers.ModelSerializer):
    replied_comments = serializers.ListField(read_only=True)
    source_id = serializers.IntegerField(required=False)
    rating = serializers.IntegerField(required=False, default=0)
    file = serializers.FileField(write_only=True, required=False)
    user = serializers.CharField(read_only=True)
    files = serializers.ListSerializer(child=serializers.FileField(), read_only=True)

    def to_representation(self, instance):
        request = self.context.get("request")
        _replies = self.context.get("replies", True)
        data = super().to_representation(instance)

        if _replies:
            # Flatten replies
            flattened_replies = get_all_replies(instance)
            data["replied_comments"] = (
                CommentsSerializer(
                    flattened_replies, many=True, context={"replies": False}
                ).data
                if flattened_replies
                else []
            )
        data["files"] = get_files(instance)
        if instance.wb_user:
            user = instance.wb_user
        elif instance.user:
            user = instance.user.full_name or instance.user.email
        else:
            user = "Anonymous"
        data["user"] = user
        data["source_date"] = (
            instance.source_date if instance.source_date else instance.created_at
        )
        if request and instance.user:
            is_own = request.user.id == instance.user.id
        else:
            is_own = False
        data["is_own"] = is_own
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        comment = self.context.get("comment", False)

        if comment and not validated_data.get("reply_to"):
            raise exceptions.ValidationError(
                {"message": "Комментарий должен быть ответил кому-то"}
            )

        source_id = validated_data.pop("source_id", None)
        variant = (
            ProductVariant.objects.filter(source_id=source_id)
            .prefetch_related("product")
            .first()
        )
        product = variant.product if variant else None
        if product:
            validated_data["product"] = product
        validated_data["user"] = request.user
        if request.query_params.get("direct", "false") == "true":
            status = CommentStatuses.ACCEPTED
        else:
            status = CommentStatuses.NOT_REVIEWED
        validated_data["status"] = status

        comment_instance = super().create(validated_data)

        if source_id and not product:
            scrape_product_by_source_id.delay(source_id, comment_instance.pk)

        if request.query_params.get("direct", "false") != "true":
            try:
                RequestedComment.objects.create(**validated_data)
            except Exception:
                pass

        return comment_instance

    class Meta:
        model = Comment
        fields = (
            "id",
            "user",
            "product",
            "source_id",
            "content",
            "rating",
            "files",
            "file",
            "file_type",
            "reply_to",
            "replied_comments",
            "source_date",
        )


class CommentDetailSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["files"] = get_files(instance)
        data["source_date"] = (
            instance.source_date if instance.source_date else instance.created_at
        )
        flattened_replies = get_all_replies(instance)
        data["replied_comments"] = (
            CommentsSerializer(flattened_replies, many=True).data
            if flattened_replies
            else None
        )
        return data

    class Meta:
        model = Comment
        fields = (
            "id",
            "product",
            "source_id",
            "content",
            "rating",
            "status",
            "reply_to",
            "source_date",
        )
        extra_kwargs = {
            "status": {"read_only": True},
            "product": {"read_only": True},
            "source_date": {"read_only": True},
        }


class FavoritesSerializer(serializers.ModelSerializer):
    product = ProductsSerializer(many=False, read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Favorite
        fields = (
            "id",
            "product",
            "product_id",
        )


class LikesSerializer(serializers.ModelSerializer):
    product = ProductsSerializer(many=False, read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    def create(self, validated_data):
        request = self.context.get("request")
        product = (
            Product.objects.prefetch_related("category")
            .filter(id=validated_data.get("product_id"))
            .first()
        )
        if not product:
            raise exceptions.ValidationError({"message": "Товар не найден"})
        like = Like.objects.create(user=request.user, product=product)
        return like
