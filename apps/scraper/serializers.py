from rest_framework import exceptions, serializers
from scraper.models import (
    Category,
    Comment,
    CommentStatuses,
    Favorite,
    FileTypeChoices,
    Product,
    RequestedComment,
)
from scraper.utils.queryset import (
    get_all_replies,
    get_files,
    get_user_likes_and_favorites,
)


class CategoriesSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["parent"] = {}
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
        img_link = self.context.get("img_link")
        if not img_link:
            img_link = instance.img_link
        data = super().to_representation(instance)

        if request and request.user.is_authenticated:
            liked_products, favorite_products = get_user_likes_and_favorites(
                request.user
            )
            data["liked"] = instance.id in liked_products
            data["favorite"] = instance.id in favorite_products

        data["likes"] = instance.product_likes.count()
        data["category"] = instance.category.title if instance.category else ""

        # Safely retrieve product image
        data["image"] = {
            "link": img_link,
            "type": FileTypeChoices.IMAGE,
            "stream": False,
        }

        # Use safe attribute access
        data["link"] = (
            f"https://wildberries.ru/catalog/{instance.source_id}/detail.aspx"
            if instance.source_id
            else None
        )

        return data

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "category",
            "source_id",
            "liked",
            "favorite",
            "likes",
        )


class CommentsSerializer(serializers.ModelSerializer):
    replied_comments = serializers.ListField(read_only=True)
    rating = serializers.IntegerField(required=False, default=0)
    file = serializers.FileField(write_only=True, required=False)
    user = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        request = self.context.get("request")
        user_feedback = self.context.get("user_feedback", False)
        _replies = self.context.get("replies", False)
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
        if user_feedback:
            data["product_name"] = instance.product.title if instance.product else None
            data["product_image"] = {
                "link": instance.product_image_link,
                "type": FileTypeChoices.IMAGE,
                "stream": False,
            }
        else:
            data["product_name"] = ""
            data["product_image"] = {}
        data["promo"] = instance.promo
        data["replied_comments"] = []
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        comment = self.context.get("comment", False)

        if comment and not validated_data.get("reply_to"):
            raise exceptions.ValidationError(
                {"message": "Комментарий должен быть ответил кому-то"}
            )

        source_id = validated_data.pop("source_id", None)
        product = Product.objects.filter(source_id=source_id).first()
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
        data["replied_comments"] = []
        return data

    def update(self, instance, validated_data):
        if not instance.reply_to or instance.status == CommentStatuses.NOT_ACCEPTED:
            instance.status = CommentStatuses.NOT_REVIEWED
        comment = super().update(instance, validated_data)
        RequestedComment.objects.update_or_create(**validated_data)
        return comment

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
    product = serializers.SerializerMethodField()
    product_id = serializers.IntegerField(write_only=True)

    def get_product(self, obj):
        # Pass the img_link to the ProductSerializer
        product_data = ProductsSerializer(
            obj.product, context={**self.context, "img_link": obj.img_link}
        ).data
        return product_data

    class Meta:
        model = Favorite
        fields = (
            "id",
            "product",
            "product_id",
        )
