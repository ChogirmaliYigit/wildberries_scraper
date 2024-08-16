from django.conf import settings
from rest_framework import exceptions, serializers
from scraper.models import (
    Category,
    Comment,
    CommentStatuses,
    Favorite,
    Product,
    ProductVariant,
)


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

    def get_images(self, variant):
        return [
            pv.image_link for pv in variant.images.prefetch_related("variant").all()
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["variants"] = ProductVariantsSerializer(
            instance.variants.all(), many=True
        ).data
        data["category"] = instance.category.title
        return data

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "category",
            "variants",
        )


class CommentsSerializer(serializers.ModelSerializer):
    replies = serializers.ListField(read_only=True)
    source_id = serializers.IntegerField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["replies"] = (
            CommentsSerializer(
                instance.replies.prefetch_related("user", "reply_to", "product").all(),
                many=True,
            ).data
            if instance.replies.prefetch_related("user", "reply_to", "product").all()
            else {}
        )
        if instance.file_link:
            data["file"] = instance.file_link
        else:
            data["file"] = (
                f"{settings.BACKEND_DOMAIN}{data.get('file')}"
                if data.get("file")
                else ""
            )
        if instance.wb_user:
            data["user"] = instance.wb_user
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        source_id = validated_data.pop("source_id", None)
        validated_data["status"] = CommentStatuses.NOT_REVIEWED
        product = (
            Product.objects.prefetch_related("category")
            .filter(source_id=source_id)
            .first()
        )
        if source_id and product:
            validated_data["product"] = product
        validated_data["user"] = request.user
        return super().create(validated_data)

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
            "replies",
        )


class FavoritesSerializer(serializers.ModelSerializer):
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
            raise exceptions.ValidationError({"message": "Product not found"})
        favorite = Favorite.objects.create(user=request.user, product=product)
        return favorite

    class Meta:
        model = Favorite
        fields = (
            "id",
            "product",
            "product_id",
        )
