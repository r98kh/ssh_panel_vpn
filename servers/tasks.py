"""
Celery tasks for server health monitoring and rebalancing.
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="servers.tasks.check_all_servers_health")
def check_all_servers_health():
    from servers.models import Server
    from servers.ssh import get_ssh_manager

    servers = Server.objects.exclude(status=Server.Status.DOWN)
    for srv in servers:
        try:
            with get_ssh_manager(srv) as ssh:
                health = ssh.get_health()
            srv.cpu_usage = health["cpu_usage"]
            srv.ram_usage = health["ram_usage"]
            srv.disk_usage = health["disk_usage"]
            srv.uptime_seconds = health["uptime_seconds"]
            srv.last_health_check = timezone.now()
            if srv.status == Server.Status.ACTIVE and srv.cpu_usage > 95:
                srv.status = Server.Status.FULL
            srv.save()
        except Exception:
            logger.exception("Health check failed for %s", srv)
            srv.status = Server.Status.DOWN
            srv.last_health_check = timezone.now()
            srv.save(update_fields=["status", "last_health_check"])


@shared_task(name="servers.tasks.check_single_server")
def check_single_server(server_id: int):
    from servers.models import Server
    from servers.ssh import get_ssh_manager

    srv = Server.objects.get(pk=server_id)
    try:
        with get_ssh_manager(srv) as ssh:
            health = ssh.get_health()
        srv.cpu_usage = health["cpu_usage"]
        srv.ram_usage = health["ram_usage"]
        srv.disk_usage = health["disk_usage"]
        srv.uptime_seconds = health["uptime_seconds"]
        srv.last_health_check = timezone.now()
        if srv.status == Server.Status.DOWN:
            srv.status = Server.Status.ACTIVE
        srv.save()
        return True
    except Exception:
        logger.exception("Health check failed for %s", srv)
        srv.status = Server.Status.DOWN
        srv.last_health_check = timezone.now()
        srv.save(update_fields=["status", "last_health_check"])
        return False


@shared_task(name="servers.tasks.rebalance_users")
def rebalance_users(down_server_id: int):
    """Move users from a downed server to available ones."""
    from accounts.models import SSHAccount, AuditLog
    from accounts.services import pick_best_server
    from servers.models import Server
    from servers.ssh import get_ssh_manager

    down_srv = Server.objects.get(pk=down_server_id)
    accounts = SSHAccount.objects.filter(
        server=down_srv,
        status=SSHAccount.Status.ACTIVE,
    )

    moved = 0
    for acc in accounts:
        try:
            target = pick_best_server()
            with get_ssh_manager(target) as ssh:
                ssh.create_user(acc.username, generate_temp_password())
                ssh.set_expiry(acc.username, acc.expire_date.strftime("%Y-%m-%d"))
                ssh.set_max_logins(acc.username, acc.max_connections)
            acc.server = target
            acc.save(update_fields=["server", "updated_at"])
            AuditLog.objects.create(
                action=AuditLog.Action.REBALANCE,
                account=acc,
                detail=f"Moved from {down_srv.name} to {target.name}",
            )
            moved += 1
        except Exception:
            logger.exception("Rebalance failed for %s", acc)

    logger.info("Rebalanced %d/%d users from %s", moved, accounts.count(), down_srv)
    return moved


def generate_temp_password() -> str:
    from accounts.models import generate_password
    return generate_password()
