#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────
#  ShadowLink Node Setup Script
#  Deploys and configures ShadowLink server on a fresh VPS
# ─────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="/opt/shadowlink"
CONFIG_FILE="$INSTALL_DIR/config.yaml"
SERVICE_NAME="shadowlink"
BINARY_NAME="shadowlink-server"
DEFAULT_PORT=8443
DEFAULT_BRIDGE_PORT=9090
DEFAULT_WS_PATH="/ws"

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════╗"
    echo "║       ShadowLink Node Setup              ║"
    echo "║       Anti-Censorship Proxy Protocol     ║"
    echo "╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

generate_api_key() {
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
}

generate_uuid() {
    cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())"
}

# ── Check root ──────────────────────────────────────────────
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# ── Detect server IP ────────────────────────────────────────
detect_ip() {
    SERVER_IP=$(curl -s4 ifconfig.me 2>/dev/null || curl -s4 icanhazip.com 2>/dev/null || hostname -I | awk '{print $1}')
    echo "$SERVER_IP"
}

# ── Interactive config ──────────────────────────────────────
collect_config() {
    SERVER_IP=$(detect_ip)
    log_info "Detected server IP: $SERVER_IP"

    echo ""
    read -p "ShadowLink port [$DEFAULT_PORT]: " SL_PORT
    SL_PORT=${SL_PORT:-$DEFAULT_PORT}

    read -p "Bridge API port [$DEFAULT_BRIDGE_PORT]: " BRIDGE_PORT
    BRIDGE_PORT=${BRIDGE_PORT:-$DEFAULT_BRIDGE_PORT}

    read -p "WebSocket path [$DEFAULT_WS_PATH]: " WS_PATH
    WS_PATH=${WS_PATH:-$DEFAULT_WS_PATH}

    API_KEY=$(generate_api_key)
    log_info "Generated API key: $API_KEY"

    read -p "How many user tokens to create? [1]: " TOKEN_COUNT
    TOKEN_COUNT=${TOKEN_COUNT:-1}

    TOKENS=()
    for i in $(seq 1 $TOKEN_COUNT); do
        TOKEN=$(generate_uuid)
        TOKENS+=("$TOKEN")
    done

    read -p "Max connections per token? [2]: " MAX_CONNS
    MAX_CONNS=${MAX_CONNS:-2}
}

# ── Install binary ──────────────────────────────────────────
install_binary() {
    log_info "Setting up installation directory..."
    mkdir -p "$INSTALL_DIR"

    if [ ! -f "$INSTALL_DIR/$BINARY_NAME" ]; then
        log_error "Binary not found at $INSTALL_DIR/$BINARY_NAME"
        log_info "Upload it first with:"
        echo ""
        echo -e "  ${CYAN}scp shadowlink/dist/shadowlink-server-linux-amd64 root@$SERVER_IP:$INSTALL_DIR/$BINARY_NAME${NC}"
        echo ""
        read -p "Have you uploaded it? Press Enter to continue or Ctrl+C to abort..."

        if [ ! -f "$INSTALL_DIR/$BINARY_NAME" ]; then
            log_error "Binary still not found. Aborting."
            exit 1
        fi
    fi

    chmod +x "$INSTALL_DIR/$BINARY_NAME"
    log_info "Binary ready at $INSTALL_DIR/$BINARY_NAME"
}

# ── Write config ────────────────────────────────────────────
write_config() {
    log_info "Writing server config..."

    cat > "$CONFIG_FILE" << EOF
server:
  listen_addr: "0.0.0.0:$SL_PORT"
  ws_path: "$WS_PATH"
  tls_cert: ""
  tls_key: ""
  decoy_dir: ""

bridge:
  listen_addr: "127.0.0.1:$BRIDGE_PORT"
  api_key: "$API_KEY"

obfuscation:
  padding:
    enabled: true
    min_bytes: 16
    max_bytes: 128
  timing:
    enabled: true
    min_delay: "0ms"
    max_delay: "50ms"
  traffic_shape:
    enabled: true
    idle_interval: "5s"

sessions:
  idle_timeout: "5m"
  cleanup_interval: "1m"
  max_per_token: $MAX_CONNS
EOF

    log_info "Config written to $CONFIG_FILE"
}

# ── Systemd service ─────────────────────────────────────────
install_service() {
    log_info "Installing systemd service..."

    cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=ShadowLink Proxy Server
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/$BINARY_NAME -config $CONFIG_FILE
Restart=always
RestartSec=5
LimitNOFILE=65535
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    log_info "Systemd service installed and enabled"
}

# ── Firewall ────────────────────────────────────────────────
configure_firewall() {
    log_info "Configuring firewall..."

    if command -v ufw &>/dev/null; then
        ufw allow "$SL_PORT"/tcp 2>/dev/null || true
        log_info "UFW: opened port $SL_PORT"
    elif command -v firewall-cmd &>/dev/null; then
        firewall-cmd --permanent --add-port="$SL_PORT"/tcp 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
        log_info "firewalld: opened port $SL_PORT"
    else
        # Raw iptables
        iptables -I INPUT -p tcp --dport "$SL_PORT" -j ACCEPT 2>/dev/null || true
        log_info "iptables: opened port $SL_PORT"
    fi
}

