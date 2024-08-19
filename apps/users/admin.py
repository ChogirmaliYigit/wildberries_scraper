from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from users.models import Token, User


@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = (
        "email",
        "full_name",
        "is_blocked_display",
    )
    list_filter = ("is_blocked",)
    filter_horizontal = (
        "groups",
        "user_permissions",
    )
    search_fields = (
        "full_name",
        "email",
        "id",
    )
    actions = ["block_users", "unblock_users"]

    def block_users(self, request, queryset):
        queryset.update(is_blocked=True)
        self.message_user(request, _("Selected users are blocked"), level=30)

    block_users.short_description = _("Block selected users")

    def unblock_users(self, request, queryset):
        queryset.update(is_blocked=False)
        self.message_user(request, _("Selected users are unblocked"), level=25)

    unblock_users.short_description = _("Unblock selected users")

    def is_blocked_display(self, obj):
        return _("Yes") if obj.is_blocked else _("No")

    is_blocked_display.short_description = _("Is blocked")

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (
                _("User"),
                {
                    "fields": (
                        "full_name",
                        "email",
                        "profile_photo",
                        "is_blocked",
                    ),
                    "classes": ["tab"],
                },
            ),
        ]

        if request.user.is_superuser:
            fieldsets.append(
                (
                    "Permissions",
                    {
                        "fields": (
                            "is_staff",
                            "is_superuser",
                            "groups",
                            "user_permissions",
                        ),
                        "classes": ["tab"],
                    },
                )
            )

        return fieldsets


@admin.register(Token)
class TokenAdmin(ModelAdmin):
    list_display = (
        "user",
        "key",
        "is_active",
        "expires_at",
    )
    fields = list_display
    search_fields = ("id", "key", "user__full_name", "user__email")
    list_filter = ("is_active",)
