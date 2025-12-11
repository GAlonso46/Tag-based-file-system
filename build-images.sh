#!/bin/bash

# Stops on error
set -e

echo -e "\n🐳 Building Docker images..."

# Backend
echo -e "\n📦 Building Backend..."
docker build -f Dockerfile.backend -t tagfs-backend:latest .

# Frontend
echo -e "\n🎨 Building Frontend..."
cd frontend-react
docker build -t tagfs-frontend:latest .
cd ..

# Verify
echo -e "\n✅ Images built:"
docker images | grep "tagfs"

echo -e "\n🎉 Ready! You can now deploy:"
echo "   docker stack deploy -c docker-stack-distributed.yml tagfs"
