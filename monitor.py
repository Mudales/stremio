import docker
import time
import requests
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContainerMonitor:
    def __init__(self, container_name, inactivity_threshold_minutes=30, check_interval_seconds=60):
        self.client = docker.from_env()
        self.container_name = container_name
        self.inactivity_threshold = timedelta(minutes=inactivity_threshold_minutes)
        self.check_interval = check_interval_seconds
        
    def get_container(self):
        try:
            return self.client.containers.get(self.container_name)
        except docker.errors.NotFound:
            logger.error(f"Container {self.container_name} not found")
            return None
            
    def check_app_activity(self, container):
        # Get container IP and port mapping
        container_info = container.attrs
        networks = container_info['NetworkSettings']['Networks']
        container_ip = next(iter(networks.values()))['IPAddress']
        
        # Get exposed ports
        ports = container_info['NetworkSettings']['Ports']
        if not ports:
            logger.error("No ports exposed")
            return False
            
        # Try the first exposed port
        port = next(iter(ports.keys())).split('/')[0]
        
        try:
            response = requests.get(f"http://{container_ip}:{port}/health")
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
            
    def monitor(self):
        logger.info(f"Starting monitoring of container {self.container_name}")
        last_activity = datetime.now()
        
        while True:
            container = self.get_container()
            if not container:
                break
                
            if self.check_app_activity(container):
                last_activity = datetime.now()
                logger.info("Activity detected, resetting timer")
            else:
                time_inactive = datetime.now() - last_activity
                if time_inactive >= self.inactivity_threshold:
                    logger.info(f"No activity detected for {time_inactive}, stopping container")
                    container.stop()
                    break
                    
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
            inactivity_threshold_minutes=30,
            check_interval_seconds=60
        )
        monitor.monitor()
    else:
        logger.error(f'Cannot find container with name "{container_name}"')
