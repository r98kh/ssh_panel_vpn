from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Server(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        MAINTENANCE = "maintenance", "Maintenance"
        FULL = "full", "Full"
        DOWN = "down", "Down"

    name = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField(unique=True)
    ssh_port = models.PositiveIntegerField(
        default=22,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
    )
    ssh_user = models.CharField(max_length=64, default="root")
    ssh_key_path = models.CharField(
        max_length=500,
        help_text="Absolute path to private key on the panel server.",
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE)
    location = models.CharField(max_length=120, blank=True, help_text="e.g. Frankfurt, DE")
    max_users = models.PositiveIntegerField(default=100)

    # Health snapshot (updated by Celery beat)
    cpu_usage = models.FloatField(default=0, help_text="Percentage")
    ram_usage = models.FloatField(default=0, help_text="Percentage")
    disk_usage = models.FloatField(default=0, help_text="Percentage")
    uptime_seconds = models.BigIntegerField(default=0)
    last_health_check = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

    @property
    def current_user_count(self):
        return self.ssh_accounts.exclude(status="deleted").count()

    @property
    def is_available(self):
        return self.status == self.Status.ACTIVE and self.current_user_count < self.max_users
