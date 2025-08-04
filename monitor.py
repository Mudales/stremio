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

class ContainerMonitor:
    """
    Monitors a Docker container for inactivity and stops it, clearing a cache.
    """
    def __init__(self, container_name, inactivity_threshold_minutes=30, check_interval_seconds=30):
        self.client = docker.from_env()
        self.container_name = container_name
        self.inactivity_threshold = timedelta(minutes=inactivity_threshold_minutes)
        self.check_interval = check_interval_seconds
        
        # This will store the time when inactivity was first detected.
        self.inactive_start_time = None
        
        # Regex to find lines indicating a server is idle (e.g., just responding to health checks)
        self.no_activity_pattern = re.compile(r"-> GET /\s*\n")

    def _clear_cache(self):
        """Executes the command to clear the Stremio cache."""
        try:
            logging.info("Clearing Stremio cache...")
            cleanup_command = "rm -rf /home/refa/stremio/stremio-server/stremio-cache/*"
            subprocess.run(cleanup_command, shell=True, check=True, capture_output=True)
            logging.info("Cache cleared successfully.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to clear cache: {e.stderr.decode()}")

    def monitor(self):
        """Main monitoring loop."""
        logging.info(f"Starting monitor for container '{self.container_name}'...")
        while True:
            try:
                container = self.client.containers.get(self.container_name)

                # 1. Only perform checks if the container is actually running
                if container.status == 'running':
                    logs = container.logs(tail=10).decode("utf-8")
                    
                    # 2. Check if the logs show inactivity
                    if self.no_activity_pattern.search(logs):
                        if self.inactive_start_time is None:
                            # Start the inactivity timer
                            self.inactive_start_time = datetime.now()
                            logging.info("Inactivity pattern detected. Starting timer.")
                        
                        elapsed_time = datetime.now() - self.inactive_start_time
                        logging.info(f"Container has been inactive for {elapsed_time}.")

                        # 3. If inactivity threshold is reached, stop the container
                        if elapsed_time >= self.inactivity_threshold:
                            logging.info("Inactivity threshold reached. Stopping container.")
                            container.stop()
                            self._clear_cache()
                            
                            # 4. CRITICAL FIX: Reset the timer after stopping the container
                            self.inactive_start_time = None
                            logging.info("Timer reset. Waiting for container to restart.")

                    else:
                        # Activity was detected, so reset the timer if it was running
                        if self.inactive_start_time is not None:
                            logging.info("Activity detected. Resetting inactivity timer.")
                            self.inactive_start_time = None
                
                else:
                    # If container is stopped, ensure timer is reset and wait
                    if self.inactive_start_time is not None:
                        self.inactive_start_time = None
                    logging.info(f"Container '{self.container_name}' is not running. Waiting...")

            except docker.errors.NotFound:
                logging.warning(f"Container '{self.container_name}' not found. Waiting...")
                # Ensure timer is reset if container is removed
                self.inactive_start_time = None
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")

            time.sleep(self.check_interval)

if __name__ == "__main__":
    # --- Configuration ---
    CONTAINER_TO_MONITOR = 'stremio'
    INACTIVITY_MINUTES = 30
    CHECK_INTERVAL_SECONDS = 30
    
    monitor = ContainerMonitor(
        container_name=CONTAINER_TO_MONITOR,
        inactivity_threshold_minutes=INACTIVITY_MINUTES,
        check_interval_seconds=CHECK_INTERVAL_SECONDS
    )
    monitor.monitor()
