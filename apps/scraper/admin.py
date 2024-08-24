from django.contrib import admin
from django.db.models import ForeignKey
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    CommentStatuses,
    Product,
    ProductVariant,
    ProductVariantImage,
    RequestedComment,
    RequestedCommentFile,
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


class RequestedCommentFilesInline(TabularInline):
    model = RequestedCommentFile
    fields = ("file_link",)
    fk_name = "requested_comment"
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

    @display(description=_("User"))
    def user_display(self, instance):
        name = "Anonymous"
        if instance.wb_user:
            name = instance.wb_user
        elif instance.user:
            name = instance.user.full_name
            if not name:
                name = instance.user.email
        return name if name is not None else "Anonymous"


@admin.register(RequestedComment)
class RequestedCommentAdmin(ModelAdmin):
    list_display = (
        "user_display",
        "product",
        "content",
        "rating",
        "status",
        "action_buttons",
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
    inlines = [RequestedCommentFilesInline]

    @display(description=_("User"))
    def user_display(self, instance):
        name = "Anonymous"
        if instance.wb_user:
            name = instance.wb_user
        elif instance.user:
            name = instance.user.full_name
            if not name:
                name = instance.user.email
        return name if name is not None else "Anonymous"

    def action_buttons(self, obj):
        accept_url = reverse("admin:accept_comment", args=[obj.pk])
        reject_url = reverse("admin:reject_comment", args=[obj.pk])

        return format_html(
            '<div style="display: flex; width: 100%;">'
            '<a class="inline-block border border-green-500 font-medium rounded-md text-center text-green-500 whitespace-nowrap dark:border-transparent dark:bg-green-500/20 dark:text-green-500" '
            'style="flex: 1; text-align: center; display: block; padding: 5px 10px; margin: 0 2px;" href="{}">Accept</a> '
            '<a class="inline-block border border-red-500 font-medium rounded-md text-center text-red-500 whitespace-nowrap dark:border-transparent dark:bg-red-500/20 dark:text-red-500" '
            'style="flex: 1; text-align: center; display: block; padding: 5px 10px; margin: 0 2px;" href="{}">Reject</a>'
            "</div>",
            accept_url,
            reject_url,
        )

    action_buttons.short_description = _("Actions")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "accept/<int:pk>/",
                self.admin_site.admin_view(self.accept_comment),
                name="accept_comment",
            ),
            path(
                "reject/<int:pk>/",
                self.admin_site.admin_view(self.reject_comment),
                name="reject_comment",
            ),
        ]
        return custom_urls + urls

    def accept_comment(self, request, pk):
        requested_comment = RequestedComment.objects.get(pk=pk)
        comment = requested_comment
        comment.status = CommentStatuses.ACCEPTED
        comment.save()
        requested_comment.delete()
        self.message_user(request, _("Comment accepted"), level=25)
        return HttpResponseRedirect(
            request.META.get(
                "HTTP_REFERER", reverse("admin:scraper_comment_changelist")
            )
        )

    def reject_comment(self, request, pk):
        requested_comment = RequestedComment.objects.get(pk=pk)
        comment = requested_comment
        comment.status = CommentStatuses.NOT_ACCEPTED
        comment.save()
        requested_comment.delete()
        self.message_user(request, _("Comment not accepted"), level=30)
        return HttpResponseRedirect(
            request.META.get(
                "HTTP_REFERER", reverse("admin:scraper_comment_changelist")
            )
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
