import docker
import time
import shutil
import signal
import os
import logging
from pathlib import Path

# --- Configuration via environment variables ---
CONTAINER_KEYWORD = os.environ.get("MONITOR_CONTAINER_KEYWORD", "stremio")
INACTIVITY_MINUTES = int(os.environ.get("MONITOR_INACTIVITY_MINUTES", "45"))
CHECK_INTERVAL_SECONDS = int(os.environ.get("MONITOR_CHECK_INTERVAL", "30"))
CACHE_DIR = os.environ.get("MONITOR_CACHE_DIR", "/home/refa/stremio/stremio-server/stremio-cache")
# Minimum network bytes received between checks to count as "active"
NETWORK_THRESHOLD_BYTES = int(os.environ.get("MONITOR_NETWORK_THRESHOLD", "1024"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("container-monitor")


class ContainerMonitor:
    def __init__(self):
        self.client = docker.from_env()
        self.inactivity_seconds = INACTIVITY_MINUTES * 60
        self.inactive_since = None
        self.prev_net_rx = None
        self.running = True

        # Graceful shutdown
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, _signum, _frame):
        logger.info("Received shutdown signal, exiting gracefully.")
        self.running = False

    # ---- Helpers ----

    def _find_container(self):
        """Find container by keyword. Returns container or None."""
        for c in self.client.containers.list(all=True):
            if CONTAINER_KEYWORD in c.name:
                return c
        return None

    def _get_network_rx_bytes(self, container):
        """Get total bytes received by the container via Docker stats API."""
        try:
            stats = container.stats(stream=False)
            networks = stats.get("networks", {})
            return sum(net.get("rx_bytes", 0) for net in networks.values())
        except Exception:
            return None

    def _clear_cache(self):
        """Remove stremio cache directory contents."""
        cache_path = Path(CACHE_DIR)
        if not cache_path.exists():
            return
        try:
            for item in cache_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            logger.info("Cache cleared.")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    # ---- Main loop ----

    def run(self):
        logger.info(
            f"Monitor started — keyword='{CONTAINER_KEYWORD}', "
            f"inactivity={INACTIVITY_MINUTES}m, interval={CHECK_INTERVAL_SECONDS}s"
        )

        while self.running:
            try:
                self._tick()
            except docker.errors.NotFound:
                logger.debug("Container disappeared, resetting state.")
                self._reset_state()
            except Exception as e:
                logger.error(f"Unexpected error: {e}")

            time.sleep(CHECK_INTERVAL_SECONDS)

        logger.info("Monitor stopped.")

    def _tick(self):
        container = self._find_container()
        if container is None:
            logger.debug(f"No container matching '{CONTAINER_KEYWORD}' found. Waiting...")
            self._reset_state()
            return

        container.reload()

        if container.status != "running":
            logger.debug(f"Container '{container.name}' is {container.status}.")
            self._reset_state()
            return

        # --- Measure network activity ---
        current_rx = self._get_network_rx_bytes(container)
        if current_rx is None:
            # Stats unavailable, skip this tick
            return

        has_activity = False
        if self.prev_net_rx is not None:
            delta = current_rx - self.prev_net_rx
            has_activity = delta > NETWORK_THRESHOLD_BYTES
        else:
            # First measurement after (re)start — assume active
            has_activity = True

        self.prev_net_rx = current_rx

        # --- Inactivity logic ---
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
                    self._reset_state()

    def _reset_state(self):
        self.inactive_since = None
        self.prev_net_rx = None


if __name__ == "__main__":
    ContainerMonitor().run()
