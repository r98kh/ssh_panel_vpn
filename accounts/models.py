import secrets
import string
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class SSHAccount(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        EXPIRED = "expired", "Expired"
        DELETED = "deleted", "Deleted"

    username = models.CharField(max_length=32)
    password_display = models.CharField(
        max_length=128,
        blank=True,
        help_text="Shown once at creation, then cleared.",
    )
    server = models.ForeignKey(
        "servers.Server",
        on_delete=models.PROTECT,
        related_name="ssh_accounts",
    )
    plan = models.ForeignKey(
        "plans.Plan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounts",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    expire_date = models.DateTimeField()
    max_connections = models.PositiveIntegerField(default=1)
    bandwidth_limit_gb = models.PositiveIntegerField(default=0)
    bandwidth_used_gb = models.FloatField(default=0)

    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_accounts",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("username", "server")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username}@{self.server.ip_address}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expire_date

    @property
    def days_remaining(self):
        delta = self.expire_date - timezone.now()
        return max(0, delta.days)

    def extend(self, days: int):
        base = max(self.expire_date, timezone.now())
        self.expire_date = base + timedelta(days=days)
        self.status = self.Status.ACTIVE
        self.save(update_fields=["expire_date", "status", "updated_at"])


class ActiveSession(models.Model):
    """Tracks currently connected SSH sessions (synced periodically)."""

    account = models.ForeignKey(SSHAccount, on_delete=models.CASCADE, related_name="sessions")
    pid = models.IntegerField()
    client_ip = models.GenericIPAddressField(blank=True, null=True)
    connected_since = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("account", "pid")

    def __str__(self):
        return f"{self.account.username} pid={self.pid}"


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Create"
        DELETE = "delete", "Delete"
        SUSPEND = "suspend", "Suspend"
        ACTIVATE = "activate", "Activate"
        EXTEND = "extend", "Extend"
        EXPIRE = "expire", "Expire"
        PASSWORD_RESET = "password_reset", "Password Reset"
        REBALANCE = "rebalance", "Rebalance"

    action = models.CharField(max_length=20, choices=Action.choices)
    account = models.ForeignKey(
        SSHAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.action} – {self.account}"
