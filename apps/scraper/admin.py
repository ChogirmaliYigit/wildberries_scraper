from django.contrib import admin
from django.db.models import ForeignKey
from django.http import HttpRequest
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    Product,
    ProductVariant,
    ProductVariantImage,
)
from unfold.admin import ModelAdmin, TabularInline


class ProductsInline(TabularInline):
    model = Product
    fields = ("title",)
    extra = 1
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = (
        "title",
        "parent",
        "image_link",
        "source_id",
    )
    fields = (
        "title",
        "parent",
        "image_link",
        "source_id",
        "slug_name",
        "shard",
    )
    search_fields = (
        "title",
        "source_id",
        "image_link",
        "id",
        "slug_name",
        "shard",
    )
    list_filter = ("parent",)
    inlines = [ProductsInline]
    actions = [
        "clear_source_ids",
    ]

    def clear_source_ids(self, request, queryset):
        Category.objects.filter(source_id=0).update(source_id=None)
        self.message_user(request, "Category source ids cleared")

    def formfield_for_foreignkey(
        self, db_field: ForeignKey, request: HttpRequest, **kwargs
    ):
        if db_field.name == "parent":
            object_id = request.resolver_match.kwargs.get("object_id")
            if object_id:
                kwargs["queryset"] = Category.objects.exclude(pk=object_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProductVariantsInline(TabularInline):
    model = ProductVariant
    fields = (
        "color",
        "price",
        "source_id",
    )
    extra = 1
    show_change_link = True


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = (
        "title",
        "category",
        "root",
    )
    fields = list_display
    search_fields = fields + ("id",)
    list_filter = ("category",)
    inlines = [ProductVariantsInline]
    show_facets = True


class ProductVariantImagesInline(TabularInline):
    model = ProductVariantImage
    fields = ("image_link",)
    extra = 1


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    list_display = (
        "product",
        "price",
        "color",
        "source_id",
    )
    fields = list_display
    search_fields = fields + ("id",)
    inlines = [ProductVariantImagesInline]
    actions = [
        "clear_source_ids",
    ]

    def clear_source_ids(self, request, queryset):
        ProductVariant.objects.filter(source_id=0).update(source_id=None)
        self.message_user(request, "Product variant source ids cleared")


class CommentFilesInline(TabularInline):
    model = CommentFiles
    fields = ("file_link",)
    extra = 1


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = (
        "user",
        "product",
        "content",
        "rating",
        "status",
    )
    fields = list_display + (
        "wb_user",
        "reply_to",
        "file",
        "source_id",
    )
    search_fields = fields + ("id",)
    list_filter = ("status",)
    inlines = [CommentFilesInline]
    actions = [
        "clear_source_ids",
    ]

    def clear_source_ids(self, request, queryset):
        Comment.objects.filter(source_id=0).update(source_id=None)
        self.message_user(request, "Comment source ids cleared")
