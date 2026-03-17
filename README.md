# Stremio Docker Server

Self-hosted Stremio streaming server with HTTPS support, automatic on-demand startup, and idle auto-shutdown.

## Quick Start

```bash
git clone https://github.com/Mudales/stremio.git
cd stremio
sudo ./install.sh
```

This will:
- Build the Docker image (lightweight, alpine-based)
- Install `stremio-manager.service` (handles both on-demand startup and inactivity shutdown)

Access at: `http://<your-ip>` (redirects to HTTPS automatically)

## How It Works

**`stremio_manager.py`** runs as a single systemd service with two jobs:

- **HTTP Listener (port 80)** — when someone accesses your server, starts the Stremio container if it's not running and redirects to HTTPS
- **Inactivity Monitor** — checks container network activity every 30s, stops it and clears cache after 45 minutes of no traffic

**SSL** — The Dockerfile generates a self-signed certificate at build time and patches `server.js` (via `fix.py`) to load it. The container serves HTTPS on port 12470 (mapped to 443).

## Behind a Reverse Proxy (Nginx / Caddy / Traefik)

If you use a reverse proxy with your own certificate, forward traffic to the **HTTP** port to avoid self-signed cert issues:

```
your-proxy → http://localhost:11470
```

Example Nginx config:
```nginx
server {
    listen 443 ssl;
    server_name stremio.example.com;

    ssl_certificate     /path/to/your/cert.pem;
    ssl_certificate_key /path/to/your/key.pem;

    location / {
        proxy_pass http://localhost:11470;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

In this setup, the `443:12470` port mapping in `docker-compose.yml` is not needed — you can remove it.

## Configuration

All settings are overridable via environment variables in the systemd service file (`/etc/systemd/system/stremio-manager.service`):

| Variable | Default | Description |
|----------|---------|-------------|
| `STREMIO_LISTEN_PORT` | `80` | HTTP listener port |
| `STREMIO_INACTIVITY_MINUTES` | `45` | Minutes of idle before auto-shutdown |
| `STREMIO_CHECK_INTERVAL` | `30` | Seconds between activity checks |
| `STREMIO_STARTUP_TIMEOUT` | `60` | Seconds to wait for container health |
| `STREMIO_NETWORK_THRESHOLD` | `1024` | Bytes of network I/O to count as active |
| `STREMIO_CACHE_DIR` | `./stremio-server/stremio-cache` | Cache path to clear on shutdown |

After editing, reload with:
```bash
sudo systemctl daemon-reload
sudo systemctl restart stremio-manager
```

## Service Management

```bash
sudo systemctl status stremio-manager     # check status
sudo journalctl -u stremio-manager -f     # follow logs
sudo systemctl stop stremio-manager       # stop
sudo systemctl start stremio-manager      # start
```

## Manual Docker Usage

If you prefer to run without the manager:

```bash
docker compose up --build -d
```

Access at: `https://<your-ip>:443`

## Stremio Setup

1. Create an account at https://www.stremio.com/register
2. Install the Torrentio addon: https://torrentio.strem.fun/configure

## Credits

SSL fix based on: https://github.com/Stremio/stremio-service/issues/39#issuecomment-1988694509
