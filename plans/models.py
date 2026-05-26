from django.db import models
from django.core.validators import MinValueValidator


class Plan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    duration_days = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Subscription length in days.",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=5, default="USD")
    max_connections = models.PositiveIntegerField(
        default=1,
        help_text="Max concurrent SSH sessions per user.",
    )
    bandwidth_limit_gb = models.PositiveIntegerField(
        default=0,
        help_text="0 = unlimited.",
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["duration_days", "price"]

    def __str__(self):
        return f"{self.name} – {self.duration_days}d – {self.price} {self.currency}"
