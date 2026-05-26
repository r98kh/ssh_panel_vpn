#!/usr/bin/env bash
#
# deploy.sh — One-command deployment for SSH VPN Panel
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Options:
#   ./deploy.sh --build     Force rebuild images
#   ./deploy.sh --down      Stop all services
#   ./deploy.sh --restart   Restart all services
#   ./deploy.sh --logs      Show live logs
#   ./deploy.sh --ssl       Setup SSL with Let's Encrypt
#
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_banner() {
    echo -e "${CYAN}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "   SSH VPN Management Panel - Deployer"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${NC}"
}

log_info() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

check_dependencies() {
    local missing=()

    if ! command -v docker &>/dev/null; then
        missing+=("docker")
    fi

    if ! docker compose version &>/dev/null 2>&1; then
        if ! command -v docker-compose &>/dev/null; then
            missing+=("docker-compose")
        fi
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        echo ""
        echo "Install Docker:"
        echo "  curl -fsSL https://get.docker.com | sh"
        echo "  sudo usermod -aG docker \$USER"
        echo "  newgrp docker"
        echo ""
        exit 1
    fi

    if ! docker info &>/dev/null 2>&1; then
        log_error "Docker daemon is not running. Start it with:"
        echo "  sudo systemctl start docker"
        exit 1
    fi

    log_info "Docker is installed and running"
}

setup_env() {
    if [ ! -f .env ]; then
        if [ -f .env.production ]; then
            cp .env.production .env
            log_warn ".env file created from .env.production"
            log_warn "Please edit .env with your actual values before continuing!"
            echo ""
            echo -e "  ${CYAN}nano .env${NC}  (or use any editor)"
            echo ""
            echo "Required changes:"
            echo "  - SECRET_KEY: Generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(64))\""
            echo "  - DB_PASSWORD: Set a strong database password"
            echo "  - ALLOWED_HOSTS: Your server domain/IP"
            echo "  - DJANGO_SUPERUSER_PASSWORD: Admin panel password"
            echo "  - CORS_ALLOWED_ORIGINS: Your domain with https://"
            echo "  - CSRF_TRUSTED_ORIGINS: Your domain with https://"
            echo ""
            read -p "Have you edited .env? (y/N): " confirm
            if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
                log_error "Aborted. Edit .env and run again."
                exit 1
            fi
        else
            log_error "No .env or .env.production found!"
            exit 1
        fi
    fi

    source .env 2>/dev/null || true

    if [[ "${SECRET_KEY:-}" == *"CHANGE-ME"* ]] || [[ -z "${SECRET_KEY:-}" ]]; then
        log_warn "Generating a random SECRET_KEY..."
        local new_key
        new_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))" 2>/dev/null || openssl rand -base64 48)
        sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$new_key|" .env
        log_info "SECRET_KEY auto-generated"
    fi

    log_info "Environment file is ready"
}

compose_cmd() {
    if docker compose version &>/dev/null 2>&1; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

do_deploy() {
    print_banner
    check_dependencies
    setup_env

    echo ""
    log_info "Building and starting all services..."
    echo ""

    compose_cmd up -d --build --remove-orphans

    echo ""
    log_info "Waiting for services to be healthy..."
    sleep 5

    local retries=30
    while [ $retries -gt 0 ]; do
        if compose_cmd ps | grep -q "healthy"; then
            break
        fi
        retries=$((retries - 1))
        sleep 2
    done

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Deployment Complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  Services:"
    compose_cmd ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "  Access:"
    echo "    Panel:  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-server-ip')"
    echo "    Admin:  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-server-ip')/admin/"
    echo "    API:    http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-server-ip')/api/"
    echo ""
    echo "  Commands:"
    echo "    Logs:       ./deploy.sh --logs"
    echo "    Stop:       ./deploy.sh --down"
    echo "    Restart:    ./deploy.sh --restart"
    echo "    SSL Setup:  ./deploy.sh --ssl your-domain.com"
    echo ""
}

do_down() {
    log_info "Stopping all services..."
    compose_cmd down
    log_info "All services stopped"
}

do_restart() {
    log_info "Restarting all services..."
    compose_cmd restart
    log_info "All services restarted"
}

do_logs() {
    compose_cmd logs -f --tail=100
}

do_ssl() {
    local domain="${1:-}"
    if [ -z "$domain" ]; then
        log_error "Usage: ./deploy.sh --ssl your-domain.com"
        exit 1
    fi

    log_info "Setting up SSL for $domain..."

    # Create SSL nginx config
    cat > nginx/default.conf <<NGINX
upstream django {
    server web:8000;
}

server {
    listen 80;
    server_name $domain;

    location /health/ {
        access_log off;
        return 200 "OK";
    }

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name $domain;

    ssl_certificate /etc/letsencrypt/live/$domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$domain/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 20M;

    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300;
    }
}
NGINX

    docker run --rm \
        -v "$(pwd)/certbot_www:/var/www/certbot" \
        -v "$(pwd)/certbot_conf:/etc/letsencrypt" \
        -p 80:80 \
        certbot/certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "admin@$domain" \
        -d "$domain"

    compose_cmd restart nginx
    log_info "SSL configured for $domain"

    # Setup auto-renewal cron
    (crontab -l 2>/dev/null; echo "0 3 * * * cd $(pwd) && docker run --rm -v $(pwd)/certbot_conf:/etc/letsencrypt -v $(pwd)/certbot_www:/var/www/certbot certbot/certbot renew --quiet && docker compose restart nginx") | sort -u | crontab -
    log_info "Auto-renewal cron job added"
}

do_update() {
    log_info "Pulling latest code and rebuilding..."
    git pull origin main 2>/dev/null || true
    compose_cmd up -d --build --remove-orphans
    log_info "Update complete"
}

# --- Main ---
cd "$(dirname "$0")"

case "${1:-}" in
    --down|-d)
        do_down
        ;;
    --restart|-r)
        do_restart
        ;;
    --logs|-l)
        do_logs
        ;;
    --build|-b)
        compose_cmd up -d --build --force-recreate --remove-orphans
        ;;
    --ssl)
        do_ssl "${2:-}"
        ;;
    --update|-u)
        do_update
        ;;
    --status|-s)
        compose_cmd ps
        ;;
    --help|-h)
        print_banner
        echo "Usage: ./deploy.sh [option]"
        echo ""
        echo "Options:"
        echo "  (none)        First-time deploy / start services"
        echo "  --build, -b   Force rebuild all images"
        echo "  --down, -d    Stop all services"
        echo "  --restart, -r Restart all services"
        echo "  --logs, -l    Show live logs (Ctrl+C to exit)"
        echo "  --ssl DOMAIN  Setup Let's Encrypt SSL"
        echo "  --update, -u  Pull git & rebuild"
        echo "  --status, -s  Show service status"
        echo "  --help, -h    Show this help"
        echo ""
        ;;
    *)
        do_deploy
        ;;
esac
