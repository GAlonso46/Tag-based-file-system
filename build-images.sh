#!/bin/bash

# Script para construir todas las imágenes Docker

echo "🐳 Construyendo imágenes Docker..."

# Backend
echo "📦 Construyendo Backend..."
docker build -f Dockerfile.backend -t tagfs-backend:latest .

# Frontend
echo "🎨 Construyendo Frontend..."
cd frontend-react
docker build -t tagfs-frontend:latest .
cd ..

# Verificar
echo "✅ Imágenes construidas:"
docker images | grep tagfs

echo ""
echo "🎉 ¡Listo! Ahora puedes:"
echo "   - Desarrollo local: docker-compose up"
echo "   - Docker Swarm: docker stack deploy -c docker-stack.yml tagfs"
