#!/bin/bash

set -e

echo "🚀 Deploying Complete SRE Kubernetes Environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
print_status "Checking prerequisites..."

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check helm
if ! command -v helm &> /dev/null; then
    print_error "helm is not installed. Please install helm first."
    exit 1
fi

# Check docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    print_error "Cannot connect to Kubernetes cluster. Please ensure your cluster is running."
    exit 1
fi

print_success "All prerequisites are met"

# Step 1: Initialize cluster
print_status "Step 2: Initializing Kubernetes cluster..."
./scripts/init-cluster.sh
print_success "Cluster initialized"

# Step 2: Verify deployment
print_status "Step 3: Verifying deployment..."

# Wait for all pods to be ready
print_status "Waiting for all pods to be ready..."
kubectl wait --for=condition=ready pod -l app=main-api-service -n applications --timeout=300s
kubectl wait --for=condition=ready pod -l app=auth-service -n applications --timeout=300s
kubectl wait --for=condition=ready pod -l app=image-service -n applications --timeout=300s
kubectl wait --for=condition=ready pod -l app=postgresql -n infrastructure --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n infrastructure --timeout=300s
kubectl wait --for=condition=ready pod -l app=minio -n infrastructure --timeout=300s
kubectl wait --for=condition=ready pod -l app=prometheus -n monitoring --timeout=300s
kubectl wait --for=condition=ready pod -l app=grafana -n monitoring --timeout=300s
kubectl wait --for=condition=ready pod -l app=alertmanager -n monitoring --timeout=300s

print_success "All pods are ready"

# Step 4: Health checks
print_status "Step 4: Performing health checks..."

# Check main API service
print_status "Checking Main API Service..."
if curl -sk https://api.sy.sa/health | grep -q "healthy"; then
    print_success "Main API Service is healthy"
else
    print_warning "Main API Service health check failed"
fi

# Check auth service
print_status "Checking Auth Service..."
if curl -sk https://auth.sy.sa/health | grep -q "healthy"; then
    print_success "Auth Service is healthy"
else
    print_warning "Auth Service health check failed"
fi

# Check image service
print_status "Checking Image Service..."
if curl -sk https://image.sy.sa/health | grep -q "healthy"; then
    print_success "Image Service is healthy"
else
    print_warning "Image Service health check failed"
fi

# Step 5: Display access information
print_success "SRE Kubernetes Environment deployed successfully!"
echo ""
echo "📋 Access Information:"
echo "  • Main API Service: https://api.sy.sa"
echo "  • Grafana Dashboard: https://grafana.sy.sa (admin/admin)"
echo "  • Prometheus: https://prometheus.sy.sa"
echo "  • Alertmanager: https://alertmanager.sy.sa"
echo "  • MinIO Console: https://minio.sy.sa (minioadmin/minioadmin)"
echo "  • Docker Registry: https://registry.sy.sa:5000"
echo ""
echo "🔍 Useful Commands:"
echo "  • Check pod status: kubectl get pods --all-namespaces"
echo "  • View logs: kubectl logs -f deployment/main-api-service -n applications"
echo "  • Monitor HPA: kubectl get hpa -A"
echo "  • Check metrics: kubectl top pods -A"
echo ""
echo "🧪 Testing Commands:"
echo "  • Run load tests: ./scripts/load-test.sh"
echo "  • Simulate failures: see docs/failure-scenarios.md"
echo ""
echo "📊 Monitoring:"
echo "  • Prometheus alerts are configured for high CPU, memory, and error rates"
echo "  • Alertmanager is configured for alert routing and notifications"
echo "  • Grafana dashboards are pre-configured for each service and Alertmanager"
echo "  • Network policies are in place for security"
echo ""
print_success "Deployment completed successfully!" 