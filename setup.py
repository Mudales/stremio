#!/bin/bash

# ==============================================================================
# Stremio Smart Server - Installation Script
# ==============================================================================
# This script automates the full setup for the Stremio project.
# It creates all necessary files, services, and directories.
# ==============================================================================

# --- Configuration ---
# The main directory where all project files will be stored.
INSTALL_DIR="/home/refa/stremio"


# --- Functions ---
print_header() {
    echo "===================================================="
    echo "  $1"
    echo "===================================================="
}

print_success() {
    # Green color
    echo -e "\e[32m✔ $1\e[0m"
}

print_error() {
    # Red color
    echo -e "\e[31m✖ $1\e[0m"
    exit 1
}


# --- Main Execution ---

# 1. Check for Root Privileges
print_header "Checking for root privileges"
if [ "$EUID" -ne 0 ]; then
  print_error "This script must be run as root. Please use 'sudo ./install.sh'"
fi
print_success "Running as root."


# 2. Check Dependencies
print_header "Checking for dependencies"
command -v docker >/dev/null 2>&1 || print_error "Docker is not installed. Please install it first."
print_success "Docker is installed."

command -v docker-compose >/dev/null 2>&1 || print_error "Docker Compose is not installed. Please install it first."
print_success "Docker Compose is installed."

command -v python3 >/dev/null 2>&1 || print_error "Python 3 is not installed. Please install it first."
print_success "Python 3 is installed."

python3 -c "import docker; import flask" >/dev/null 2>&1 || {
    echo "Required Python libraries (docker, flask) not found. Attempting to install..."
    pip3 install docker flask || print_error "Failed to install Python libraries. Please install them manually ('pip3 install docker flask')."
}
print_success "Required Python libraries are installed."


# 3. Create Directories
print_header "Creating installation directories"
mkdir -p "${INSTALL_DIR}/monitor"
if [ $? -eq 0 ]; then
    print_success "Directory structure created at $INSTALL_DIR"
else
    print_error "Failed to create directories."
fi


# 4. Create Project Files
print_header "Writing project files"

# Dockerfile (using the final corrected version)
cat << 'EOF' > "${INSTALL_DIR}/Dockerfile"
# --- Stage 1: The Builder ---
FROM node:14-slim AS builder
WORKDIR /build
# Install tools needed only for the build process
RUN apt-get update && apt-get install -y --no-install-recommends wget python3 openssl
# Download Stremio server
RUN wget --no-check-certificate -O server.js "https://dl.strem.io/server/v4.20.8/desktop/server.js"
# Create SSL certificates
RUN mkdir ssl && openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
   -keyout ssl/server.key -out ssl/server.crt \
   -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"
# Copy and run the fix script
COPY fix.py .
RUN python3 fix.py

# --- Stage 2: The Final Image ---
FROM node:14-slim
WORKDIR /stremio
# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl procps wget && \
    wget --no-check-certificate https://repo.jellyfin.org/archive/ffmpeg/debian/4.4.1-4/jellyfin-ffmpeg_4.4.1-4-buster_$(dpkg --print-architecture).deb -O jellyfin-ffmpeg.deb && \
    apt-get install -y ./jellyfin-ffmpeg.deb && \
    rm jellyfin-ffmpeg.deb && \
    apt-get remove -y wget && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
# Copy artifacts from the builder stage
COPY --from=builder /build/server.js .
COPY --from=builder /build/ssl ./ssl
# Set up environment
RUN mkdir -p /root/.stremio-server
EXPOSE 11470 12470
ENV FFMPEG_BIN=/usr/lib/jellyfin-ffmpeg/ffmpeg \
    FFPROBE_BIN=/usr/lib/jellyfin-ffmpeg/ffprobe
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:11470/ || exit 1
ENTRYPOINT ["node", "server.js"]
EOF
print_success "Dockerfile created."

# docker-compose.yml
cat << 'EOF' > "${INSTALL_DIR}/docker-compose.yml"
version: '3.8'
services:
  stremio:
    build: .
    container_name: stremio_server
    ports:
      - "11470:11470"
      - "443:12470"
    volumes:
      - ./stremio-server:/root/.stremio-server
    restart: always
EOF
print_success "docker-compose.yml created."

# fix.py
cat << 'EOF' > "${INSTALL_DIR}/fix.py"
replacement = """
        try {
            var fs = require('fs');
            var https = require('https');
            _cr = {
                key: fs.readFileSync('./ssl/server.key', 'utf8'),
                cert: fs.readFileSync('./ssl/server.crt', 'utf8')
            };
        } catch (e) {
            console.error("Failed to load SSL cert:", e);
            _cr = { };
        }
        var sserver = https.createServer(_cr, app);
"""

with open("server.js", "r") as file:
    lines = file.readlines()

with open("server.js", "w") as file:
    for line in lines:
        if "var sserver = https.createServer(app);" in line:
            file.write(replacement + "\n")
        else:
            file.write(line)
EOF
print_success "fix.py created."

# web_listener.py
cat << 'EOF' > "${INSTALL_DIR}/web_listener.py"
from flask import Flask, redirect, request
import docker
import os
import sys
from pathlib import Path
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)
client = docker.from_env()

