#!/bin/bash
set -e

STACK_NAME="tagfs"

echo "=== Deploying to Docker Swarm ==="

# 1. Initialize Swarm if not active
if ! docker info | grep -q "Swarm: active"; then
    echo ">> Initializing Docker Swarm..."
    docker swarm init
else
    echo ">> Swarm already active."
fi

# 2. Create Overlay Network if not exists (usually created by stack deploy, but good to ensure)
# docker network create --driver overlay tagfs-overlay || true

# 3. Deploy Stack
echo ">> Deploying stack '$STACK_NAME'..."
docker stack deploy -c docker-stack-distributed.yml $STACK_NAME

echo ">> Waiting for services to start (30s)..."
sleep 30

echo ">> Service Status:"
docker stack services $STACK_NAME

echo "=== Deployment Triggered ==="
echo "Run 'docker service ls' to check status."
