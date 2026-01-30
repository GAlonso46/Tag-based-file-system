#!/bin/bash

# Detener contenedores existentes primero
docker stop $(docker ps -q) 2>/dev/null || true

# Crear red si no existe
docker network create -d overlay --attachable tagfs-overlay 2>/dev/null || true

# Crear volúmenes si no existen
docker volume create metadata-store 2>/dev/null || true
docker volume create datanode-store 2>/dev/null || true
docker volume create gateway-store 2>/dev/null || true  # <-- NUEVO VOLUMEN

# Frontend
docker run -d \
  --name frontend_1 \
  --network tagfs-overlay \
  -p 80:80 \
  tagfs-frontend:latest

# Datanode 1
docker run -d \
  --name datanode_1 \
  --hostname datanode_1 \
  --network tagfs-overlay \
  --network-alias datanode_service \
  -e NODE_ID=dn1 \
  -e PORT=50051 \
  -v datanode-store:/app/data_node_storage \
  tagfs-backend:latest python services/datanode/main.py

# Metadata 1
docker run -d \
  --name metadata_1 \
  --hostname metadata_1 \
  --network tagfs-overlay \
  --network-alias metadata_service \
  -e NODE_ID=1 \
  -e PORT=50051 \
  -v metadata-store:/app/metadata_storage \
  tagfs-backend:latest python services/metadata/main.py

# Gateway 2 CON VOLUMEN gateway-store
docker run -d \
  --name gateway_2 \
  --network tagfs-overlay \
  --network-alias gateway_service \
  -p 8001:8000 \
  -e METADATA_HOST=metadata_service \
  -e METADATA_PORT=50051 \
  -v gateway-store:/app/tags_data \
  tagfs-backend:latest python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000

echo "Contenedores iniciados:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"