# ── Start and register tokens ───────────────────────────────
start_and_register() {
    log_info "Starting ShadowLink server..."
    systemctl start "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_info "Server is running!"
    else
        log_error "Server failed to start. Check logs: journalctl -u $SERVICE_NAME -f"
        exit 1
    fi

    log_info "Registering user tokens..."
    for TOKEN in "${TOKENS[@]}"; do
        curl -s -X POST "http://127.0.0.1:$BRIDGE_PORT/api/tokens" \
            -H "X-API-Key: $API_KEY" \
            -H "Content-Type: application/json" \
            -d "{\"token\": \"$TOKEN\", \"max_conns\": $MAX_CONNS}" > /dev/null 2>&1
        log_info "Registered token: $TOKEN"
    done
}

# ── Generate client configs ─────────────────────────────────
generate_client_configs() {
    mkdir -p "$INSTALL_DIR/clients"

    for i in "${!TOKENS[@]}"; do
        TOKEN="${TOKENS[$i]}"
        NUM=$((i + 1))
        CLIENT_FILE="$INSTALL_DIR/clients/client-${NUM}.yaml"

        cat > "$CLIENT_FILE" << EOF
client:
  listen_addr: "127.0.0.1:1080"
  server_addr: "$SERVER_IP:$SL_PORT"
  server_sni: "$SERVER_IP"
  ws_path: "$WS_PATH"
  auth_token: "$TOKEN"
  use_tls: false
  insecure: true
EOF
    done

    log_info "Client configs generated in $INSTALL_DIR/clients/"
}

# ── Save credentials ────────────────────────────────────────
save_credentials() {
    CREDS_FILE="$INSTALL_DIR/credentials.txt"

    cat > "$CREDS_FILE" << EOF
═══════════════════════════════════════════
  ShadowLink Server Credentials
  Generated: $(date)
═══════════════════════════════════════════

Server IP:     $SERVER_IP
Server Port:   $SL_PORT
WS Path:       $WS_PATH
Bridge Port:   $BRIDGE_PORT
API Key:       $API_KEY

── User Tokens ────────────────────────────
EOF

    for i in "${!TOKENS[@]}"; do
        NUM=$((i + 1))
        echo "Token $NUM:  ${TOKENS[$i]}" >> "$CREDS_FILE"
    done

    cat >> "$CREDS_FILE" << EOF

── Useful Commands ────────────────────────
Status:    systemctl status shadowlink
Logs:      journalctl -u shadowlink -f
Restart:   systemctl restart shadowlink
Stop:      systemctl stop shadowlink

Add token: curl -X POST http://127.0.0.1:$BRIDGE_PORT/api/tokens \\
  -H "X-API-Key: $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"token": "NEW-UUID-HERE", "max_conns": 2}'

═══════════════════════════════════════════
EOF

    chmod 600 "$CREDS_FILE"
    log_info "Credentials saved to $CREDS_FILE"
}

# ── Print summary ───────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ShadowLink Setup Complete!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Server:     ${CYAN}$SERVER_IP:$SL_PORT${NC}"
    echo -e "  Status:     ${GREEN}Running${NC}"
    echo -e "  Bridge:     127.0.0.1:$BRIDGE_PORT"
    echo -e "  API Key:    $API_KEY"
    echo ""
    echo -e "  ${YELLOW}── Client Setup ──${NC}"
    echo ""

    for i in "${!TOKENS[@]}"; do
        NUM=$((i + 1))
        echo -e "  User $NUM token: ${CYAN}${TOKENS[$i]}${NC}"
        echo -e "  Config file: $INSTALL_DIR/clients/client-${NUM}.yaml"
        echo ""
    done

    echo -e "  ${YELLOW}── On your local machine ──${NC}"
    echo ""
    echo -e "  1. Download client config:"
    echo -e "     ${CYAN}scp root@$SERVER_IP:$INSTALL_DIR/clients/client-1.yaml ./config.yaml${NC}"
    echo ""
    echo -e "  2. Run client:"
    echo -e "     ${CYAN}./shadowlink-client -config config.yaml${NC}"
    echo ""
    echo -e "  3. Set browser SOCKS5 proxy to: ${CYAN}127.0.0.1:1080${NC}"
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
}

# ── Uninstall ───────────────────────────────────────────────
uninstall() {
    echo -e "${YELLOW}Uninstalling ShadowLink...${NC}"
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    rm -rf "$INSTALL_DIR"
    log_info "ShadowLink uninstalled completely"
    exit 0
}

# ── Main ────────────────────────────────────────────────────
main() {
    print_banner
    check_root

    case "${1:-}" in
        uninstall|remove)
            uninstall
            ;;
        status)
            systemctl status "$SERVICE_NAME"
            exit 0
            ;;
        add-token)
            if [ -z "${2:-}" ]; then
                NEW_TOKEN=$(generate_uuid)
            else
                NEW_TOKEN="$2"
            fi
            STORED_KEY=$(grep 'api_key:' "$CONFIG_FILE" | awk '{print $2}' | tr -d '"')
            STORED_PORT=$(grep 'listen_addr:.*127' "$CONFIG_FILE" | awk -F: '{print $NF}' | tr -d '"' | tr -d ' ')
            MAX_C=${3:-2}
            curl -s -X POST "http://127.0.0.1:$STORED_PORT/api/tokens" \
                -H "X-API-Key: $STORED_KEY" \
                -H "Content-Type: application/json" \
                -d "{\"token\": \"$NEW_TOKEN\", \"max_conns\": $MAX_C}"
            echo ""
            log_info "Added token: $NEW_TOKEN"
            exit 0
            ;;
    esac

    collect_config
    install_binary
    write_config
    install_service
    configure_firewall
    start_and_register
    generate_client_configs
    save_credentials
    print_summary
}

main "$@"
