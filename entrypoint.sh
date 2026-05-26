#!/usr/bin/env bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SSH VPN Panel - Starting up..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

wait_for_service() {
    local host="$1"
    local port="$2"
    local service="$3"
    local retries=30

    echo "[*] Waiting for $service ($host:$port)..."
    while ! python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('$host', $port)); s.close()" 2>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            echo "[!] FATAL: $service is not reachable after 30 attempts"
            exit 1
        fi
        sleep 1
    done
    echo "[✓] $service is ready"
}

wait_for_service "${DB_HOST:-db}" "${DB_PORT:-5432}" "PostgreSQL"
wait_for_service "${REDIS_HOST:-redis}" "6379" "Redis"

echo "[*] Running database migrations..."
python manage.py migrate --noinput

if [ "$CREATE_SUPERUSER" = "true" ]; then
    echo "[*] Creating superuser..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME:-admin}').exists():
    User.objects.create_superuser(
        username='${DJANGO_SUPERUSER_USERNAME:-admin}',
        email='${DJANGO_SUPERUSER_EMAIL:-admin@example.com}',
        password='${DJANGO_SUPERUSER_PASSWORD:-admin}'
    )
    print('[✓] Superuser created')
else:
    print('[~] Superuser already exists')
"
fi

if [ "$SEED_DATA" = "true" ]; then
    echo "[*] Seeding initial plans..."
    python manage.py seedplans 2>/dev/null || echo "[~] Seed command skipped or already applied"
fi

echo "[*] Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

mkdir -p /app/logs

echo "[✓] Initialization complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exec "$@"
