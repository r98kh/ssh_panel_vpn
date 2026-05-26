"""
ShadowLink Server Manager
==========================
Manages the ShadowLink Go process on remote nodes and communicates with
its bridge API for user registration/deregistration.
"""
import json
import logging
from typing import Optional

import requests

from servers.ssh import SSHManager, get_ssh_manager

logger = logging.getLogger(__name__)

BRIDGE_TIMEOUT = 10
BINARY_REMOTE_PATH = "/opt/shadowlink/shadowlink-server"
CONFIG_REMOTE_PATH = "/opt/shadowlink/config.yaml"
SERVICE_NAME = "shadowlink"


class ShadowLinkError(Exception):
    """Domain exception for ShadowLink operations."""


class ShadowLinkManager:
    """Manages ShadowLink Go server on a remote node via SSH + bridge API."""

    def __init__(self, server):
        self.server = server
        self.bridge_url = f"http://{server.ip_address}:{server.shadowlink_bridge_port}"
        self.api_key = server.shadowlink_api_key

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    def _bridge_request(self, method: str, path: str, data: Optional[dict] = None) -> dict:
        url = f"{self.bridge_url}{path}"
        try:
            resp = requests.request(
                method, url, json=data, headers=self._headers(), timeout=BRIDGE_TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            raise ShadowLinkError(f"Cannot reach ShadowLink bridge at {url}")
        except requests.Timeout:
            raise ShadowLinkError(f"Bridge request timed out: {url}")
        except requests.HTTPError as e:
            raise ShadowLinkError(f"Bridge API error: {e.response.status_code} - {e.response.text}")

    # --- Token management via bridge API ---

    def register_token(self, token: str, max_conns: int = 1) -> dict:
        return self._bridge_request("POST", "/api/tokens", {
            "token": token,
            "max_conns": max_conns,
        })

    def deregister_token(self, token: str) -> dict:
        return self._bridge_request("POST", "/api/tokens/delete", {
            "token": token,
        })

    def suspend_token(self, token: str) -> dict:
        return self._bridge_request("POST", "/api/tokens/suspend", {
            "token": token,
        })

    def activate_token(self, token: str) -> dict:
        return self._bridge_request("POST", "/api/tokens/activate", {
            "token": token,
        })

    def get_status(self) -> dict:
        return self._bridge_request("GET", "/api/status")

    def get_sessions(self) -> list:
        return self._bridge_request("GET", "/api/sessions")

    def health_check(self) -> dict:
        return self._bridge_request("GET", "/api/health")

    # --- Server deployment via SSH ---

    def deploy_binary(self, binary_path: str) -> None:
        """Upload the ShadowLink server binary to the remote node."""
        with get_ssh_manager(self.server) as ssh:
            ssh.run("mkdir -p /opt/shadowlink")
            sftp = ssh._client.open_sftp()
            try:
                sftp.put(binary_path, BINARY_REMOTE_PATH)
                sftp.chmod(BINARY_REMOTE_PATH, 0o755)
            finally:
                sftp.close()
            logger.info("Deployed ShadowLink binary to %s", self.server.ip_address)

    def deploy_config(self) -> None:
        """Generate and upload config to the remote node."""
        config = self._generate_config()
        with get_ssh_manager(self.server) as ssh:
            ssh.run("mkdir -p /opt/shadowlink")
            ssh.run(f"cat > {CONFIG_REMOTE_PATH} << 'SLEOF'\n{config}\nSLEOF")
            logger.info("Deployed ShadowLink config to %s", self.server.ip_address)

    def deploy_systemd_service(self) -> None:
        """Install and enable systemd service for ShadowLink."""
        unit = self._generate_systemd_unit()
        with get_ssh_manager(self.server) as ssh:
            ssh.run(f"cat > /etc/systemd/system/{SERVICE_NAME}.service << 'SLEOF'\n{unit}\nSLEOF")
            ssh.run("systemctl daemon-reload")
            ssh.run(f"systemctl enable {SERVICE_NAME}")
            logger.info("Installed ShadowLink systemd service on %s", self.server.ip_address)

    def start_service(self) -> None:
        with get_ssh_manager(self.server) as ssh:
            result = ssh.run(f"systemctl start {SERVICE_NAME}")
            if not result.ok:
                raise ShadowLinkError(f"Failed to start ShadowLink: {result.stderr}")

    def stop_service(self) -> None:
        with get_ssh_manager(self.server) as ssh:
            ssh.run(f"systemctl stop {SERVICE_NAME}")

    def restart_service(self) -> None:
        with get_ssh_manager(self.server) as ssh:
            result = ssh.run(f"systemctl restart {SERVICE_NAME}")
            if not result.ok:
                raise ShadowLinkError(f"Failed to restart ShadowLink: {result.stderr}")

    def service_status(self) -> dict:
        with get_ssh_manager(self.server) as ssh:
            result = ssh.run(f"systemctl is-active {SERVICE_NAME}")
            is_active = result.stdout.strip() == "active"
            pid_result = ssh.run(f"systemctl show {SERVICE_NAME} --property=MainPID --value")
            pid = pid_result.stdout.strip() if pid_result.ok else "0"
            return {
                "running": is_active,
                "pid": int(pid) if pid.isdigit() else 0,
                "status": result.stdout.strip(),
            }

    def full_deploy(self, binary_path: str) -> None:
        """Complete deployment: binary + config + systemd + start."""
        self.deploy_binary(binary_path)
        self.deploy_config()
        self.deploy_systemd_service()
        self.start_service()
        logger.info("Full ShadowLink deployment completed on %s", self.server.ip_address)

    # --- Config generation ---

    def _generate_config(self) -> str:
        import yaml
        config = {
            "server": {
                "listen_addr": f"0.0.0.0:{self.server.shadowlink_port}",
                "ws_path": self.server.shadowlink_ws_path,
                "tls_cert": "",
                "tls_key": "",
                "decoy_dir": "",
            },
            "bridge": {
                "listen_addr": f"127.0.0.1:{self.server.shadowlink_bridge_port}",
                "api_key": self.server.shadowlink_api_key,
            },
            "obfuscation": {
                "padding": {"enabled": True, "min_bytes": 16, "max_bytes": 128},
                "timing": {"enabled": True, "min_delay": "0ms", "max_delay": "50ms"},
                "traffic_shape": {"enabled": True, "idle_interval": "5s"},
            },
            "sessions": {
                "idle_timeout": "5m",
                "cleanup_interval": "1m",
                "max_per_token": 3,
            },
        }
        return yaml.dump(config, default_flow_style=False)

    def _generate_systemd_unit(self) -> str:
        return f"""[Unit]
Description=ShadowLink Proxy Server
After=network.target

[Service]
Type=simple
ExecStart={BINARY_REMOTE_PATH} -config {CONFIG_REMOTE_PATH}
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target"""

    # --- Client config generation ---

    @staticmethod
    def generate_client_config(account, server) -> dict:
        """Generate a client config dict for a ShadowLink account."""
        domain = server.shadowlink_domain or server.ip_address
        return {
            "client": {
                "listen_addr": "127.0.0.1:1080",
                "server_addr": f"{domain}:{server.shadowlink_port}",
                "server_sni": domain,
                "ws_path": server.shadowlink_ws_path,
                "auth_token": str(account.auth_token),
                "use_tls": True,
                "insecure": not bool(server.shadowlink_domain),
            },
            "cdn": {
                "enabled": False,
                "cdn_address": "",
                "domain": domain,
                "ws_path": server.shadowlink_ws_path,
            },
            "obfuscation": {
                "padding": {"enabled": True, "min_bytes": 16, "max_bytes": 128},
                "timing": {"enabled": True, "min_delay": "0ms", "max_delay": "50ms"},
                "traffic_shape": {"enabled": True, "idle_interval": "5s"},
            },
        }


def get_shadowlink_manager(server) -> ShadowLinkManager:
    """Build a ShadowLinkManager from a Server model instance."""
    return ShadowLinkManager(server)
