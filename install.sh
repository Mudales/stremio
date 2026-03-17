#!/bin/bash
set -e

# ==============================================================================
# Stremio Smart Server - Installation Script
# ==============================================================================
# Installs the systemd service and builds the Docker image.
# Project files (Dockerfile, stremio_manager.py, etc.) are used from the repo.
# ==============================================================================

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Helpers ---
print_header() { echo -e "\n====  $1  ===="; }
print_success() { echo -e "\e[32m✔ $1\e[0m"; }
print_error()   { echo -e "\e[31m✖ $1\e[0m"; exit 1; }

# --- 1. Root check ---
print_header "Checking prerequisites"
[ "$EUID" -eq 0 ] || print_error "Run as root: sudo ./install.sh"
print_success "Running as root"

# --- 2. Dependencies ---
command -v docker  >/dev/null 2>&1 || print_error "Docker not installed"
command -v python3 >/dev/null 2>&1 || print_error "Python 3 not installed"

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    print_error "Docker Compose not installed (tried 'docker compose' and 'docker-compose')"
fi
print_success "Docker, Compose ($COMPOSE_CMD), Python 3 found"

python3 -c "import docker; import flask" >/dev/null 2>&1 || {
    echo "Installing Python libraries (docker, flask)..."
    pip3 install docker flask || print_error "Failed to install Python libraries"
}
print_success "Python libraries ready"

# --- 3. Ensure directories ---
mkdir -p "${INSTALL_DIR}/stremio-server/stremio-cache"

# --- 4. Install systemd service ---
print_header "Installing systemd service"

# Clean up old services from previous versions
for OLD_SVC in docker-listener container-monitor; do
    if systemctl list-unit-files "${OLD_SVC}.service" >/dev/null 2>&1; then
        systemctl stop "${OLD_SVC}.service" 2>/dev/null || true
        systemctl disable "${OLD_SVC}.service" 2>/dev/null || true
        rm -f "/etc/systemd/system/${OLD_SVC}.service"
    fi
done

# Stop current service if running
systemctl stop stremio-manager.service 2>/dev/null || true

cat << EOF > /etc/systemd/system/stremio-manager.service
[Unit]
Description=Stremio Manager (on-demand startup + auto-shutdown)
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/stremio_manager.py
Restart=on-failure
RestartSec=5

# Uncomment to override defaults:
# Environment=STREMIO_LISTEN_PORT=80
# Environment=STREMIO_INACTIVITY_MINUTES=45
# Environment=STREMIO_CHECK_INTERVAL=30
# Environment=STREMIO_STARTUP_TIMEOUT=60

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable stremio-manager.service
systemctl restart stremio-manager.service
print_success "stremio-manager.service installed and started"

# --- 5. Build Docker image ---
print_header "Building Docker image"
cd "${INSTALL_DIR}"
$COMPOSE_CMD build
print_success "Image built"

# --- Done ---
print_header "Done!"
echo "Service:   stremio-manager"
echo "Status:    sudo systemctl status stremio-manager"
echo "Logs:      sudo journalctl -u stremio-manager -f"
echo "Access:    http://<your-ip> (auto-starts container, redirects to HTTPS)"
