from django.contrib import admin

from .models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        "name", "duration_days", "price", "currency",
        "max_connections", "bandwidth_limit_gb", "is_active",
    ]
    list_filter = ["is_active", "currency"]
    search_fields = ["name"]
    list_editable = ["price", "is_active"]
