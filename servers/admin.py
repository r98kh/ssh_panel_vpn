from django.contrib import admin
from django.utils.html import format_html

from .models import Server


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = [
        "name", "ip_address", "ssh_port", "status_badge", "location",
        "user_count_display", "cpu_bar", "ram_bar", "disk_bar",
        "last_health_check",
    ]
    list_filter = ["status", "location"]
    search_fields = ["name", "ip_address", "location"]
    readonly_fields = [
        "cpu_usage", "ram_usage", "disk_usage",
        "uptime_seconds", "last_health_check", "created_at", "updated_at",
    ]
    fieldsets = (
        (None, {
            "fields": ("name", "ip_address", "ssh_port", "ssh_user", "ssh_key_path", "status", "location", "max_users"),
        }),
        ("Health (auto-updated)", {
            "classes": ("collapse",),
            "fields": ("cpu_usage", "ram_usage", "disk_usage", "uptime_seconds", "last_health_check"),
        }),
    )

    def status_badge(self, obj):
        colors = {
            "active": "#28a745",
            "maintenance": "#ffc107",
            "full": "#fd7e14",
            "down": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def user_count_display(self, obj):
        return f"{obj.current_user_count} / {obj.max_users}"
    user_count_display.short_description = "Users"

    def _progress_bar(self, value):
        if value > 80:
            color = "#dc3545"
        elif value > 60:
            color = "#ffc107"
        else:
            color = "#28a745"
        return format_html(
            '<div style="width:80px;background:#e9ecef;border-radius:4px;">'
            '<div style="width:{pct}%;background:{color};height:14px;'
            'border-radius:4px;text-align:center;color:#fff;font-size:10px;'
            'line-height:14px;">{pct}%</div></div>',
            pct=int(value), color=color,
        )

    def cpu_bar(self, obj):
        return self._progress_bar(obj.cpu_usage)
    cpu_bar.short_description = "CPU"

    def ram_bar(self, obj):
        return self._progress_bar(obj.ram_usage)
    ram_bar.short_description = "RAM"

    def disk_bar(self, obj):
        return self._progress_bar(obj.disk_usage)
    disk_bar.short_description = "Disk"
