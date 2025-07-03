from flask import Flask, redirect, request
import docker
import os
import sys
from pathlib import Path
import subprocess

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
client = docker.from_env()

COMPOSE_FILE_PATH = Path("docker-compose.yml")
SERVICE_NAME = "stremio"

def is_container_running():
    try:
        # List all containers (including stopped ones)
        all_containers = client.containers.list(all=True)
        # Find a container whose name CONTAINS the service name
        for container in all_containers:
            if CONTAINER_NAME in container.name and container.status == 'running':
                logger.info(f"Found running container: {container.name}")
                return True
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
        # Run the command, capturing output and errors
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"docker-compose stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"docker-compose stderr: {result.stderr}")
        return True
    except FileNotFoundError:
        logger.error("'docker-compose' command not found. Is it installed?")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Error starting container with docker-compose: {e.stderr}")
        return False


@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def catch_all(path):
    if not is_container_running():
        logger.info("Container not running. Starting...")
        if not start_container():
            return "Failed to start container", 500
        logger.info("Container started successfully")

    # Redirect to HTTPS (443)
    scheme = 'https'
    host = request.headers.get('Host', '').split(':')[0]
    return redirect(f"{scheme}://{host}/{path}", code=307)

if __name__ == "__main__":
    # Check if running as root (required for port 80)
    if os.geteuid() != 0:
        logger.error("This script must be run as root to bind to port 80")
        sys.exit(1)

    app.run(host='0.0.0.0', port=80)
