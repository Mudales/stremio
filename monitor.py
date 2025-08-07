import docker
import time
import subprocess
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
        self.waiting_for_restart = False
        # ### שינוי: הוספת משתנה למעקב אחר זמן הבדיקה האחרון ###
        self.last_log_timestamp = datetime.now()

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
        # הגדרת זמן התחלה ראשוני
        self.last_log_timestamp = datetime.now()

        while True:
            try:
                container = self.client.containers.get(self.container_name)
                container.reload()  # Refresh container status

                if container.status == 'running':
                    if self.waiting_for_restart:
                        logger.info("Container restarted. Resuming monitoring.")
                        self.waiting_for_restart = False
                        self.inactive_start_time = None
                        self.last_log_timestamp = datetime.now() # איפוס הזמן לאחר ריסטארט

                    # ### שינוי מרכזי: בדיקת לוגים חדשים במקום בדיקת תוכן ###
                    since_time = self.last_log_timestamp
                    # עדכון חותמת הזמן *לפני* קריאת הלוגים כדי לא לפספס כלום
                    self.last_log_timestamp = datetime.now()
                    
                    new_logs = container.logs(since=since_time)

                    if not new_logs:
                        # אין לוגים חדשים = חוסר פעילות
                        if self.inactive_start_time is None:
                            self.inactive_start_time = datetime.now()
                            logger.info("No new logs detected. Starting inactivity timer.")
                        else:
                            elapsed = datetime.now() - self.inactive_start_time
                            logger.info(f"Container inactive for {elapsed}.")
                            if elapsed >= self.inactivity_threshold:
                                logger.warning("Inactivity threshold reached. Stopping container.")
                                container.stop()
                                self._clear_cache()
                                self.waiting_for_restart = True
                    else:
                        # יש לוגים חדשים = פעילות
                        if self.inactive_start_time is not None:
                            logger.info("New activity detected. Resetting inactivity timer.")
                            self.inactive_start_time = None
                        # אפשר להוסיף הדפסה של הלוגים החדשים לדיבאג
                        # logger.debug(f"New logs: {new_logs.decode('utf-8', errors='ignore').strip()}")

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
