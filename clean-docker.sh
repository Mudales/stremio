#!/bin/bash

echo "WARNING: This script will remove all Docker containers, images, volumes, and networks."
read -p "Do you want to continue? (y/N): " confirm

if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Stopping all running containers..."
    docker stop $(docker ps -q) 2>/dev/null || echo "No running containers to stop."

    echo "Removing all containers..."
    docker rm $(docker ps -aq) 2>/dev/null || echo "No containers to remove."

    echo "Removing all images..."
    docker rmi $(docker images -q) -f 2>/dev/null || echo "No images to remove."

    echo "Removing all volumes..."
    docker volume rm $(docker volume ls -q) 2>/dev/null || echo "No volumes to remove."

    echo "Pruning all unused Docker resources..."
    docker system prune -af --volumes

    echo "Docker has been cleaned. All containers, images, volumes, and networks have been removed."
else
    echo "Operation canceled by the user."
fi
