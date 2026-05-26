"""
Celery tasks for automated account lifecycle management.
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="accounts.tasks.expire_users")
def expire_users():
    """Mark expired accounts and lock them on the remote server."""
    from accounts.models import SSHAccount
    from servers.ssh import get_ssh_manager

    now = timezone.now()
    accounts = SSHAccount.objects.filter(
        status=SSHAccount.Status.ACTIVE,
        expire_date__lte=now,
    ).select_related("server")

    count = 0
    for acc in accounts:
        try:
            with get_ssh_manager(acc.server) as ssh:
                ssh.lock_user(acc.username)
            acc.status = SSHAccount.Status.EXPIRED
            acc.save(update_fields=["status", "updated_at"])
            count += 1
        except Exception:
            logger.exception("Failed to expire %s", acc)
    logger.info("Expired %d accounts", count)
    return count


@shared_task(name="accounts.tasks.cleanup_expired_accounts")
def cleanup_expired_accounts(grace_days: int = 3):
    """Delete accounts that have been expired for longer than grace_days."""
    from datetime import timedelta
    from accounts.models import SSHAccount
    from accounts.services import delete_account

    cutoff = timezone.now() - timedelta(days=grace_days)
    accounts = SSHAccount.objects.filter(
        status=SSHAccount.Status.EXPIRED,
        expire_date__lte=cutoff,
    ).select_related("server")

    count = 0
    for acc in accounts:
        try:
            delete_account(acc)
            count += 1
        except Exception:
            logger.exception("Failed to cleanup %s", acc)
    logger.info("Cleaned up %d expired accounts", count)
    return count


@shared_task(name="accounts.tasks.sync_bandwidth_usage")
def sync_bandwidth_usage():
    """Read bandwidth counters from iptables and update accounts."""
    from accounts.models import SSHAccount
    from servers.models import Server
    from servers.ssh import get_ssh_manager

    servers = Server.objects.filter(status=Server.Status.ACTIVE)
    for srv in servers:
        try:
            accounts = SSHAccount.objects.filter(
                server=srv,
                status=SSHAccount.Status.ACTIVE,
                bandwidth_limit_gb__gt=0,
            )
            if not accounts.exists():
                continue
            with get_ssh_manager(srv) as ssh:
                for acc in accounts:
                    bytes_used = ssh.get_user_bandwidth_bytes(acc.username)
                    gb_used = round(bytes_used / (1024 ** 3), 3)
                    if gb_used != acc.bandwidth_used_gb:
                        acc.bandwidth_used_gb = gb_used
                        acc.save(update_fields=["bandwidth_used_gb", "updated_at"])
                    if acc.bandwidth_limit_gb > 0 and gb_used >= acc.bandwidth_limit_gb:
                        ssh.lock_user(acc.username)
                        acc.status = SSHAccount.Status.SUSPENDED
                        acc.save(update_fields=["status", "updated_at"])
                        logger.info("User %s suspended: bandwidth limit exceeded (%.2f/%.0f GB)",
                                    acc.username, gb_used, acc.bandwidth_limit_gb)
        except Exception:
            logger.exception("Bandwidth sync failed for %s", srv)


@shared_task(name="accounts.tasks.sync_active_sessions")
def sync_active_sessions():
    """Fetch active SSH sessions from every server, store in DB, and enforce limits."""
    from accounts.models import SSHAccount, ActiveSession
    from servers.models import Server
    from servers.ssh import get_ssh_manager

    servers = Server.objects.filter(status=Server.Status.ACTIVE)
    for srv in servers:
        try:
            with get_ssh_manager(srv) as ssh:
                sessions = ssh.get_active_sessions()
                usernames = {s["user"] for s in sessions}
                accounts = SSHAccount.objects.filter(
                    server=srv,
                    username__in=usernames,
                    status=SSHAccount.Status.ACTIVE,
                )
                acc_map = {a.username: a for a in accounts}

                ActiveSession.objects.filter(account__server=srv).delete()

                user_sessions: dict[str, list[dict]] = {}
                for sess in sessions:
                    acc = acc_map.get(sess["user"])
                    if acc:
                        ActiveSession.objects.create(
                            account=acc,
                            pid=sess["pid"],
                            client_ip=sess.get("client_ip"),
                        )
                        user_sessions.setdefault(sess["user"], []).append(sess)

                for username, sess_list in user_sessions.items():
                    acc = acc_map.get(username)
                    if acc and len(sess_list) > acc.max_connections:
                        excess = sorted(sess_list, key=lambda s: s["pid"])[acc.max_connections:]
                        pids = [str(s["pid"]) for s in excess]
                        ssh.run(f"kill -9 {' '.join(pids)}")
                        logger.info(
                            "Killed %d excess sessions for %s (limit=%d, had=%d)",
                            len(pids), username, acc.max_connections, len(sess_list),
                        )
        except Exception:
            logger.exception("Session sync failed for %s", srv)
