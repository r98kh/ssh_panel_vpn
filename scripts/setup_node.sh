#!/usr/bin/env bash
#
# setup_node.sh — Prepare a fresh Ubuntu server as an SSH VPN node.
# Run on the TARGET server (not the panel server).
#
# Usage:  bash setup_node.sh <panel_public_key_file>
#
set -euo pipefail

PANEL_KEY_FILE="${1:-}"

if [[ -z "$PANEL_KEY_FILE" ]]; then
    echo "Usage: $0 <path_to_panel_public_key>"
    exit 1
fi

echo "==> Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

echo "==> Installing required packages..."
apt-get install -y -qq openssh-server libpam-modules fail2ban

echo "==> Hardening SSH configuration..."
SSHD_CONFIG="/etc/ssh/sshd_config"
cp "$SSHD_CONFIG" "${SSHD_CONFIG}.bak"

cat > /etc/ssh/sshd_config.d/vpn-hardening.conf <<'SSHCONF'
PermitRootLogin prohibit-password
PasswordAuthentication yes
MaxAuthTries 5
MaxSessions 10
ClientAliveInterval 300
ClientAliveCountMax 2
AllowTcpForwarding yes
GatewayPorts no
X11Forwarding no
UsePAM yes
SSHCONF

echo "==> Setting up PAM session limits..."
if ! grep -q 'pam_limits.so' /etc/pam.d/sshd; then
    echo "session required pam_limits.so" >> /etc/pam.d/sshd
fi

echo "==> Creating management user 'vpnpanel'..."
if ! id vpnpanel &>/dev/null; then
    useradd -m -s /bin/bash vpnpanel
    mkdir -p /home/vpnpanel/.ssh
    chmod 700 /home/vpnpanel/.ssh
    cp "$PANEL_KEY_FILE" /home/vpnpanel/.ssh/authorized_keys
    chmod 600 /home/vpnpanel/.ssh/authorized_keys
    chown -R vpnpanel:vpnpanel /home/vpnpanel/.ssh

    # Grant passwordless sudo for user management commands
    cat > /etc/sudoers.d/vpnpanel <<'SUDOERS'
vpnpanel ALL=(root) NOPASSWD: /usr/sbin/useradd, /usr/sbin/userdel, /usr/sbin/usermod, /usr/bin/chpasswd, /usr/bin/chage, /usr/bin/pkill
SUDOERS
    chmod 440 /etc/sudoers.d/vpnpanel
fi

echo "==> Configuring fail2ban..."
cat > /etc/fail2ban/jail.local <<'F2B'
[sshd]
enabled = true
port = ssh
maxretry = 5
bantime = 3600
findtime = 600
F2B
systemctl enable fail2ban
systemctl restart fail2ban

echo "==> Restarting SSH service..."
systemctl restart sshd

echo ""
echo "=========================================="
echo "  Node setup complete!"
echo "  SSH user: vpnpanel"
echo "  Auth: key-based only"
echo "  Remember to add this server to the panel."
echo "=========================================="
