FROM node:14-slim

ARG VERSION=master
ARG BUILD=desktop

LABEL com.stremio.vendor="Smart Code Ltd." \
      version=${VERSION} \
      description="Stremio's streaming Server"

WORKDIR /stremio

# Install dependencies, generate SSL certificate, and clean up in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openssl \
    python3 \
    procps \
    && mkdir ssl \
    && openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
       -keyout ssl/server.key -out ssl/server.crt \
       -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*" \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Download and install jellyfin-ffmpeg in a single step
RUN ARCH=$(dpkg --print-architecture) && \
    curl -L -o jellyfin-ffmpeg.deb "https://repo.jellyfin.org/archive/ffmpeg/debian/4.4.1-4/jellyfin-ffmpeg_4.4.1-4-buster_${ARCH}.deb" && \
    apt-get install -y ./jellyfin-ffmpeg.deb && \
    rm -f jellyfin-ffmpeg.deb

# Download server.js
RUN curl -L -o server.js "https://dl.strem.io/server/v4.20.8/desktop/server.js"

# Create configuration directory and set permissions
RUN mkdir -p /root/.stremio-server && \
    echo '{}' > /root/.stremio-server/server-settings.json && \
    chmod 777 -R /root/.stremio-server

# Copy and execute fix.py, then remove it
COPY fix.py fix.py
RUN python3 fix.py && rm fix.py

# Define persistent storage
VOLUME ["/root/.stremio-server"]

# Expose required ports
EXPOSE 11470 12470 443

# Define environment variables
ENV FFMPEG_BIN=/usr/lib/jellyfin-ffmpeg/ffmpeg \
    FFPROBE_BIN=/usr/lib/jellyfin-ffmpeg/ffprobe

# Healthcheck with longer intervals and start period
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:11470/ || exit 1

# Start the application
ENTRYPOINT ["node", "server.js"]