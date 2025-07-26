#!/bin/bash

set -e

echo "🐳 Building and pushing Docker images..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Set registry URL (change this to your registry)
REGISTRY="registry.sy.sa"

# Build and push Main API Service (Node.js)
echo "🔨 Building Main API Service..."
cd services/main-api-service
docker build -t $REGISTRY/main-api-service:latest .
docker push $REGISTRY/main-api-service:latest
cd ../..

# Build and push Auth Service (Go)
echo "🔨 Building Auth Service..."
cd services/auth-service
docker build -t $REGISTRY/auth-service:latest .
docker push $REGISTRY/auth-service:latest
cd ../..

# Build and push Image Service (Python)
echo "🔨 Building Image Service..."
cd services/image-service
docker build -t $REGISTRY/image-service:latest .
docker push $REGISTRY/image-service:latest
cd ../..

echo "✅ All images built and pushed successfully!"
echo ""
echo "📋 Image Registry: $REGISTRY"
echo "  • main-api-service:latest"
echo "  • auth-service:latest"
echo "  • image-service:latest" 