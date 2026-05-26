from django.core.management.base import BaseCommand

from plans.models import Plan


class Command(BaseCommand):
    help = "Seed default subscription plans."

    def handle(self, *args, **options):
        defaults = [
            {"name": "Trial", "duration_days": 1, "price": 0.50, "max_connections": 1, "bandwidth_limit_gb": 5},
            {"name": "Weekly", "duration_days": 7, "price": 2.00, "max_connections": 2, "bandwidth_limit_gb": 50},
            {"name": "Monthly", "duration_days": 30, "price": 5.00, "max_connections": 2, "bandwidth_limit_gb": 0},
            {"name": "Quarterly", "duration_days": 90, "price": 12.00, "max_connections": 3, "bandwidth_limit_gb": 0},
        ]
        for d in defaults:
            plan, created = Plan.objects.get_or_create(name=d["name"], defaults=d)
            status = "created" if created else "exists"
            self.stdout.write(f"  {status}: {plan}")
        self.stdout.write(self.style.SUCCESS("Done."))
