import docker
import time, subprocess 
import re
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContainerMonitor:
    def __init__(self, container_name, inactivity_threshold_minutes=30, check_interval_seconds=10):
        self.client = docker.from_env()
        self.container_name = container_name
        self.inactivity_threshold = timedelta(minutes=inactivity_threshold_minutes)
        self.check_interval = check_interval_seconds
        self.inactive_start_time = None
        self.no_activity_pattern = re.compile(r"(?:\n|^)-> GET /\s*")

    def get_container(self):
        try:
            return self.client.containers.get(self.container_name)
        except docker.errors.NotFound:
            logger.error(f"Container {self.container_name} not found")
            return None

    def check_logs_for_inactivity(self, container):
        logs = container.logs(tail=20, stderr=False, stdout=True).decode("utf-8")
        if self.no_activity_pattern.findall(logs):
            logger.info("Detected repeated inactivity pattern in logs.")
            return True
        return False

    def monitor(self):
        logger.info(f"Monitoring container {self.container_name}...")
        
        while True:
            container = self.get_container()
            if not container:
                break  # Exit if the container is not found
            
            if self.check_logs_for_inactivity(container):
                if self.inactive_start_time is None:
                    self.inactive_start_time = datetime.now()
                
                elapsed_inactive_time = datetime.now() - self.inactive_start_time
                logger.info(f"Inactivity detected for {elapsed_inactive_time}")

                if elapsed_inactive_time >= self.inactivity_threshold:
                    logger.info(f"No activity for {elapsed_inactive_time}, stopping container...")
                    container.stop()
                    # clear the cache
                    try:
                        logger.info("Clearing Stremio cache...")
                        cleanup_command = "rm -rf /home/refa/stremio/stremio-server/stremio-cache/*"
                        subprocess.run(cleanup_command, shell=True, check=True)
                        logger.info("Cache cleared successfully.")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to clear cache: {e}")
                    # break
            else:
                self.inactive_start_time = None  # Reset if activity is detected

            time.sleep(self.check_interval)


if __name__ == "__main__":
    container_name = 'stremio'

    client = docker.from_env()
    containers = client.containers.list()

    target_container = None
    for container in containers:
        if container_name in container.name:
            target_container = container
            logger.info(f"Found container: {container.name}")
            break

    if target_container:
        monitor = ContainerMonitor(
            container_name=target_container.name,
            inactivity_threshold_minutes=30,  # Adjust as needed
            check_interval_seconds=30  # Check logs every 30 seconds
        )
        monitor.monitor()
    else:
        logger.error(f'Cannot find container with name "{container_name}"')
