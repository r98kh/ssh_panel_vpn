#!/usr/bin/env bash
#
# setup_panel.sh — Bootstrap the panel server (Ubuntu 22.04+)
#
# Run as root or with sudo.
#
set -euo pipefail

echo "==> Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    redis-server \
    nginx certbot python3-certbot-nginx \
    git

echo "==> Creating database..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='vpn'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER vpn WITH PASSWORD 'vpn';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='sshvpn'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE sshvpn OWNER vpn;"

echo "==> Setting up Python virtual environment..."
PROJECT_DIR="/opt/sshvpn"
mkdir -p "$PROJECT_DIR"
python3 -m venv "$PROJECT_DIR/venv"
source "$PROJECT_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r /home/rasool/Desktop/vpn/requirements.txt

echo "==> Generating SSH keypair for panel↔node communication..."
KEY_DIR="$PROJECT_DIR/keys"
mkdir -p "$KEY_DIR"
if [ ! -f "$KEY_DIR/panel_key" ]; then
    ssh-keygen -t ed25519 -f "$KEY_DIR/panel_key" -N "" -C "sshvpn-panel"
    echo "Panel public key: $KEY_DIR/panel_key.pub"
fi

echo "==> Creating log directory..."
mkdir -p /opt/sshvpn/logs

echo "==> Setting up systemd services..."

cat > /etc/systemd/system/sshvpn-web.service <<'SVC'
[Unit]
Description=SSH VPN Panel Web
After=network.target postgresql.service redis.service

[Service]
User=www-data
WorkingDirectory=/opt/sshvpn
ExecStart=/opt/sshvpn/venv/bin/gunicorn sshvpn.wsgi:application --bind 127.0.0.1:8000 --workers 4
Restart=always
EnvironmentFile=/opt/sshvpn/.env

[Install]
WantedBy=multi-user.target
SVC

cat > /etc/systemd/system/sshvpn-celery.service <<'SVC'
[Unit]
Description=SSH VPN Celery Worker
After=network.target redis.service

[Service]
User=www-data
WorkingDirectory=/opt/sshvpn
ExecStart=/opt/sshvpn/venv/bin/celery -A sshvpn worker -l info --concurrency=4
Restart=always
EnvironmentFile=/opt/sshvpn/.env

[Install]
WantedBy=multi-user.target
SVC

cat > /etc/systemd/system/sshvpn-beat.service <<'SVC'
[Unit]
Description=SSH VPN Celery Beat
After=network.target redis.service

[Service]
User=www-data
WorkingDirectory=/opt/sshvpn
ExecStart=/opt/sshvpn/venv/bin/celery -A sshvpn beat -l info
Restart=always
EnvironmentFile=/opt/sshvpn/.env

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable sshvpn-web sshvpn-celery sshvpn-beat

echo ""
echo "=========================================="
echo "  Panel setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Copy your project to /opt/sshvpn/"
echo "  2. Create /opt/sshvpn/.env from .env.example"
echo "  3. Run: source /opt/sshvpn/venv/bin/activate"
echo "  4. Run: python manage.py migrate"
echo "  5. Run: python manage.py createsuperuser"
echo "  6. Run: python manage.py seedplans"
echo "  7. Start services: systemctl start sshvpn-web sshvpn-celery sshvpn-beat"
echo "  8. Configure Nginx reverse proxy"
echo "=========================================="
