#!/usr/bin/env sh
# Generate a self-signed cert for staging / demo use (NOT for production).
#   sh deploy/nginx/gen-selfsigned.sh [common-name]
set -e

CN="${1:-localhost}"
DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$DIR"

openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout "$DIR/privkey.pem" \
  -out "$DIR/fullchain.pem" \
  -subj "/CN=$CN" \
  -addext "subjectAltName=DNS:$CN,DNS:localhost,IP:127.0.0.1"

chmod 600 "$DIR/privkey.pem"
echo "[gen-selfsigned] wrote $DIR/{fullchain,privkey}.pem for CN=$CN"
echo "Browsers will warn on this cert — expected for a self-signed staging box."
