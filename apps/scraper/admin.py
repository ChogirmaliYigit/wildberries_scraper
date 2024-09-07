from django.contrib import admin
from django.db.models import Exists, ForeignKey, OuterRef
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


class HasCommentsFilter(admin.SimpleListFilter):
    title = _("Comments")
    parameter_name = "has_comments"

    def lookups(self, request, model_admin):
        return [
            ("yes", _("Have comment")),
            ("no", _("Have no comment")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.annotate(
                has_comments=Exists(Comment.objects.filter(product=OuterRef("pk")))
            ).filter(has_comments=True)
        elif self.value() == "no":
            return queryset.annotate(
                has_comments=Exists(Comment.objects.filter(product=OuterRef("pk")))
            ).filter(has_comments=False)
        return queryset


class HasImagesInVariantsFilter(admin.SimpleListFilter):
    title = _("Images in Variants")
    parameter_name = "has_images_in_variants"

    def lookups(self, request, model_admin):
        return [
            ("yes", _("Have image")),
            ("no", _("Have no image")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.annotate(
                has_images=Exists(
                    ProductVariantImage.objects.filter(variant__product=OuterRef("pk"))
                )
            ).filter(has_images=True)
        elif self.value() == "no":
            return queryset.annotate(
                has_images=Exists(
                    ProductVariantImage.objects.filter(variant__product=OuterRef("pk"))
                )
            ).filter(has_images=False)
        return queryset


class HasCommentsAndImagesFilter(admin.SimpleListFilter):
    title = _("Comments and Images in Variants")
    parameter_name = "has_comments_and_images"

    def lookups(self, request, model_admin):
        return [
            ("yes", _("Have comment and image")),
            ("no", _("Have no comments and no images")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.annotate(
                has_comments=Exists(Comment.objects.filter(product=OuterRef("pk"))),
                has_images=Exists(
                    ProductVariantImage.objects.filter(variant__product=OuterRef("pk"))
                ),
            ).filter(has_comments=True, has_images=True)
        elif self.value() == "no":
            return queryset.annotate(
                has_comments=Exists(Comment.objects.filter(product=OuterRef("pk"))),
                has_images=Exists(
                    ProductVariantImage.objects.filter(variant__product=OuterRef("pk"))
                ),
            ).filter(has_comments=False, has_images=False)
        return queryset


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
        "slug_name",
        "shard",
        "position",
    )
    search_fields = (
        "title",
        "source_id",
        "id",
        "shard",
        "slug_name",
    )
    list_filter = ("parent",)
    inlines = [ProductsInline]
    autocomplete_fields = ["parent"]

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
    list_filter = (
        "category",
        HasCommentsFilter,
        HasImagesInVariantsFilter,
        HasCommentsAndImagesFilter,
    )
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


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    list_display = (
        "product",
        "color",
        "price",
        "source_id",
    )
    fields = list_display
    autocomplete_fields = ("product",)
    search_fields = ("product__title",)


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
    autocomplete_fields = ("variant",)


class CommentFilesInline(TabularInline):
    model = CommentFiles
    fields = ("file_link",)
    extra = 1


class RequestedCommentFilesInline(TabularInline):
    model = RequestedCommentFile
    fields = ("file_link",)
    fk_name = "requested_comment"
    extra = 1


class BaseCommentAdmin(ModelAdmin):
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

    def get_queryset(self, request):
        # Filter out instances of RequestedComment
        queryset = super().get_queryset(request)
        return queryset.filter(requestedcomment__isnull=True)


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

        def get_button(color, url, text) -> str:
            button_template = (
                '<a class="inline-block border border-{color}-500 font-medium rounded-md text-center text-{'
                "color}-500 whitespace-nowrap dark:border-transparent dark:bg-{color}-500/20 "
                'dark:text-{color}-500" style="flex: 1; text-align: center; display: block; padding: 5px '
                '10px; margin: 0 2px;" href="{url}">{text}</a>'
            )

            return button_template.format(color=color, url=url, text=text)

        return format_html(
            button_div.format(
                content=get_button(color="green", url=accept_url, text=_("Accept"))
                + get_button(color="red", url=reject_url, text=_("Reject"))
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
        return self.update_comment(request, pk, CommentStatuses.NOT_ACCEPTED)

    def update_comment(self, request, pk: int, status: CommentStatuses):
        requested_comment = RequestedComment.objects.get(pk=pk)
        comment = Comment.objects.get(pk=requested_comment.pk - 1)
        comment.status = status
        comment.save(update_fields=["status"])
        requested_comment.delete()

        msg = _("Comment not accepted")
        level = 30
        if status == CommentStatuses.ACCEPTED:
            msg = _("Comment accepted")
            level = 25
        self.message_user(request, msg, level=level)

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
        return True

    def has_view_permission(self, request, obj=None):
        return True
