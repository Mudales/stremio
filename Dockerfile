# Use Node.js 14.15.0-alpine as the base image
FROM node:14.15.0-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy the server.js file to the container
COPY server.js .

# Create the ssl directory and generate the self-signed certificate
RUN mkdir ssl && \
    openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout ssl/server.key -out ssl/server.crt -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=*"

# Expose the required ports
EXPOSE 11470
EXPOSE 12470

# Command to run the server
CMD ["node", "server.js"]
