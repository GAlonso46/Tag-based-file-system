#!/bin/bash
set -e

echo "=== Setting up Environment ==="

# 1. Generate Certificates
if [ -f "./generate_certs.sh" ]; then
    echo ">> Generating Certificates..."
    chmod +x generate_certs.sh
    ./generate_certs.sh
else
    echo "Error: generate_certs.sh not found!"
    exit 1
fi

# 2. Build Docker Images
if [ -f "./build-images.sh" ]; then
    echo ">> Building Docker Images..."
    chmod +x build-images.sh
    ./build-images.sh
else
    echo "Error: build-images.sh not found!"
    exit 1
fi

echo "=== Setup Complete ==="
