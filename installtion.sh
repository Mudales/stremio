#!/bin/bash

# Set default values for variables
NODE_VERSION=${NODE_VERSION:-16}
VERSION=${VERSION:-master}
BUILD=${BUILD:-desktop}
JELLYFIN_VERSION=${JELLYFIN_VERSION:-4.4.1-4}
WORKDIR=/stremio

# Create the working directory
mkdir -p "$WORKDIR"
cd "$WORKDIR"

# Install Node.js
echo "Installing Node.js version $NODE_VERSION"
curl -sL https://deb.nodesource.com/setup_$NODE_VERSION.x | bash -
apt-get install -y nodejs

# Generate SSL certificates
echo "Generating SSL certificates"
mkdir -p ssl
openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout ssl/server.key -out ssl/server.crt -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"

# Update apt and install wget
echo "Updating apt and installing wget"
apt-get update -y
apt-get install -y wget

# Download and install Jellyfin ffmpeg
echo "Downloading and installing Jellyfin ffmpeg version $JELLYFIN_VERSION"
wget https://repo.jellyfin.org/archive/ffmpeg/debian/4.4.1-4/jellyfin-ffmpeg_4.4.1-4-buster_$(dpkg --print-architecture).deb -O jellyfin-ffmpeg_4.4.1-4-buster.deb
apt-get install -y ./jellyfin-ffmpeg_4.4.1-4-buster.deb
rm jellyfin-ffmpeg_4.4.1-4-buster.deb

# Copy server.js
echo "Copying server.js"
wget https://raw.githubusercontent.com/refa3211/stremio/main/server.js
# cp /path/to/your/server.js .

# Expose ports
echo "Exposing ports 11470 and 12470"
# This is not necessary in a script, but for documentation:
# HTTP port
HTTP_PORT=11470
# HTTPS port
HTTPS_PORT=12470

# Set environment variables
echo "Setting environment variables"
export FFMPEG_BIN=
export FFPROBE_BIN=
export APP_PATH=
export NO_CORS=
export CASTING_DISABLED=1

# Run the server
echo "Starting the server"
node server.js
