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


@shared_task(name="accounts.tasks.sync_active_sessions")
def sync_active_sessions():
    """Fetch active SSH sessions from every server and store in DB."""
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
            for sess in sessions:
                acc = acc_map.get(sess["user"])
                if acc:
                    ActiveSession.objects.create(
                        account=acc,
                        pid=sess["pid"],
                        client_ip=sess.get("client_ip"),
                    )
        except Exception:
            logger.exception("Session sync failed for %s", srv)
