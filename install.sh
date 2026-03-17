#!/bin/bash
set -e

# ==============================================================================
# Stremio Smart Server - Installation Script
# ==============================================================================
# Installs systemd services and builds the Docker image.
# Project files (Dockerfile, monitor.py, etc.) are used directly from the repo.
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

# Detect docker compose (plugin) vs docker-compose (standalone)
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

# --- 4. Install systemd services ---
print_header "Installing systemd services"

# Stop old services if running
systemctl stop docker-listener.service container-monitor.service 2>/dev/null || true

cat << EOF > /etc/systemd/system/docker-listener.service
[Unit]
Description=Stremio Web Listener (on-demand startup)
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/web_listener.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat << EOF > /etc/systemd/system/container-monitor.service
[Unit]
Description=Stremio Container Monitor (auto-shutdown)
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/monitor.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable docker-listener.service container-monitor.service
systemctl restart docker-listener.service container-monitor.service
print_success "Services installed and started"

# --- 5. Build Docker image ---
print_header "Building Docker image"
cd "${INSTALL_DIR}"
$COMPOSE_CMD build
print_success "Image built"

# --- Done ---
print_header "Done!"
echo "Services:  docker-listener, container-monitor"
echo "Status:    sudo systemctl status docker-listener container-monitor"
echo "Logs:      sudo journalctl -u docker-listener -u container-monitor -f"
echo "Access:    http://<your-ip> (auto-starts container, redirects to HTTPS)"