COMPOSE_FILE_PATH = Path(__file__).parent / "docker-compose.yml"
CONTAINER_NAME = "stremio_server"

def is_container_running():
    try:
        container = client.containers.get(CONTAINER_NAME)
        return container.status == 'running'
    except docker.errors.NotFound:
        return False
    except Exception as e:
        logger.error(f"Error checking container status: {e}")
        return False

def start_container():
    try:
        if not COMPOSE_FILE_PATH.exists():
            logger.error(f"Docker compose file not found at {COMPOSE_FILE_PATH}")
            return False
        command = ["docker-compose", "-f", str(COMPOSE_FILE_PATH), "up", "-d", "--build"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"docker-compose up stdout: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error starting container with docker-compose: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during container start: {e}")
        return False

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if not is_container_running():
        logger.info("Container not running. Starting...")
        if not start_container():
            return "Failed to start Stremio container.", 500
        logger.info("Container started successfully.")
    scheme = 'https'
    host = request.headers.get('Host', '').split(':')[0]
    return redirect(f"{scheme}://{host}/{path}", code=307)

if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.error("This script must be run as root to bind to port 80.")
        sys.exit(1)
    app.run(host='0.0.0.0', port=80, debug=False)
EOF
print_success "web_listener.py created."


# monitor.py
cat << 'EOF' > "${INSTALL_DIR}/monitor/monitor.py"
import docker
import time
import re
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ContainerMonitor:
    def __init__(self, container_name, inactivity_threshold_minutes=15, check_interval_seconds=60):
        self.client = docker.from_env()
        self.container_name = container_name
        self.inactivity_threshold = timedelta(minutes=inactivity_threshold_minutes)
        self.check_interval = check_interval_seconds
        self.last_activity_time = None
        self.activity_pattern = re.compile(r"HTTP request: |-> GET /manifest.json|-> GET /stream/")

    def get_container(self):
        try:
            return self.client.containers.get(self.container_name)
        except docker.errors.NotFound:
            logger.info(f"Container '{self.container_name}' not found. Assuming it is stopped.")
            return None
        except Exception as e:
            logger.error(f"Docker API error while getting container: {e}")
            return None

    def check_for_activity(self, container):
        try:
            since_time = datetime.utcnow() - timedelta(seconds=self.check_interval + 5)
            logs = container.logs(since=since_time, stdout=True, stderr=True).decode("utf-8", errors='ignore')
            if self.activity_pattern.search(logs):
                logger.info("Activity detected.")
                return True
            else:
                logger.info("No significant activity detected.")
                return False
        except Exception as e:
            logger.error(f"Could not retrieve logs for container {self.container_name}: {e}")
            return True

    def monitor(self):
        logger.info(f"Starting monitor for '{self.container_name}'...")
        while True:
            container = self.get_container()
            if container and container.status == 'running':
                if self.last_activity_time is None:
                    self.last_activity_time = datetime.now()
                if self.check_for_activity(container):
                    self.last_activity_time = datetime.now()
                else:
                    elapsed_inactive_time = datetime.now() - self.last_activity_time
                    logger.info(f"Container has been inactive for {elapsed_inactive_time.total_seconds():.0f} seconds.")
                    if elapsed_inactive_time >= self.inactivity_threshold:
                        logger.warning(f"Inactivity threshold reached. Stopping container '{self.container_name}'...")
                        try:
                            container.stop()
                            logger.info("Container stopped successfully.")
                            self.last_activity_time = None
                        except Exception as e:
                            logger.error(f"Failed to stop container: {e}")
            else:
                if self.last_activity_time is not None:
                    logger.info("Container is stopped. Resetting activity timer.")
                    self.last_activity_time = None
            time.sleep(self.check_interval)

if __name__ == "__main__":
    monitor = ContainerMonitor(
        container_name='stremio_server',
        inactivity_threshold_minutes=15,
        check_interval_seconds=60
    )
    monitor.monitor()
EOF
print_success "monitor.py created."


# 5. Create and install Systemd Service Files
print_header "Installing systemd services"

# docker-listener.service
cat << EOF > /etc/systemd/system/docker-listener.service
[Unit]
Description=Stremio Docker Web Listener Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/web_listener.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# container-monitor.service
cat << EOF > /etc/systemd/system/container-monitor.service
[Unit]
Description=Stremio Docker Container Activity Monitor
After=docker.service
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/monitor/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
print_success "Service files created in /etc/systemd/system/."


# 6. Enable and Start Services
print_header "Enabling and starting services"
systemctl daemon-reload
print_success "Systemd daemon reloaded."

systemctl enable docker-listener.service container-monitor.service
print_success "Services enabled to start on boot."

systemctl restart docker-listener.service container-monitor.service
print_success "Services started."


# --- Final Instructions ---
print_header "Installation Complete!"
echo "The Stremio smart management system has been installed and started."
echo
echo "To check the status of the services, you can run:"
echo "  sudo systemctl status docker-listener.service"
echo "  sudo systemctl status container-monitor.service"
echo
echo "To see the logs in real-time, use:"
echo "  sudo journalctl -u docker-listener -f"
echo "  sudo journalctl -u container-monitor -f"
echo
echo "Try accessing your server now at: http://<your_server_ip>"
