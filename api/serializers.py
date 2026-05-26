from rest_framework import serializers

from accounts.models import SSHAccount, ActiveSession, AuditLog
from plans.models import Plan
from servers.models import Server


class ServerSerializer(serializers.ModelSerializer):
    current_user_count = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = Server
        fields = [
            "id", "name", "ip_address", "ssh_port", "protocol_type",
            "status", "location",
            "max_users", "current_user_count", "is_available",
            "shadowlink_port", "shadowlink_ws_path", "shadowlink_domain",
            "cpu_usage", "ram_usage", "disk_usage", "uptime_seconds",
            "last_health_check", "created_at",
        ]
        read_only_fields = [
            "cpu_usage", "ram_usage", "disk_usage", "uptime_seconds",
            "last_health_check", "created_at",
        ]


class ServerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Server
        fields = [
            "id", "name", "ip_address", "ssh_port", "ssh_user",
            "ssh_key_path", "location", "max_users",
        ]


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


class SSHAccountSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source="server.name", read_only=True)
    server_ip = serializers.CharField(source="server.ip_address", read_only=True)
    server_ssh_port = serializers.IntegerField(source="server.ssh_port", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    days_remaining = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = SSHAccount
        fields = [
            "id", "username", "password_display", "server", "server_name",
            "server_ip", "server_ssh_port", "plan", "plan_name",
            "protocol_type", "status",
            "expire_date", "max_connections", "bandwidth_limit_gb",
            "bandwidth_used_gb", "days_remaining", "is_expired",
            "access_token", "auth_token", "note", "created_at",
        ]
        read_only_fields = [
            "password_display", "bandwidth_used_gb", "created_at",
            "access_token", "auth_token",
        ]


class PublicAccountStatusSerializer(serializers.ModelSerializer):
    """Read-only serializer for public user status page (no sensitive data)."""
    server_ip = serializers.CharField(source="server.ip_address", read_only=True)
    server_ssh_port = serializers.IntegerField(source="server.ssh_port", read_only=True)
    server_location = serializers.CharField(source="server.location", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    days_remaining = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = SSHAccount
        fields = [
            "username", "server_ip", "server_ssh_port", "server_location",
            "plan_name", "status", "expire_date", "max_connections",
            "bandwidth_limit_gb", "bandwidth_used_gb", "days_remaining",
            "is_expired", "created_at",
        ]


class CreateAccountSerializer(serializers.Serializer):
    username = serializers.RegexField(
        r"^[a-z_][a-z0-9_-]{2,31}$",
        help_text="Linux-compatible username (3-32 chars, lowercase).",
    )
    plan_id = serializers.IntegerField()
    server_id = serializers.IntegerField(required=False, help_text="Omit for auto-assign.")
    password = serializers.CharField(required=False, max_length=128)
    note = serializers.CharField(required=False, default="", allow_blank=True)
    duration_days = serializers.IntegerField(required=False, min_value=1, max_value=3650, help_text="Override plan duration.")
    bandwidth_limit_gb = serializers.IntegerField(required=False, min_value=0, help_text="Override plan bandwidth (0=unlimited).")
    max_connections = serializers.IntegerField(required=False, min_value=1, max_value=100, help_text="Override plan max connections.")


class AccountUpdateSerializer(serializers.Serializer):
    expire_date = serializers.DateTimeField(required=False)
    duration_days = serializers.IntegerField(required=False, min_value=1, max_value=3650, help_text="Set new duration from now.")
    bandwidth_limit_gb = serializers.IntegerField(required=False, min_value=0)
    max_connections = serializers.IntegerField(required=False, min_value=1, max_value=100)
    note = serializers.CharField(required=False, allow_blank=True)


class BulkCreateSerializer(serializers.Serializer):
    prefix = serializers.RegexField(r"^[a-z_][a-z0-9_-]{1,25}$")
    count = serializers.IntegerField(min_value=1, max_value=500)
    plan_id = serializers.IntegerField()
    server_id = serializers.IntegerField(required=False)


class ExtendAccountSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=365)


class ActiveSessionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="account.username", read_only=True)
    server_ip = serializers.CharField(source="account.server.ip_address", read_only=True)

    class Meta:
        model = ActiveSession
        fields = ["id", "username", "server_ip", "pid", "client_ip", "connected_since"]


class AuditLogSerializer(serializers.ModelSerializer):
    account_username = serializers.CharField(source="account.username", read_only=True, default=None)
    admin_username = serializers.CharField(source="admin_user.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "account", "account_username",
            "admin_user", "admin_username", "detail", "created_at",
        ]


class PaymentWebhookSerializer(serializers.Serializer):
    """Mock payment webhook payload."""
    order_id = serializers.CharField()
    username = serializers.CharField()
    plan_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.ChoiceField(choices=["paid", "failed", "pending"])
    signature = serializers.CharField()


class ShadowLinkAccountSerializer(serializers.ModelSerializer):
    """Serializer for ShadowLink-specific account info."""
    server_name = serializers.CharField(source="server.name", read_only=True)
    server_ip = serializers.CharField(source="server.ip_address", read_only=True)
    server_domain = serializers.CharField(source="server.shadowlink_domain", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    days_remaining = serializers.ReadOnlyField()

    class Meta:
        model = SSHAccount
        fields = [
            "id", "username", "server", "server_name", "server_ip",
            "server_domain", "plan", "plan_name", "protocol_type",
            "status", "expire_date", "max_connections",
            "bandwidth_limit_gb", "bandwidth_used_gb", "days_remaining",
            "auth_token", "access_token", "note", "created_at",
        ]
        read_only_fields = ["auth_token", "access_token", "bandwidth_used_gb", "created_at"]


class CreateShadowLinkAccountSerializer(serializers.Serializer):
    username = serializers.RegexField(
        r"^[a-z_][a-z0-9_-]{2,31}$",
        help_text="Account identifier (3-32 chars, lowercase).",
    )
    plan_id = serializers.IntegerField()
    server_id = serializers.IntegerField(required=False, help_text="Omit for auto-assign.")
    note = serializers.CharField(required=False, default="", allow_blank=True)
    duration_days = serializers.IntegerField(required=False, min_value=1, max_value=3650)
    max_connections = serializers.IntegerField(required=False, min_value=1, max_value=100)


class ShadowLinkServerStatusSerializer(serializers.Serializer):
    running = serializers.BooleanField()
    pid = serializers.IntegerField()
    status = serializers.CharField()


class ShadowLinkClientConfigSerializer(serializers.Serializer):
    """Read-only serializer for generated client config."""
    client = serializers.DictField()
    cdn = serializers.DictField()
    obfuscation = serializers.DictField()
