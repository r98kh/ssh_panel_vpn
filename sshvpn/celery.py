import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sshvpn.settings")

app = Celery("sshvpn")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "expire-users-every-5-min": {
        "task": "accounts.tasks.expire_users",
        "schedule": crontab(minute="*/5"),
    },
    "cleanup-deleted-accounts-daily": {
        "task": "accounts.tasks.cleanup_expired_accounts",
        "schedule": crontab(hour=3, minute=0),
    },
    "server-health-check-every-minute": {
        "task": "servers.tasks.check_all_servers_health",
        "schedule": crontab(minute="*"),
    },
    "sync-active-sessions-every-30-sec": {
        "task": "accounts.tasks.sync_active_sessions",
        "schedule": 30.0,
    },
}
