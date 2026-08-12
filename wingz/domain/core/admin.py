from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from wingz.domain.core.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for the custom user.

    Subclasses Django's UserAdmin rather than using a plain ModelAdmin so that
    passwords go through the hashed change form instead of being editable as raw
    text in a normal field.
    """

    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name", "phone_number")
    readonly_fields = ("last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name", "phone_number")}),
        (
            "Role and permissions",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )
