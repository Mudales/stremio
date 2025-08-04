import docker
import time
import subprocess
import re
import logging
from datetime import datetime, timedelta

# --- Basic Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ContainerMonitor:
    def __init__(self, container_name, inactivity_threshold_minutes=30, check_interval_seconds=30):
        self.client = docker.from_env()
        self.container_name = container_name
        self.inactivity_threshold = timedelta(minutes=inactivity_threshold_minutes)
        self.check_interval = check_interval_seconds
        self.inactive_start_time = None
        self.no_activity_pattern = re.compile(r"-> GET /\s*\n")
        self.waiting_for_restart = False

    def _clear_cache(self):
        try:
            logger.info("Clearing Stremio cache...")
            subprocess.run(
                "rm -rf /home/refa/stremio/stremio-server/stremio-cache/*",
                shell=True, check=True, capture_output=True
            )
            logger.info("Cache cleared successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clear cache: {e.stderr.decode()}")

    def monitor(self):
        logger.info(f"Starting monitor for container '{self.container_name}'...")

        while True:
            try:
                container = self.client.containers.get(self.container_name)
                container.reload()  # Refresh container status

                if container.status == 'running':
                    if self.waiting_for_restart:
                        logger.info("Container restarted. Resuming monitoring.")
                        self.waiting_for_restart = False
                        self.inactive_start_time = None

                    logs = container.logs(tail=10)
                   logs = container.logs(tail=10)

                if logs:
                    logs = logs.decode("utf-8")
                    logger.debug(f"Container logs:\n{logs}")
                
                    # Reset no-log timer
                    if self.no_log_start_time is not None:
                        logger.info("Logs received. Resetting no-log timer.")
                        self.no_log_start_time = None
                
                    # Check for activity pattern
                    if self.no_activity_pattern.search(logs):
                        if self.inactive_start_time is None:
                            self.inactive_start_time = datetime.now()
                            logger.info("Inactivity pattern detected. Starting timer.")
                        else:
                            elapsed = datetime.now() - self.inactive_start_time
                            logger.info(f"Inactivity duration: {elapsed}")
                            if elapsed >= self.inactivity_threshold:
                                logger.info("Inactivity threshold reached. Stopping container.")
                                container.stop()
                                self._clear_cache()
                                self.waiting_for_restart = True
                    else:
                        if self.inactive_start_time is not None:
                            logger.info("Activity detected. Resetting inactivity timer.")
                            self.inactive_start_time = None
                
                else:
                    # No logs at all received
                    if self.no_log_start_time is None:
                        self.no_log_start_time = datetime.now()
                        logger.info("No logs received. Starting no-log timer.")
                    else:
                        silent_duration = datetime.now() - self.no_log_start_time
                        logger.info(f"No logs for {silent_duration}.")
                
                        if silent_duration >= self.inactivity_threshold:
                            logger.info("No-log threshold reached. Stopping container.")
                            container.stop()
                            self._clear_cache()
                            self.waiting_for_restart = True

                else:
                    logger.debug(f"Container '{self.container_name}' is not running.")
                    if not self.waiting_for_restart:
                        self.inactive_start_time = None

            except docker.errors.NotFound:
                logger.error(f"Container '{self.container_name}' not found. Exiting.")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")

            time.sleep(self.check_interval)

if __name__ == "__main__":
    container_name_to_find = 'stremio'
    INACTIVITY_MINUTES = 30
    CHECK_INTERVAL_SECONDS = 30

    client = docker.from_env()
    containers = client.containers.list(all=True)

    target_container = next((c for c in containers if container_name_to_find in c.name), None)

    if target_container:
        logger.info(f"Found container: {target_container.name}")
        monitor = ContainerMonitor(
            container_name=target_container.name,
            inactivity_threshold_minutes=INACTIVITY_MINUTES,
            check_interval_seconds=CHECK_INTERVAL_SECONDS
        )
        monitor.monitor()
    else:
        logger.error(f'Cannot find a container with "{container_name_to_find}" in its name.')
