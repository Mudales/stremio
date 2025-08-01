FROM node:14-slim

ARG VERSION=master
ARG BUILD=desktop

LABEL com.stremio.vendor="Smart Code Ltd." \
      version=${VERSION} \
      description="Stremio's streaming Server"

WORKDIR /stremio

# Install dependencies and generate SSL certificate
# Install dependencies and generate SSL certificate
RUN sed -i 's/deb.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i '/buster-updates/d' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    openssl \
    python3 \
    procps \
    curl \
    && mkdir ssl \
    && openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
       -keyout ssl/server.key -out ssl/server.crt \
       -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"

# Download and install jellyfin-ffmpeg
RUN wget --no-check-certificate https://repo.jellyfin.org/archive/ffmpeg/debian/4.4.1-4/jellyfin-ffmpeg_4.4.1-4-buster_$(dpkg --print-architecture).deb \
    -O jellyfin-ffmpeg.deb && \
    apt-get install -y ./jellyfin-ffmpeg.deb && \
    rm jellyfin-ffmpeg.deb

# Download server.js
RUN wget --no-check-certificate -O server.js "https://dl.strem.io/server/v4.20.8/desktop/server.js"

# Create directory and set permissions
RUN mkdir -p /root/.stremio-server && \
    touch /root/.stremio-server/server-settings.json && \
    echo '{}' > /root/.stremio-server/server-settings.json && \
    chmod 777 -R /root/.stremio-server

# Cleanup but keep curl and procps
RUN apt-get remove -y wget && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY fix.py fix.py
RUN python3 fix.py && rm fix.py

VOLUME ["/root/.stremio-server"]

EXPOSE 11470 12470 443

ENV FFMPEG_BIN=/usr/lib/jellyfin-ffmpeg/ffmpeg \
    FFPROBE_BIN=/usr/lib/jellyfin-ffmpeg/ffprobe

# Modified healthcheck with longer intervals and start period
#HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
#    CMD curl -f http://localhost:11470/ || exit 1

ENTRYPOINT ["node", "server.js"]
