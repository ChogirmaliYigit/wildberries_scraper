from rest_framework import serializers
from scraper.models import Category, Comment, Favorite, Product, ProductVariant
from users.serializers import UserSerializer


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
            "image_link",
            "source_id",
        )


class ProductVariantsSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()

    def get_images(self, variant):
        return [pv.image_link for pv in variant.images.all()]

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

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "category",
            "variants",
        )


class CommentsSerializer(serializers.ModelSerializer):
    product = ProductsSerializer(many=False)
    user = UserSerializer(many=False)
    replies = serializers.ListField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["replies"] = (
            CommentsSerializer(instance.replies.all(), many=True).data
            if instance.replies.all()
            else {}
        )
        return data

    class Meta:
        model = Comment
        fields = (
            "id",
            "user",
            "product",
            "source_id",
            "content",
            "rating",
            "replies",
        )


class FavoritesSerializer(serializers.ModelSerializer):
    product = ProductsSerializer(many=False)

    class Meta:
        model = Favorite
        fields = (
            "id",
            "product",
        )
