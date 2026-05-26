"""
SSH Remote Execution Module
============================
Provides a secure abstraction over paramiko for executing commands on
remote SSH servers. All panel ↔ server communication flows through this layer.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

import paramiko

logger = logging.getLogger(__name__)

_CONNECTION_TIMEOUT = 10
_COMMAND_TIMEOUT = 30


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class SSHManager:
    """Manages an SSH connection to a single remote server."""

    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "root",
        key_path: str = "",
    ):
        self.host = host
        self.port = port
        self.username = username
        self.key_path = key_path
        self._client: Optional[paramiko.SSHClient] = None

    @staticmethod
    def _load_private_key(path: str):
        for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
            try:
                return key_class.from_private_key_file(path)
            except Exception:
                continue
        raise ValueError(f"Unable to load SSH key from {path}")

    # -- connection lifecycle --------------------------------------------------

    def connect(self) -> None:
        if self._client is not None:
            return
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key = self._load_private_key(self.key_path) if self.key_path else None
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            pkey=key,
            timeout=_CONNECTION_TIMEOUT,
            allow_agent=not bool(self.key_path),
        )
        self._client = client
        logger.info("SSH connected to %s:%s", self.host, self.port)

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.disconnect()

    # -- command execution -----------------------------------------------------

    def run(self, command: str, timeout: int = _COMMAND_TIMEOUT) -> CommandResult:
        if not self._client:
            self.connect()
        logger.debug("SSH [%s] exec: %s", self.host, command)
        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        if exit_code != 0:
            logger.warning("SSH [%s] exit=%d stderr=%s", self.host, exit_code, err)
        return CommandResult(exit_code=exit_code, stdout=out, stderr=err)

    # -- user management -------------------------------------------------------

    def create_user(self, username: str, password: str) -> CommandResult:
        self.run(f"useradd -m -s /bin/false {_q(username)}")
        return self.run(f"echo {_q(username)}:{_q(password)} | chpasswd")

    def delete_user(self, username: str) -> CommandResult:
        self.run(f"pkill -u {_q(username)} || true")
        return self.run(f"userdel -rf {_q(username)}")

    def lock_user(self, username: str) -> CommandResult:
        return self.run(f"usermod -L {_q(username)}")

    def unlock_user(self, username: str) -> CommandResult:
        return self.run(f"usermod -U {_q(username)}")

    def set_expiry(self, username: str, date_str: str) -> CommandResult:
        """date_str in YYYY-MM-DD format."""
        return self.run(f"chage -E {_q(date_str)} {_q(username)}")

    def set_max_logins(self, username: str, max_logins: int) -> CommandResult:
        line = f"{username}  hard  maxlogins  {max_logins}"
        self.run(
            f"grep -q '^{_q(username)}' /etc/security/limits.conf "
            f"&& sed -i '/^{_q(username)}/c\\{line}' /etc/security/limits.conf "
            f"|| echo '{line}' >> /etc/security/limits.conf"
        )
        self._ensure_maxlogin_script()
        return CommandResult(exit_code=0, stdout="", stderr="")

    def _ensure_maxlogin_script(self) -> None:
        """Install a PAM script that enforces max logins on SSH connect."""
        script = r'''#!/bin/bash
USER="$PAM_USER"
[ -z "$USER" ] && exit 0
MAX=$(grep "^$USER" /etc/security/limits.conf 2>/dev/null | awk '/maxlogins/{print $4}')
[ -z "$MAX" ] && exit 0
CURRENT=$(ps -u "$USER" -o pid= 2>/dev/null | grep -c "sshd" 2>/dev/null || pgrep -cu "$USER" sshd 2>/dev/null || echo 0)
CURRENT=$(pgrep -c -u "$USER" sshd 2>/dev/null || echo 0)
if [ "$CURRENT" -gt "$MAX" ]; then
    exit 1
fi
exit 0
'''
        check = self.run("test -f /etc/ssh/check_maxlogins.sh && echo exists")
        if "exists" not in check.stdout:
            self.run(f"cat > /etc/ssh/check_maxlogins.sh << 'SCRIPT'\n{script}\nSCRIPT")
            self.run("chmod +x /etc/ssh/check_maxlogins.sh")
            self.run(
                "grep -q 'check_maxlogins' /etc/pam.d/sshd || "
                "echo 'session    required    pam_exec.so /etc/ssh/check_maxlogins.sh' >> /etc/pam.d/sshd"
            )

    def setup_traffic_accounting(self, username: str) -> None:
        """Set up iptables rules to track user bandwidth."""
        uid = self.run(f"id -u {_q(username)}").stdout.strip()
        if not uid or not uid.isdigit():
            return
        chain = f"SSHVPN_{username}"
        exists = self.run(f"iptables -L {chain} -n 2>/dev/null")
        if exists.exit_code != 0:
            self.run(f"iptables -N {chain}")
            self.run(f"iptables -A OUTPUT -m owner --uid-owner {uid} -j {chain}")
            self.run(f"iptables -A {chain} -j RETURN")

    def get_user_bandwidth_bytes(self, username: str) -> int:
        """Get total bytes transferred by user from iptables counters."""
        chain = f"SSHVPN_{username}"
        result = self.run(f"iptables -L {chain} -nvx 2>/dev/null | tail -1")
        if not result.ok or not result.stdout.strip():
            return 0
        parts = result.stdout.strip().split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
        return 0

    def change_password(self, username: str, password: str) -> CommandResult:
        return self.run(f"echo {_q(username)}:{_q(password)} | chpasswd")

    def user_exists(self, username: str) -> bool:
        return self.run(f"id {_q(username)}").ok

    # -- session tracking ------------------------------------------------------

    def get_active_sessions(self) -> list[dict]:
        """Return list of {'user', 'pid', 'client_ip'} for active SSH connections."""
        result = self.run(
            "ps -eo pid,user,args --no-headers | grep 'sshd:' | grep -v grep"
        )
        sessions = []
        if not result.ok or not result.stdout:
            return sessions
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) < 3:
                continue
            pid = parts[0]
            args = parts[2]
            match = re.match(r"sshd:\s+(\S+?)(?:@|$)", args)
            if not match:
                continue
            user = match.group(1)
            if user in ("root", "sshd", "priv"):
                continue
            ip = None
            ip_result = self.run(
                f"cat /proc/{pid}/net/tcp 2>/dev/null | awk 'NR>1{{print $3}}' | head -1"
            )
            if ip_result.ok and ip_result.stdout:
                hex_ip = ip_result.stdout.split(":")[0] if ":" in ip_result.stdout else ""
                if len(hex_ip) == 8:
                    try:
                        ip = ".".join(str(int(hex_ip[i:i+2], 16)) for i in (6, 4, 2, 0))
                    except ValueError:
                        pass
            if not ip:
                ss_result = self.run(f"ss -tnp 2>/dev/null | grep 'pid={pid}' | awk '{{print $5}}'")
                if ss_result.ok and ss_result.stdout:
                    addr = ss_result.stdout.splitlines()[0]
                    ip = addr.rsplit(":", 1)[0] if ":" in addr else None

            sessions.append({"user": user, "pid": int(pid), "client_ip": ip})
        return sessions

    # -- health metrics --------------------------------------------------------

    def get_health(self) -> dict:
        cpu = self._parse_float(self.run(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'"
        ).stdout)
        ram_out = self.run("free | awk '/Mem:/{printf \"%.1f\", $3/$2*100}'").stdout
        ram = self._parse_float(ram_out)
        disk_out = self.run("df / | awk 'NR==2{print $5}' | tr -d '%'").stdout
        disk = self._parse_float(disk_out)
        uptime_out = self.run("awk '{print int($1)}' /proc/uptime").stdout
        uptime = int(self._parse_float(uptime_out))
        return {
            "cpu_usage": cpu,
            "ram_usage": ram,
            "disk_usage": disk,
            "uptime_seconds": uptime,
        }

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _parse_float(value: str) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0


def _q(value: str) -> str:
    """Shell-quote a value to prevent injection."""
    return "'" + value.replace("'", "'\\''") + "'"


def get_ssh_manager(server) -> SSHManager:
    """Build an SSHManager from a Server model instance."""
    return SSHManager(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_user,
        key_path=server.ssh_key_path,
    )
