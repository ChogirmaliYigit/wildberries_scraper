from django.contrib import admin
from django.db.models import ForeignKey
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    CommentStatuses,
    Product,
    ProductVariant,
    ProductVariantImage,
)
from scraper.utils.notify import send_comment_notification
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display


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
        "source_id",
        "shard",
    )
    fields = (
        "title",
        "parent",
        "source_id",
    )
    search_fields = (
        "title",
        "source_id",
        "id",
    )
    list_filter = ("parent",)
    inlines = [ProductsInline]
    # actions = [
    #     "change_parent_128296",
    #     "change_parent_306",
    #     "change_parent_629",
    #     "change_parent_566",
    # ]

    def change_parent_128296(self, request, queryset):
        parent = Category.objects.filter(source_id=128296).first()
        queryset.update(parent=parent)
        self.message_user(request, "Categories made child of 128296", level=25)

    def change_parent_306(self, request, queryset):
        parent = Category.objects.filter(source_id=306).first()
        queryset.update(parent=parent)
        self.message_user(request, "Categories made child of 306", level=25)

    def change_parent_629(self, request, queryset):
        parent = Category.objects.filter(source_id=629).first()
        queryset.update(parent=parent)
        self.message_user(request, "Categories made child of 629", level=25)

    def change_parent_566(self, request, queryset):
        parent = Category.objects.filter(source_id=566).first()
        queryset.update(parent=parent)
        self.message_user(request, "Categories made child of 566", level=25)

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
    extra = 0
    show_change_link = True


class ProductCommentsInline(TabularInline):
    model = Comment
    fields = (
        "user",
        "content",
        "rating",
        "status",
    )
    show_change_link = True
    tab = True
    readonly_fields = ("user",)
    extra = 0

    def user(self, obj):
        if obj.user:
            display_name = obj.user.full_name or obj.user.email
        else:
            display_name = obj.wb_user
        return display_name

    user.short_description = _("User")


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = (
        "title",
        "category",
        "root",
        "likes",
    )
    fields = (
        "title",
        "category",
    )
    search_fields = (
        "id",
        "title",
        "root",
    )
    list_filter = ("category",)
    inlines = [ProductVariantsInline]
    # actions = ["delete_unused_products"]

    @display(description=_("Likes"))
    def likes(self, instance):
        return instance.product_likes.count()

    def delete_unused_products(self, request, queryset):
        queryset1 = Product.objects.filter(variants__images__isnull=True)
        count1 = queryset1.count()
        queryset2 = Product.objects.filter(product_comments__isnull=True)
        count2 = queryset2.count()
        queryset1.delete()
        queryset2.delete()
        self.message_user(
            request,
            f"{count1} + {count2} = {count1 + count2} products deleted",
            level=30,
        )


@admin.register(ProductVariantImage)
class ProductVariantImageAdmin(ModelAdmin):
    list_display = (
        "variant",
        "image_link",
    )
    fields = (
        "variant",
        "image_link",
    )


class CommentFilesInline(TabularInline):
    model = CommentFiles
    fields = ("file_link",)
    extra = 1


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = (
        "user_display",
        "product",
        "content",
        "rating",
        "status",
    )
    fields = (
        "user",
        "product",
        "content",
        "rating",
        "status",
        "wb_user",
        "reply_to",
        "file",
        "source_id",
    )
    search_fields = (
        "id",
        "user__full_name",
        "user__email",
        "wb_user",
        "content",
        "product__title",
        "product__category__title",
        "rating",
        "reply_to__content",
        "source_id",
    )
    list_filter = ("status",)
    inlines = [CommentFilesInline]
    actions = [
        "accept_all",
        "not_accept_all",
    ]

    @display(description=_("User"))
    def user_display(self, instance):
        name = "Anonymous"
        if instance.wb_user:
            name = instance.wb_user
        elif instance.user:
            name = instance.user.full_name
            if not name:
                name = instance.user.email
        return name

    def accept_all(self, request, queryset):
        queryset.update(status=CommentStatuses.ACCEPTED)
        self.message_user(request, _("Selected comments accepted"), level=25)

    def not_accept_all(self, request, queryset):
        queryset.update(status=CommentStatuses.NOT_ACCEPTED)
        for comment in list(queryset):
            send_comment_notification(comment)
        self.message_user(request, _("Selected comments not accepted"), level=30)

    accept_all.short_description = _("Accept selected comments")
    not_accept_all.short_description = _("Not accept selected comments")
