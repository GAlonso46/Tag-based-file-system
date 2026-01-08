#!/bin/bash

# Script to generate self-signed certificates for TLS in development
# For production, use proper CA-signed certificates

CERT_DIR="./certs"
mkdir -p "$CERT_DIR"

echo "=== Generating TLS Certificates for TagFS ==="

# Generate CA private key and certificate
echo "1. Generating CA certificate..."
openssl req -x509 -newkey rsa:4096 -keyout "$CERT_DIR/ca-key.pem" -out "$CERT_DIR/ca-cert.pem" -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=TagFS/OU=Development/CN=TagFS-CA"

# Generate server private key
echo "2. Generating server private key..."
openssl genrsa -out "$CERT_DIR/server-key.pem" 4096

# Generate server certificate signing request
echo "3. Generating server CSR..."
openssl req -new -key "$CERT_DIR/server-key.pem" -out "$CERT_DIR/server-csr.pem" \
  -subj "/C=US/ST=State/L=City/O=TagFS/OU=Services/CN=*.tagfs.local"

# Sign server certificate with CA
echo "4. Signing server certificate..."
openssl x509 -req -in "$CERT_DIR/server-csr.pem" -CA "$CERT_DIR/ca-cert.pem" -CAkey "$CERT_DIR/ca-key.pem" \
  -CAcreateserial -out "$CERT_DIR/server-cert.pem" -days 365

# Generate client private key (for mutual TLS if needed)
echo "5. Generating client private key..."
openssl genrsa -out "$CERT_DIR/client-key.pem" 4096

# Generate client certificate signing request
echo "6. Generating client CSR..."
openssl req -new -key "$CERT_DIR/client-key.pem" -out "$CERT_DIR/client-csr.pem" \
  -subj "/C=US/ST=State/L=City/O=TagFS/OU=Clients/CN=tagfs-client"

# Sign client certificate with CA
echo "7. Signing client certificate..."
openssl x509 -req -in "$CERT_DIR/client-csr.pem" -CA "$CERT_DIR/ca-cert.pem" -CAkey "$CERT_DIR/ca-key.pem" \
  -CAcreateserial -out "$CERT_DIR/client-cert.pem" -days 365

# Clean up CSR files
rm "$CERT_DIR"/*.csr.pem
rm "$CERT_DIR"/*.srl

echo ""
echo "=== Certificates generated successfully ==="
echo "Location: $CERT_DIR"
echo ""
echo "Files created:"
echo "  - ca-cert.pem (CA certificate - distribute to all services)"
echo "  - ca-key.pem (CA private key - keep secure)"
echo "  - server-cert.pem (Server certificate)"
echo "  - server-key.pem (Server private key)"
echo "  - client-cert.pem (Client certificate - for mutual TLS)"
echo "  - client-key.pem (Client private key - for mutual TLS)"
echo ""
echo "To enable TLS, set environment variable: ENABLE_TLS=true"

chmod 600 "$CERT_DIR"/*.pem
echo "Permissions set to 600 for all certificate files."
