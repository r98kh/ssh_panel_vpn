"""
Account Service Layer
======================
All business logic for SSH/ShadowLink account lifecycle management.
Controllers (views / API) call into this module — never touch SSH directly.
"""
import logging
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from accounts.models import SSHAccount, AuditLog, generate_password
from plans.models import Plan
from servers.models import Server
from servers.ssh import get_ssh_manager

logger = logging.getLogger(__name__)


def _get_shadowlink_manager(server):
    from servers.shadowlink import get_shadowlink_manager
    return get_shadowlink_manager(server)


class AccountError(Exception):
    """Domain exception for account operations."""


def pick_best_server(preferred: Optional[Server] = None) -> Server:
    """Select the least-loaded active server, or a specific one if given."""
    if preferred and preferred.is_available:
        return preferred
    servers = (
        Server.objects
        .filter(status=Server.Status.ACTIVE)
        .order_by("cpu_usage")
    )
    for srv in servers:
        if srv.is_available:
            return srv
    raise AccountError("No available servers. All are full or offline.")


@transaction.atomic
def create_account(
    username: str,
    plan: Plan,
    server: Optional[Server] = None,
    password: Optional[str] = None,
    admin_user=None,
    note: str = "",
    duration_days: Optional[int] = None,
    bandwidth_limit_gb: Optional[int] = None,
    max_connections: Optional[int] = None,
    protocol_type: Optional[str] = None,
) -> SSHAccount:
    server = pick_best_server(server)
    password = password or generate_password()
    days = duration_days if duration_days is not None else plan.duration_days
    expire_date = timezone.now() + timedelta(days=days)
    bw_limit = bandwidth_limit_gb if bandwidth_limit_gb is not None else plan.bandwidth_limit_gb
    max_conn = max_connections if max_connections is not None else plan.max_connections
    proto = protocol_type or server.protocol_type

    account = SSHAccount.objects.create(
        username=username,
        password_display=password if proto == "ssh" else "",
        server=server,
        plan=plan,
        protocol_type=proto,
        status=SSHAccount.Status.ACTIVE,
        expire_date=expire_date,
        max_connections=max_conn,
        bandwidth_limit_gb=bw_limit,
        created_by=admin_user,
        note=note,
    )

    if proto == "shadowlink":
        _provision_shadowlink_account(account, server, max_conn)
    else:
        with get_ssh_manager(server) as ssh:
            result = ssh.create_user(username, password)
            if not result.ok:
                raise AccountError(f"Remote user creation failed: {result.stderr}")
            ssh.set_expiry(username, expire_date.strftime("%Y-%m-%d"))
            ssh.set_max_logins(username, max_conn)
            if bw_limit > 0:
                ssh.setup_traffic_accounting(username)

    AuditLog.objects.create(
        action=AuditLog.Action.CREATE,
        account=account,
        admin_user=admin_user,
        detail=f"Plan={plan.name}, Server={server.name}, Protocol={proto}",
    )
    logger.info("Account created: %s on %s (protocol=%s)", username, server, proto)
    return account


def _provision_shadowlink_account(account: SSHAccount, server: Server, max_conns: int) -> None:
    """Register the account's auth token with the ShadowLink bridge."""
    try:
        mgr = _get_shadowlink_manager(server)
        mgr.register_token(str(account.auth_token), max_conns)
    except Exception as e:
        raise AccountError(f"ShadowLink provisioning failed: {e}")


def delete_account(account: SSHAccount, admin_user=None) -> None:
    if account.protocol_type == "shadowlink":
        try:
            mgr = _get_shadowlink_manager(account.server)
            mgr.deregister_token(str(account.auth_token))
        except Exception as e:
            logger.warning("ShadowLink deregister failed: %s", e)
    else:
        with get_ssh_manager(account.server) as ssh:
            ssh.delete_user(account.username)

    account.status = SSHAccount.Status.DELETED
    account.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        action=AuditLog.Action.DELETE,
        account=account,
        admin_user=admin_user,
    )
    logger.info("Account deleted: %s", account)


def suspend_account(account: SSHAccount, admin_user=None) -> None:
    if account.protocol_type == "shadowlink":
        try:
            mgr = _get_shadowlink_manager(account.server)
            mgr.suspend_token(str(account.auth_token))
        except Exception as e:
            logger.warning("ShadowLink suspend failed: %s", e)
    else:
        with get_ssh_manager(account.server) as ssh:
            ssh.lock_user(account.username)

    account.status = SSHAccount.Status.SUSPENDED
    account.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        action=AuditLog.Action.SUSPEND,
        account=account,
        admin_user=admin_user,
    )


def activate_account(account: SSHAccount, admin_user=None) -> None:
    if account.protocol_type == "shadowlink":
        try:
            mgr = _get_shadowlink_manager(account.server)
            mgr.activate_token(str(account.auth_token))
        except Exception as e:
            logger.warning("ShadowLink activate failed: %s", e)
    else:
        with get_ssh_manager(account.server) as ssh:
            ssh.unlock_user(account.username)

    account.status = SSHAccount.Status.ACTIVE
    account.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        action=AuditLog.Action.ACTIVATE,
        account=account,
        admin_user=admin_user,
    )


def extend_account(account: SSHAccount, days: int, admin_user=None) -> None:
    account.extend(days)
    with get_ssh_manager(account.server) as ssh:
        ssh.set_expiry(account.username, account.expire_date.strftime("%Y-%m-%d"))
        if account.status == SSHAccount.Status.EXPIRED:
            ssh.unlock_user(account.username)
    AuditLog.objects.create(
        action=AuditLog.Action.EXTEND,
        account=account,
        admin_user=admin_user,
        detail=f"+{days} days → {account.expire_date:%Y-%m-%d}",
    )


def reset_password(account: SSHAccount, admin_user=None) -> str:
    new_pw = generate_password()
    with get_ssh_manager(account.server) as ssh:
        result = ssh.change_password(account.username, new_pw)
        if not result.ok:
            raise AccountError(f"Password reset failed: {result.stderr}")
    account.password_display = new_pw
    account.save(update_fields=["password_display", "updated_at"])
    AuditLog.objects.create(
        action=AuditLog.Action.PASSWORD_RESET,
        account=account,
        admin_user=admin_user,
    )
    return new_pw


def bulk_create_accounts(
    prefix: str,
    count: int,
    plan: Plan,
    server: Optional[Server] = None,
    admin_user=None,
) -> list[SSHAccount]:
    accounts = []
    for i in range(1, count + 1):
        username = f"{prefix}{i:03d}"
        try:
            acc = create_account(
                username=username,
                plan=plan,
                server=server,
                admin_user=admin_user,
            )
            accounts.append(acc)
        except AccountError:
            logger.error("Bulk create failed at %s", username)
            break
    return accounts
