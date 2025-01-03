from django.contrib import admin
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy as _
from scraper.models import Comment


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


class ReplyToFilter(admin.SimpleListFilter):
    title = _("Reply to")  # Display name for the filter
    parameter_name = "reply_to"  # URL parameter for the filter

    def lookups(self, request, model_admin):
        return (
            ("null", _("Feedbacks")),
            ("not_null", _("Comment")),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "null":
            return queryset.filter(reply_to__isnull=True)
        elif value == "not_null":
            return queryset.filter(reply_to__isnull=False)
        return queryset
