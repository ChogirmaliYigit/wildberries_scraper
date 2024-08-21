from django.conf import settings
from rest_framework import exceptions, serializers
from scraper.models import (
    Category,
    Comment,
    CommentStatuses,
    Favorite,
    Like,
    Product,
    ProductVariant,
)
from scraper.utils import wildberries


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
    file_type = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["file_type"] = "image"
        return data

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
            "file_type",
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
        data["category"] = instance.category.title
        if request and request.user.is_authenticated:
            data["liked"] = Like.objects.filter(
                user=request.user, product=instance
            ).exists()
            data["favorite"] = Favorite.objects.filter(
                user=request.user, product=instance
            ).exists()
        data["likes"] = Like.objects.filter(product=instance).count()
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
    source_id = serializers.IntegerField()
    rating = serializers.IntegerField(required=False, default=0)
    file = serializers.FileField(write_only=True, required=False)
    user = serializers.CharField(read_only=True)
    files = serializers.ListSerializer(child=serializers.FileField(), read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        replies = instance.replies.prefetch_related("user", "reply_to", "product").all()
        data["replied_comments"] = (
            CommentsSerializer(replies, many=True).data if replies else []
        )
        data["files"] = self.get_files(instance)
        if instance.wb_user:
            data["user"] = instance.wb_user
        elif instance.user:
            data["user"] = instance.user.full_name or instance.user.email
        return data

    def get_files(self, comment):
        files = []
        if comment.file:
            files.append(
                f"{settings.BACKEND_DOMAIN}/{settings.MEDIA_URL}{comment.file}"
            )
        for file in comment.files.all():
            if file.file_link:
                files.append(file.file_link)
        return files

    def create(self, validated_data):
        request = self.context.get("request")
        comment = self.context.get("comment", False)
        if comment and not validated_data.get("reply_to"):
            raise exceptions.ValidationError(
                {"message": "Комментарий должен быть ответил кому-то"}
            )
        source_id = validated_data.pop("source_id", None)
        validated_data["status"] = CommentStatuses.NOT_REVIEWED
        variant = (
            ProductVariant.objects.filter(source_id=source_id)
            .prefetch_related("product")
            .first()
        )
        product = variant.product if variant else None
        if source_id:
            if not product:
                try:
                    product = wildberries.get_product_by_source_id(source_id)
                except Exception as exc:
                    product = None
                    print(
                        f"Exception while scraping product by source id: {exc.__class__.__name__}: {exc}"
                    )
            if product:
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
            "files",
            "file",
            "reply_to",
            "replied_comments",
        )


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
