from django.contrib import admin
from django.utils.html import format_html
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import SSHAccount, ActiveSession, AuditLog


class SSHAccountResource(resources.ModelResource):
    class Meta:
        model = SSHAccount
        fields = (
            "id", "username", "server__ip_address", "plan__name",
            "status", "expire_date", "max_connections", "created_at",
        )
        export_order = fields


@admin.register(SSHAccount)
class SSHAccountAdmin(ImportExportModelAdmin):
    resource_class = SSHAccountResource
    list_display = [
        "username", "server_link", "status_badge", "plan",
        "expire_date", "days_remaining", "max_connections", "created_at",
    ]
    list_filter = ["status", "server", "plan", "created_at"]
    search_fields = ["username", "note", "server__ip_address"]
    readonly_fields = ["password_display", "bandwidth_used_gb", "created_at", "updated_at"]
    list_per_page = 50
    actions = ["action_suspend", "action_activate", "action_delete_accounts"]
    raw_id_fields = ["server", "plan", "created_by"]

    def server_link(self, obj):
        return format_html(
            '<a href="/admin/servers/server/{}/change/">{}</a>',
            obj.server_id, obj.server
        )
    server_link.short_description = "Server"

    def status_badge(self, obj):
        colors = {
            "active": "#28a745",
            "suspended": "#ffc107",
            "expired": "#dc3545",
            "deleted": "#6c757d",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Status"

    @admin.action(description="Suspend selected accounts")
    def action_suspend(self, request, queryset):
        from .services import suspend_account
        count = 0
        for acc in queryset.filter(status=SSHAccount.Status.ACTIVE):
            try:
                suspend_account(acc, admin_user=request.user)
                count += 1
            except Exception:
                pass
        self.message_user(request, f"Suspended {count} accounts.")

    @admin.action(description="Activate selected accounts")
    def action_activate(self, request, queryset):
        from .services import activate_account
        count = 0
        for acc in queryset.filter(status=SSHAccount.Status.SUSPENDED):
            try:
                activate_account(acc, admin_user=request.user)
                count += 1
            except Exception:
                pass
        self.message_user(request, f"Activated {count} accounts.")

    @admin.action(description="Delete selected accounts (remote)")
    def action_delete_accounts(self, request, queryset):
        from .services import delete_account
        count = 0
        for acc in queryset.exclude(status=SSHAccount.Status.DELETED):
            try:
                delete_account(acc, admin_user=request.user)
                count += 1
            except Exception:
                pass
        self.message_user(request, f"Deleted {count} accounts.")


@admin.register(ActiveSession)
class ActiveSessionAdmin(admin.ModelAdmin):
    list_display = ["account", "pid", "client_ip", "connected_since"]
    list_filter = ["account__server"]
    search_fields = ["account__username", "client_ip"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "account", "admin_user", "short_detail"]
    list_filter = ["action", "created_at"]
    search_fields = ["detail", "account__username"]
    readonly_fields = ["action", "account", "admin_user", "detail", "created_at"]

    def short_detail(self, obj):
        return obj.detail[:80] if obj.detail else "—"
    short_detail.short_description = "Detail"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
