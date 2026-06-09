from django.contrib import admin
from .models import Company, User, Role  # Import your custom User model and Role model
from ..kyc.models import Flow, Filing


class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "created_at",
        "is_active",
    )
    search_fields = ("id", "name")
    list_filter = ("is_active",)
    ordering = ("id",)


admin.site.register(Company, CompanyAdmin)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at", "is_active")
    search_fields = ("name",)
    ordering = ("id",)


class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "phone",
        "email",
        "uid",
        "company",
        "total_credits",  # Display total credits
        "used_credits",  # Display used credits
        "available_credits",  # Display available credits
        "no_of_flows",  # Display number of flows
        "no_of_filings",  # Display number of filings
        "created_at",
        "is_active",
    )
    search_fields = ("id", "first_name", "email")
    list_filter = ("is_active",)
    ordering = ("id",)
    filter_horizontal = ("roles",)  # Add this to allow editing roles in admin

    # Access total credits directly
    def total_credits(self, obj):
        return getattr(obj.credits, "total", 0)

    total_credits.short_description = "Total Credits"

    # Access used credits directly
    def used_credits(self, obj):
        return getattr(obj.credits, "used", 0)

    used_credits.short_description = "Used Credits"

    # Access available credits directly
    def available_credits(self, obj):
        return getattr(obj.credits, "available", 0)

    available_credits.short_description = "Available Credits"

    # Count the number of flows
    def no_of_flows(self, obj):
        return Flow.objects.filter(user=obj).count()

    no_of_flows.short_description = "No. of Flows"

    # Count the number of filings
    def no_of_filings(self, obj):
        return Filing.objects.filter(kyc_flow__user=obj).count()

    no_of_filings.short_description = "No. of Filings"


admin.site.register(User, UserAdmin)  # Register the custom User model
