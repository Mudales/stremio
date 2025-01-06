# Copyright (C) 2017-2023 Smart code 203358507

ARG NODE_VERSION=14
FROM node:$NODE_VERSION

ARG VERSION=master
ARG BUILD=desktop

LABEL com.stremio.vendor="Smart Code Ltd."
LABEL version=${VERSION}
LABEL description="Stremio's streaming Server"

WORKDIR /stremio

# Install dependencies
RUN apt -y update && \
    apt -y install wget patch && \
    mkdir ssl && \
    openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
    -keyout ssl/server.key -out ssl/server.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"

# Install jellyfin-ffmpeg
ARG JELLYFIN_VERSION=4.4.1-4
RUN wget https://repo.jellyfin.org/archive/ffmpeg/debian/4.4.1-4/jellyfin-ffmpeg_4.4.1-4-buster_$(dpkg --print-architecture).deb \
    -O jellyfin-ffmpeg.deb && \
    apt -y install ./jellyfin-ffmpeg.deb && \
    rm jellyfin-ffmpeg.deb

# Download server
RUN wget -O server.js $(wget -qO- https://raw.githubusercontent.com/Stremio/stremio-shell/master/server-url.txt)

# Create patch file
RUN python3 -c "replacement = '''        try {\n            var fs = require('fs');\n            var https = require('https');\n            _cr = {\n                key: fs.readFileSync('./ssl/server.key', 'utf8'),\n                cert: fs.readFileSync('./ssl/server.crt', 'utf8')\n            };\n        } catch (e) {\n            console.error('Failed to load SSL cert:', e);\n            _cr = { };\n        }\n        var sserver = https.createServer(_cr, app);'''\nwith open('server.js', 'r') as file:\n    lines = file.readlines()\nwith open('server.js', 'w') as file:\n    for line in lines:\n        if 'var sserver = https.createServer(app);' in line:\n            file.write(replacement + '\\n')\n        else:\n            file.write(line)"

VOLUME ["/root/.stremio-server"]

# HTTP
EXPOSE 11470
# HTTPS
EXPOSE 12470

# Environment variables
ENV FFMPEG_BIN=/usr/lib/jellyfin-ffmpeg/ffmpeg
ENV FFPROBE_BIN=/usr/lib/jellyfin-ffmpeg/ffprobe
ENV CASTING_DISABLED=1

ENTRYPOINT ["node", "server.js"]
