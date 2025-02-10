# Use a smaller base image
FROM node:14-alpine

# Set environment variables
ARG VERSION=master
ARG BUILD=desktop

LABEL com.stremio.vendor="Smart Code Ltd." \
      version=${VERSION} \
      description="Stremio's streaming Server"

WORKDIR /stremio
# Download server.js


# Install dependencies and FFmpeg
RUN apk add --no-cache \
    curl \
    ffmpeg \
    openssl \
    python3 \
    procps \
    && mkdir ssl \
    && openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
       -keyout ssl/server.key -out ssl/server.crt \
       -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*" \
       && curl -L -o server.js "https://dl.strem.io/server/v4.20.8/desktop/server.js"

# RUN curl -L -o server.js "https://dl.strem.io/server/v4.20.8/desktop/server.js"

# Create configuration directory with necessary permissions
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
ENV FFMPEG_BIN=/usr/bin/ffmpeg \
    FFPROBE_BIN=/usr/bin/ffprobe

# Healthcheck to ensure the server is running
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:11470/ || exit 1

# Start the application
ENTRYPOINT ["node", "server.js"]