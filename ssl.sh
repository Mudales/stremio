#!/bin/bash

# Create a directory named ssl
mkdir -p ssl

# Generate a new private key and a self-signed certificate
openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout ssl/server.key -out ssl/server.crt -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"

# Output result
echo "SSL certificate and key have been generated and stored in the ssl directory."
