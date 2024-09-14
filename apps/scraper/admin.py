from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from scraper.admin_filters import ReplyToFilter
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    CommentStatuses,
    Product,
    ProductVariant,
    RequestedComment,
    RequestedCommentFile,
)
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display


class ProductVariantsInline(TabularInline):
    model = ProductVariant
    fields = (
        "color",
        "price",
        "source_id",
    )
    readonly_fields = fields
    extra = 0
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = (
        "title",
        "parent",
        "source_id",
        "shard",
    )
    search_fields = (
        "title",
        "source_id",
        "id",
        "shard",
        "slug_name",
    )

    def has_view_or_change_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return False


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
    autocomplete_fields = ["category"]

    @display(description=_("Likes"))
    def likes(self, instance):
        return instance.product_likes.count()

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.is_superuser:
            actions["delete_unused_products"] = (
                self.delete_unused_products,
                "delete_unused_products",
                "Delete unused products",
            )
        return actions

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


class CommentFilesInline(TabularInline):
    model = CommentFiles
    fields = ("file_link",)
    readonly_fields = fields
    extra = 0


class RequestedCommentFilesInline(TabularInline):
    model = RequestedCommentFile
    fields = ("file_link",)
    readonly_fields = fields
    fk_name = "requested_comment"
    extra = 0


class BaseCommentAdmin(ModelAdmin):
    list_display = (
        "user_display",
        "product",
        "content",
        "rating",
        "promo",
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
        "reason",
        "promo",
    )
    readonly_fields = fields
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
        "reason",
    )
    list_filter = (
        "status",
        "promo",
    )
    autocomplete_fields = [
        "user",
        "product",
        "reply_to",
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
        return name if name is not None else "Anonymous"


@admin.register(Comment)
class CommentAdmin(BaseCommentAdmin):
    inlines = [CommentFilesInline]
    actions = (
        "promo_comment",
        "not_promo_comment",
    )

    def get_list_filter(self, request):
        return super().get_list_filter(request) + (ReplyToFilter,)

    @display(description=_("Promo selected comments"))
    def promo_comment(self, request, queryset):
        queryset.update(promo=True)
        self.message_user(request, _("Selected comments promoted"))

    @display(description=_("Not promo selected comments"))
    def not_promo_comment(self, request, queryset):
        queryset.update(promo=False)
        self.message_user(request, _("Selected comments not promoted"))

    def get_queryset(self, request):
        # Filter out instances of RequestedComment
        queryset = super().get_queryset(request)
        queryset = queryset.filter(requestedcomment__isnull=True)
        return queryset.filter(status=CommentStatuses.ACCEPTED)


@admin.register(RequestedComment)
class RequestedCommentAdmin(BaseCommentAdmin):
    inlines = [RequestedCommentFilesInline]

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        return list_display + ("action_buttons",)

    @display(description=_("Actions"))
    def action_buttons(self, obj):
        accept_url = reverse("admin:accept_comment", args=[obj.pk])
        reject_url = reverse("admin:reject_comment", args=[obj.pk])
        button_div = '<div style="display: flex; width: 100%;">{content}</div>'

        def get_button(color, url, text, action=None) -> str:
            button_template = (
                '<a class="inline-block border border-{color}-500 font-medium rounded-md text-center text-{'
                "color}-500 whitespace-nowrap dark:border-transparent dark:bg-{color}-500/20 "
                'dark:text-{color}-500" style="flex: 1; text-align: center; display: block; padding: 5px '
                '10px; margin: 0 2px;" href="#" onclick="{action}">{text}</a>'
            )

            return button_template.format(color=color, action=action, text=text)

        return format_html(
            button_div.format(
                content=get_button(
                    color="green",
                    url=accept_url,
                    text=_("Accept"),
                    action=f"window.location.href='{accept_url}'",
                )
                + get_button(
                    color="red",
                    url=reject_url,
                    text=_("Reject"),
                    action=f"showRejectModal({obj.pk}, '{reject_url}')",
                )
            )
        )

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
        return self.update_comment(request, pk, CommentStatuses.ACCEPTED)

    def reject_comment(self, request, pk):
        print(request.POST)
        reason = request.POST.get("reason", "")
        return self.update_comment(request, pk, CommentStatuses.NOT_ACCEPTED, reason)

    def update_comment(self, request, pk: int, status: CommentStatuses, reason=""):
        requested_comment = RequestedComment.objects.get(pk=pk)
        comment = Comment.objects.get(pk=requested_comment.pk - 1)
        comment.status = status
        comment.reason = reason
        comment.save(update_fields=["status"])
        requested_comment.delete()

        msg = (
            _("Comment not accepted")
            if status == CommentStatuses.NOT_ACCEPTED
            else _("Comment accepted")
        )
        self.message_user(request, msg)
        return HttpResponseRedirect(reverse("admin:scraper_comment_changelist"))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    def has_view_permission(self, request, obj=None):
        return True
