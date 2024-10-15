from django.contrib import admin
from django.db import transaction
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
    RequestedComment,
    RequestedCommentFile,
)
from scraper.utils.queryset import get_comments, get_products
from unfold.admin import ModelAdmin, StackedInline
from unfold.decorators import display


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
    list_filter = ("parent",)

    def has_view_or_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return False

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
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
        "source_id",
        "image_link",
        "created_at",
    )
    readonly_fields = ("created_at",)
    search_fields = (
        "id",
        "title",
        "root",
        "image_link",
    )
    list_filter = ("category",)
    autocomplete_fields = ["category"]

    def get_queryset(self, request):
        return get_products()

    @display(description=_("Likes"))
    def likes(self, instance):
        return instance.product_likes.count()

    def delete_queryset(self, request, queryset):
        try:
            with transaction.atomic():
                queryset.delete()
        except Exception as e:
            transaction.set_rollback(True)
            raise e


class CommentFilesInline(StackedInline):
    model = CommentFiles
    fields = ("file_link",)
    readonly_fields = fields
    extra = 0


class RequestedCommentFilesInline(StackedInline):
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
        return get_comments(comment=True, product__isnull=False)


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

        def get_button(color, text, action) -> str:
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
                    text=_("Accept"),
                    action=f"window.location.href='{accept_url}'",
                )
                + get_button(
                    color="red",
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
        requested_comment = RequestedComment.objects.get(pk=pk)

        # Fetch the associated Comment and update its status
        comment = Comment.objects.filter(id=requested_comment.comment_id).first()
        if comment:
            comment.status = CommentStatuses.ACCEPTED
            comment.save(update_fields=["status"])

        requested_comment.delete()

        self.message_user(request, _("Comment accepted"))
        return HttpResponseRedirect(
            reverse("admin:scraper_requestedcomment_changelist")
        )

    def reject_comment(self, request, pk):
        requested_comment = RequestedComment.objects.get(pk=pk)
        comment = Comment.objects.filter(id=requested_comment.comment_id).first()
        if comment:
            comment.status = CommentStatuses.NOT_ACCEPTED
            comment.reason = request.POST.get("reason", "")
            comment.save(update_fields=["status"])

        requested_comment.delete()

        self.message_user(request, _("Comment rejected"))
        return HttpResponseRedirect(
            reverse("admin:scraper_requestedcomment_changelist")
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    def has_view_permission(self, request, obj=None):
        return True
