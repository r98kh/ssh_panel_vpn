# SSH VPN Management Panel

Production-ready SSH account provisioning and management system built with Django, PostgreSQL, Redis, and Celery.

## Architecture

```
┌──────────────┐     REST API / Admin UI     ┌──────────────────┐
│   Clients    │ ◄────────────────────────── │   Django Panel    │
│  (Browser /  │                             │  + DRF + Admin    │
│  Telegram)   │                             └───────┬──────────┘
└──────────────┘                                     │
                                                     │  Paramiko SSH
                                              ┌──────┴──────┐
                                              │             │
                                         ┌────▼───┐   ┌────▼───┐
                                         │ Node 1 │   │ Node N │   ← Ubuntu SSH servers
                                         └────────┘   └────────┘

Background:  Celery Worker + Beat  ──►  PostgreSQL + Redis
```

## Features

- **Multi-server management** — add unlimited SSH nodes with auto load-balancing
- **Full account lifecycle** — create, suspend, activate, extend, delete, bulk create
- **Auto-expiration** — Celery Beat expires and cleans up accounts automatically
- **Health monitoring** — per-minute CPU/RAM/disk checks on every node
- **Real-time sessions** — track who's connected right now
- **Audit trail** — every admin action is logged
- **REST API** — full API with token auth, throttling, and OpenAPI docs
- **Telegram bot** — sell accounts directly through Telegram
- **QR codes** — generate credential QR codes
- **Import/Export** — CSV export of accounts via Django Admin
- **Payment webhook** — mock endpoint ready for real payment gateway integration

## Quick Start (Docker)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your settings

# 2. Start everything
docker compose up -d

# 3. Run migrations and create admin user
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seedplans

# 4. Access
# Admin panel:  http://localhost:8000/admin/
# API docs:     http://localhost:8000/api/docs/
```

## Quick Start (Local Development)

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env — set DATABASE, REDIS, SECRET_KEY

# 3. Database setup
python manage.py migrate
python manage.py createsuperuser
python manage.py seedplans

# 4. Run
python manage.py runserver          # Web server
celery -A sshvpn worker -l info     # Worker (separate terminal)
celery -A sshvpn beat -l info       # Beat scheduler (separate terminal)
```

## Project Structure

```
vpn/
├── sshvpn/                  # Django project settings
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
├── accounts/                # SSH account models, services, tasks
│   ├── models.py            # SSHAccount, ActiveSession, AuditLog
│   ├── services.py          # Business logic (create, delete, suspend...)
│   ├── tasks.py             # Celery: expire_users, sync_sessions
│   ├── admin.py             # Rich admin with badges, actions, import/export
│   └── utils.py             # QR code generation
├── servers/                 # Server node management
│   ├── models.py            # Server model with health fields
│   ├── ssh.py               # Paramiko SSH execution layer
│   ├── tasks.py             # Celery: health checks, rebalancing
│   └── admin.py             # Admin with progress bars
├── plans/                   # Subscription plans
│   ├── models.py
│   └── admin.py
├── api/                     # REST API (DRF)
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── bot/                     # Telegram bot
│   └── telegram_bot.py
├── scripts/                 # Deployment scripts
│   ├── setup_panel.sh       # Panel server bootstrap
│   ├── setup_node.sh        # SSH node bootstrap
│   └── nginx.conf           # Nginx reverse proxy config
├── templates/               # Admin template overrides
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/` | Summary statistics |
| GET/POST | `/api/servers/` | List / add servers |
| GET/PUT/DELETE | `/api/servers/<id>/` | Server detail |
| POST | `/api/servers/<id>/health-check/` | Trigger health check |
| GET/POST | `/api/plans/` | List / add plans |
| GET | `/api/accounts/` | List accounts (filter, search, sort) |
| POST | `/api/create-user/` | Create single account |
| POST | `/api/bulk-create/` | Bulk create accounts |
| POST | `/api/delete-user/<id>/` | Delete account |
| POST | `/api/suspend-user/<id>/` | Suspend account |
| POST | `/api/activate-user/<id>/` | Activate account |
| POST | `/api/extend-user/<id>/` | Extend subscription |
| POST | `/api/reset-password/<id>/` | Reset password |
| GET | `/api/sessions/` | Active SSH sessions |
| GET | `/api/logs/` | Audit log |
| POST | `/api/webhook/payment/` | Payment webhook (mock) |

**Authentication**: Token-based (`Authorization: Token <key>`) or session auth.

## Adding a New SSH Node

1. **On the node server**, run the setup script:
   ```bash
   scp scripts/setup_node.sh root@NODE_IP:/tmp/
   scp /opt/sshvpn/keys/panel_key.pub root@NODE_IP:/tmp/
   ssh root@NODE_IP "bash /tmp/setup_node.sh /tmp/panel_key.pub"
   ```

2. **In the admin panel**, go to Servers → Add Server:
   - IP: `NODE_IP`
   - SSH User: `vpnpanel`
   - SSH Key Path: `/opt/sshvpn/keys/panel_key`

3. The health check will run within 1 minute automatically.

## Telegram Bot

Set `TELEGRAM_BOT_TOKEN` in `.env`, then:

```bash
python manage.py runbot
```

Commands:
- `/plans` — List available plans
- `/buy <plan_id> <username>` — Purchase an account
- `/status <username>` — Check account status

## Production Deployment

See `scripts/setup_panel.sh` for full server bootstrap. Key steps:

1. Run `setup_panel.sh` on Ubuntu 22.04+
2. Copy project to `/opt/sshvpn/`
3. Configure `.env` with production values
4. Set up Nginx with `scripts/nginx.conf`
5. Enable HTTPS: `certbot --nginx -d your-domain.com`
6. Start services: `systemctl start sshvpn-web sshvpn-celery sshvpn-beat`

## Security Notes

- Panel↔Node communication uses SSH key auth (no passwords)
- Admin panel supports session auth with CSRF protection
- API is rate-limited (30/min anon, 120/min authenticated)
- All admin actions are audit-logged
- Passwords are shown once at creation, then should be cleared
- Production mode enables HSTS, secure cookies, SSL redirect
- Node servers use fail2ban for brute-force protection
- Node management user has restricted sudo (only user management commands)
