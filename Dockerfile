# --- Build stage: patch server.js with SSL support ---
FROM node:18-alpine AS builder

WORKDIR /build

RUN apk add --no-cache wget python3 openssl

# Generate self-signed SSL certificate
RUN mkdir ssl && openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
    -keyout ssl/server.key -out ssl/server.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"

# Download server.js
RUN wget --no-check-certificate -O server.js \
    "https://dl.strem.io/server/v4.20.8/desktop/server.js"

# Patch server.js for SSL
COPY fix.py fix.py
RUN python3 fix.py

# --- Runtime stage: minimal image ---
FROM node:18-alpine

ARG VERSION=master
LABEL com.stremio.vendor="Smart Code Ltd." \
      version=${VERSION} \
      description="Stremio's streaming Server"

WORKDIR /stremio

# Install only runtime dependencies
RUN apk add --no-cache ffmpeg curl

# Copy built artifacts from builder
COPY --from=builder /build/server.js ./server.js
COPY --from=builder /build/ssl ./ssl

# Create config directory
RUN mkdir -p /root/.stremio-server && \
    echo '{}' > /root/.stremio-server/server-settings.json

VOLUME ["/root/.stremio-server"]

EXPOSE 11470 12470

ENV FFMPEG_BIN=/usr/bin/ffmpeg \
    FFPROBE_BIN=/usr/bin/ffprobe \
    NO_CORS=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:11470/ || exit 1

ENTRYPOINT ["node", "server.js"]
