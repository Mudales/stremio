import os
import sys
import subprocess
import threading
import time
import logging
from pathlib import Path

import docker
from flask import Flask, redirect, request

# --- Configuration via environment variables ---
COMPOSE_FILE_PATH = Path(os.environ.get(
    "LISTENER_COMPOSE_FILE",
    str(Path(__file__).parent / "docker-compose.yml"),
))
CONTAINER_KEYWORD = os.environ.get("LISTENER_CONTAINER_KEYWORD", "stremio")
HEALTH_URL = os.environ.get("LISTENER_HEALTH_URL", "http://localhost:11470/")
STARTUP_TIMEOUT = int(os.environ.get("LISTENER_STARTUP_TIMEOUT", "60"))
LISTEN_PORT = int(os.environ.get("LISTENER_PORT", "80"))

# Detect docker compose (plugin) vs docker-compose (standalone)
def _detect_compose_cmd():
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0:
        return ["docker", "compose"]
    return ["docker-compose"]

COMPOSE_CMD = _detect_compose_cmd()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("web-listener")

app = Flask(__name__)
client = docker.from_env()

# Lock to prevent multiple simultaneous startup attempts
_start_lock = threading.Lock()


def is_container_running():
    """Check if a container matching the keyword is running."""
    try:
        for c in client.containers.list(filters={"status": "running"}):
            if CONTAINER_KEYWORD in c.name:
                return True
        return False
    except Exception as e:
        logger.error(f"Docker error: {e}")
        return False


def wait_for_healthy(timeout):
    """Poll the container health endpoint until it responds or timeout."""
    import urllib.request
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3):
                return True
        except Exception:
            time.sleep(1)
    return False


def start_container():
    """Start the stremio container via docker-compose (thread-safe)."""
    if not _start_lock.acquire(blocking=False):
        # Another request is already starting the container — just wait
        logger.info("Startup already in progress, waiting...")
        with _start_lock:
            return is_container_running()

    try:
        if not COMPOSE_FILE_PATH.exists():
            logger.error(f"Compose file not found: {COMPOSE_FILE_PATH}")
            return False

        cmd = COMPOSE_CMD + ["-f", str(COMPOSE_FILE_PATH), "up", "-d"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"docker-compose failed: {result.stderr}")
            return False

        logger.info("Container starting, waiting for healthy response...")
        if not wait_for_healthy(STARTUP_TIMEOUT):
            logger.error("Container did not become healthy in time.")
            return False

        logger.info("Container is healthy.")
        return True
    except Exception as e:
        logger.error(f"Startup error: {e}")
        return False
    finally:
        _start_lock.release()


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    if not is_container_running():
        logger.info("Container not running, starting...")
        if not start_container():
            return "Failed to start Stremio container.", 503

    host = request.headers.get("Host", "").split(":")[0]
    return redirect(f"https://{host}/{path}", code=307)


if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.error("Must run as root to bind to port 80.")
        sys.exit(1)
    app.run(host="0.0.0.0", port=LISTEN_PORT, debug=False)
