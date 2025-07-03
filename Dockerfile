# --- Stage 1: The Builder ---
FROM node:14-slim AS builder

WORKDIR /build

# Install tools needed only for the build process
RUN apt-get update && apt-get install -y --no-install-recommends wget python3 openssl

# Download Stremio server
RUN wget --no-check-certificate -O server.js "https://dl.strem.io/server/v4.20.8/desktop/server.js"

# Create SSL certificates
RUN mkdir ssl && openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
   -keyout ssl/server.key -out ssl/server.crt \
   -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"

# Copy and run the fix script
COPY fix.py .
RUN python3 fix.py

# --- Stage 2: The Final Image ---
FROM node:14-slim

WORKDIR /stremio

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl procps wget && \
    wget --no-check-certificate https://repo.jellyfin.org/archive/ffmpeg/debian/4.4.1-4/jellyfin-ffmpeg_4.4.1-4-buster_$(dpkg --print-architecture).deb -O jellyfin-ffmpeg.deb && \
    # Use apt to install the local .deb file, which handles dependencies automatically
    apt-get install -y ./jellyfin-ffmpeg.deb && \
    rm jellyfin-ffmpeg.deb && \
    # Clean up build-only dependencies and cache
    apt-get remove -y wget && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy artifacts from the builder stage
COPY --from=builder /build/server.js .
COPY --from=builder /build/ssl ./ssl

# Set up environment. We run as root inside the container to avoid
# potential permission issues with the volume that can trigger the compose bug.
RUN mkdir -p /root/.stremio-server

# The VOLUME instruction is removed as it's handled by docker-compose.yml,
# which can prevent errors with older docker-compose versions.
EXPOSE 11470 12470

ENV FFMPEG_BIN=/usr/lib/jellyfin-ffmpeg/ffmpeg \
    FFPROBE_BIN=/usr/lib/jellyfin-ffmpeg/ffprobe

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:11470/ || exit 1

ENTRYPOINT ["node", "server.js"]
