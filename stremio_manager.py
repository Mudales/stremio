"""
Stremio Manager — single process that handles:
  1. HTTP listener (port 80) — starts container on demand, redirects to HTTPS
  2. Inactivity monitor — stops container + clears cache after idle timeout
"""

import os
import sys
import subprocess
import threading
import shutil
import signal
import time
import logging
import urllib.request
from pathlib import Path

import docker
from flask import Flask, redirect, request

# =============================================================================
# Configuration (all overridable via environment variables)
# =============================================================================
INSTALL_DIR = Path(os.environ.get("STREMIO_INSTALL_DIR", Path(__file__).parent))
COMPOSE_FILE = Path(os.environ.get("STREMIO_COMPOSE_FILE", INSTALL_DIR / "docker-compose.yml"))
CONTAINER_KEYWORD = os.environ.get("STREMIO_CONTAINER_KEYWORD", "stremio")
CACHE_DIR = Path(os.environ.get("STREMIO_CACHE_DIR", INSTALL_DIR / "stremio-server" / "stremio-cache"))
LISTEN_PORT = int(os.environ.get("STREMIO_LISTEN_PORT", "80"))
HEALTH_URL = os.environ.get("STREMIO_HEALTH_URL", "http://localhost:11470/")
STARTUP_TIMEOUT = int(os.environ.get("STREMIO_STARTUP_TIMEOUT", "60"))
INACTIVITY_MINUTES = int(os.environ.get("STREMIO_INACTIVITY_MINUTES", "45"))
CHECK_INTERVAL = int(os.environ.get("STREMIO_CHECK_INTERVAL", "30"))
NETWORK_THRESHOLD = int(os.environ.get("STREMIO_NETWORK_THRESHOLD", "1024"))

# =============================================================================
# Logging
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("stremio-manager")

# =============================================================================
# Shared Docker client & helpers
# =============================================================================
client = docker.from_env()


def _detect_compose_cmd():
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0:
        return ["docker", "compose"]
    return ["docker-compose"]


COMPOSE_CMD = _detect_compose_cmd()


def find_container():
    """Find a container whose name contains the keyword."""
    try:
        for c in client.containers.list(all=True):
            if CONTAINER_KEYWORD in c.name:
                return c
    except Exception as e:
        logger.error(f"Docker error: {e}")
    return None


def is_container_running():
    c = find_container()
    return c is not None and c.status == "running"


# =============================================================================
# Container startup (used by the HTTP listener)
# =============================================================================
_start_lock = threading.Lock()


def wait_for_healthy(timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3):
                return True
        except Exception:
            time.sleep(1)
    return False


def start_container():
    """Start via docker compose (thread-safe, with health polling)."""
    if not _start_lock.acquire(blocking=False):
        logger.info("Startup already in progress, waiting...")
        with _start_lock:
            return is_container_running()

    try:
        if not COMPOSE_FILE.exists():
            logger.error(f"Compose file not found: {COMPOSE_FILE}")
            return False

        cmd = COMPOSE_CMD + ["-f", str(COMPOSE_FILE), "up", "-d"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Compose failed: {result.stderr}")
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


# =============================================================================
# Flask app (HTTP listener)
# =============================================================================
app = Flask(__name__)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    if not is_container_running():
        logger.info("Container not running, starting...")
        if not start_container():
            return "Failed to start Stremio container.", 503

    host = request.headers.get("Host", "").split(":")[0]
    return redirect(f"https://{host}/{path}", code=307)


# =============================================================================
# Inactivity monitor (runs in a background thread)
# =============================================================================
class InactivityMonitor:
    def __init__(self):
        self.inactivity_seconds = INACTIVITY_MINUTES * 60
        self.inactive_since = None
        self.prev_net_rx = None

    def _get_network_rx(self, container):
        try:
            stats = container.stats(stream=False)
            networks = stats.get("networks", {})
            return sum(net.get("rx_bytes", 0) for net in networks.values())
        except Exception:
            return None

    def _clear_cache(self):
        if not CACHE_DIR.exists():
            return
        try:
            for item in CACHE_DIR.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            logger.info("Cache cleared.")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def _reset(self):
        self.inactive_since = None
        self.prev_net_rx = None

    def _tick(self):
        container = find_container()
        if container is None or container.status != "running":
            self._reset()
            return

        current_rx = self._get_network_rx(container)
        if current_rx is None:
            return

        if self.prev_net_rx is not None:
            has_activity = (current_rx - self.prev_net_rx) > NETWORK_THRESHOLD
        else:
            has_activity = True  # first check after start — assume active

        self.prev_net_rx = current_rx

        if has_activity:
            if self.inactive_since is not None:
                logger.info("Network activity detected, resetting inactivity timer.")
            self.inactive_since = None
        else:
            if self.inactive_since is None:
                self.inactive_since = time.monotonic()
                logger.info("No network activity. Starting inactivity timer.")
            else:
                elapsed = time.monotonic() - self.inactive_since
                remaining = self.inactivity_seconds - elapsed
                logger.info(f"Inactive for {elapsed:.0f}s ({remaining:.0f}s until shutdown).")

                if elapsed >= self.inactivity_seconds:
                    logger.warning(f"Inactivity threshold reached. Stopping '{container.name}'.")
                    container.stop(timeout=15)
                    self._clear_cache()
                    self._reset()

    def run_forever(self):
        logger.info(
            f"Monitor thread started — inactivity={INACTIVITY_MINUTES}m, "
            f"interval={CHECK_INTERVAL}s, threshold={NETWORK_THRESHOLD}B"
        )
        while True:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                self._reset()
            time.sleep(CHECK_INTERVAL)


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.error("Must run as root to bind to port 80.")
        sys.exit(1)

    # Start monitor in a daemon thread
    monitor = InactivityMonitor()
    monitor_thread = threading.Thread(target=monitor.run_forever, daemon=True)
    monitor_thread.start()

    # Run Flask (blocks main thread)
    logger.info(f"HTTP listener starting on port {LISTEN_PORT}")
    app.run(host="0.0.0.0", port=LISTEN_PORT, debug=False)
