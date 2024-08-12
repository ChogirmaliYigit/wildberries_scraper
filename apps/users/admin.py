from django.contrib import admin
from unfold.admin import ModelAdmin
from users.models import Token, User


@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = (
        "email",
        "full_name",
        "is_blocked",
    )
    list_filter = ("is_blocked",)
    fieldsets = (
        (
            "Main",
            {
                "fields": (
                    "full_name",
                    "email",
                    "profile_photo",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_blocked",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )
    filter_horizontal = (
        "groups",
        "user_permissions",
    )
    search_fields = (
        "full_name",
        "email",
        "id",
    )

    list_filter_submit = True


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
