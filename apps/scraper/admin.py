from django.contrib import admin
from django.db.models import ForeignKey
from django.http import HttpRequest
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    CommentStatuses,
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
    search_fields = (
        "id",
        "title",
        "root",
    )
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
        "accept_all",
        "not_accept_all",
        "update_file_links",
    ]

    def accept_all(self, request, queryset):
        queryset.update(status=CommentStatuses.ACCEPTED)
        self.message_user(request, "Selected comments accepted", level=25)

    def not_accept_all(self, request, queryset):
        queryset.update(status=CommentStatuses.NOT_ACCEPTED)
        self.message_user(request, "Selected comments not accepted", level=30)

    def update_file_links(self, request, queryset):
        for file in CommentFiles.objects.all():
            file.file_link = file.file_link[:17] + "1" + file.file_link[18:]
            file.save(update_fields=["file_link"])
        self.message_user(request, "done", level=25)
