from flask import Flask, redirect, request
import docker
import os
import sys
from pathlib import Path
import logging
import subprocess
import time

# Add this constant at the top of the file with your other constants
IMAGE_NAME = "stremio_stremio" # <-- !!! עדכן לשם האימג' המדויק שלך



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

        # Check if the image needs to be built
        try:
            client.images.get(IMAGE_NAME)
            logger.info(f"Image '{IMAGE_NAME}' already exists. Skipping build.")
            # Command without build
            command = ["docker-compose", "-f", str(COMPOSE_FILE_PATH), "up", "-d"]
        except docker.errors.ImageNotFound:
            logger.info(f"Image '{IMAGE_NAME}' not found. Building...")
            # Command with build
            command = ["docker-compose", "-f", str(COMPOSE_FILE_PATH), "up", "-d", "--build"]

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Error starting container with docker-compose: {result.stderr}")
            return False
        
        logger.info(f"docker-compose up stdout: {result.stdout}")
        time.sleep(5) # Give container time to start
        return True
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
