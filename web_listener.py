from flask import Flask, redirect, request
import docker
import os
import sys
from pathlib import Path
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
        containers = client.containers.list(
            filters={"name": f".*{SERVICE_NAME}.*"}
        )
        return len(containers) > 0
    except docker.errors.APIError as e:
        logger.error(f"Docker API error: {e}")
        return False

def start_container():
    try:
        if not COMPOSE_FILE_PATH.exists():
            logger.error(f"Docker compose file not found at {COMPOSE_FILE_PATH}")
            return False

        # Using docker-compose command through os.system as python-docker doesn't
        # directly support compose v2
        result = os.system(f"docker-compose -f {COMPOSE_FILE_PATH} up -d")
        return result == 0
    except Exception as e:
        logger.error(f"Error starting container: {e}")
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
