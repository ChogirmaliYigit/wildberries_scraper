from rest_framework import exceptions, serializers
from scraper.models import (
    Category,
    Comment,
    CommentStatuses,
    Favorite,
    Like,
    Product,
    ProductVariant,
    RequestedComment,
)
from scraper.utils.queryset import get_all_replies, get_files, get_product_image


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


class ProductsSerializer(serializers.ModelSerializer):
    liked = serializers.BooleanField(read_only=True, default=False)
    favorite = serializers.BooleanField(read_only=True, default=False)
    likes = serializers.IntegerField(read_only=True)

    def to_representation(self, instance):
        request = self.context.get("request")
        data = super().to_representation(instance)
        data["category"] = instance.category.title if instance.category else ""
        if request and request.user.is_authenticated:
            data["liked"] = Like.objects.filter(
                user=request.user, product=instance
            ).exists()
            data["favorite"] = Favorite.objects.filter(
                user=request.user, product=instance
            ).exists()
        data["likes"] = Like.objects.filter(product=instance).count()
        image = get_product_image(instance)
        if not image:
            return None
        data["image"] = image
        source_id = instance.variants.first().source_id
        data["link"] = f"https://wildberries.ru/catalog/{source_id}/detail.aspx"
        data["source_id"] = source_id
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
        data["product_name"] = instance.product.title if instance.product else None
        data["product_image"] = (
            get_product_image(instance.product) if instance.product else None
        )
        data["promo"] = instance.promo
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
            comment_instance.product_source_id = source_id
            comment_instance.save(update_fields=["product_source_id"])

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
            "promo",
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

    def update(self, instance, validated_data):
        if instance.status == CommentStatuses.NOT_ACCEPTED:
            instance.status = CommentStatuses.NOT_REVIEWED
        return super().update(instance, validated_data)

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
