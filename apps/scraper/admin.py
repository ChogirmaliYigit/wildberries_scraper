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
)
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

    @display(description=_("Likes"))
    def likes(self, instance):
        return instance.product_likes.count()


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
    ]

    @display(description=_("User"))
    def user_display(self, instance):
        name = instance.wb_user
        if not name and instance.user:
            name = instance.user.full_name
            if not name:
                name = instance.user.email
        else:
            name = "Anonymous"
        return name

    def accept_all(self, request, queryset):
        queryset.update(status=CommentStatuses.ACCEPTED)
        self.message_user(request, _("Selected comments accepted"), level=25)

    def not_accept_all(self, request, queryset):
        queryset.update(status=CommentStatuses.NOT_ACCEPTED)
        self.message_user(request, _("Selected comments not accepted"), level=30)

    accept_all.short_description = _("Accept selected comments")
    not_accept_all.short_description = _("Not accept selected comments")
