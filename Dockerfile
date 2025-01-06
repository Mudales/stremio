# Copyright (C) 2017-2023 Smart code 203358507

# the node version for running the server
ARG NODE_VERSION=14

FROM node:$NODE_VERSION

ARG VERSION=master
ARG BUILD=desktop

LABEL com.stremio.vendor="Smart Code Ltd."
LABEL version=${VERSION}
LABEL description="Stremio's streaming Server"

SHELL ["/bin/sh", "-c"]

CMD ["bash"]

WORKDIR /stremio

# Install patch utility along with other dependencies
RUN apt -y update && \
    apt -y install wget patch && \
    mkdir ssl && \
    openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout ssl/server.key -out ssl/server.crt -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"

# Install jellyfin-ffmpeg
ARG JELLYFIN_VERSION=4.4.1-4
RUN wget https://repo.jellyfin.org/archive/ffmpeg/debian/4.4.1-4/jellyfin-ffmpeg_4.4.1-4-buster_$(dpkg --print-architecture).deb -O jellyfin-ffmpeg_4.4.1-4-buster.deb && \
    apt -y install ./jellyfin-ffmpeg_4.4.1-4-buster.deb && \
    rm jellyfin-ffmpeg_4.4.1-4-buster.deb

RUN wget $(wget -O- https://raw.githubusercontent.com/Stremio/stremio-shell/master/server-url.txt) 

# RUN sed -i '43888s|.*|try {\n    var fs = require('"'"'fs'"'"');\n    var https = require('"'"'https'"'"');\n    _cr = {\n        key: fs.readFileSync('"'"'./ssl/server.key'"'"', '"'"'utf8'"'"'),\n        cert: fs.readFileSync('"'"'./ssl/server.crt'"'"', '"'"'utf8'"'"')\n    };\n} catch (e) {\n    console.error("Failed to load SSL cert:", e);\n    _cr = { };\n}\nvar sserver = https.createServer(_cr, app);|' server.js


# Create patch file
COPY ssl.patch ssl.patch
COPY test.patch test.patch

# Create entrypoint script
RUN echo '#!/bin/sh\n\
patch server.js test.patch\n\
exec node server.js' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

VOLUME ["/root/.stremio-server"]

# HTTP
EXPOSE 11470
# HTTPS
EXPOSE 12470

# Environment variables
ENV FFMPEG_BIN=
ENV FFPROBE_BIN=
ENV APP_PATH=
ENV NO_CORS=
ENV CASTING_DISABLED=1

ENTRYPOINT [ "node", "server.js" ]
