#!/bin/sh
# Create a self-signed fallback cert so nginx can start before Let's Encrypt
# certificates are provisioned. Real certs from certbot will override this.
CERT_DIR=/etc/letsencrypt/live/default
if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/CN=localhost" 2>/dev/null
fi
