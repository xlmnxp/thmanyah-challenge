#!/bin/bash

set -e

echo "🚀 Initializing SRE Kubernetes Environment..."

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo "❌ helm is not installed. Please install helm first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster. Please ensure your cluster is running and accessible."
    exit 1
fi

echo "✅ Kubernetes cluster is accessible"

# Create namespaces
echo "📦 Creating namespaces..."
kubectl apply -f k8s/namespaces.yaml

# Add Helm repositories
echo "📚 Adding Helm repositories..."
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add jetstack https://charts.jetstack.io
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Ingress Controller
echo "🌐 Installing Ingress Controller..."
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace

# Install Cert-Manager
echo "🔐 Installing Cert-Manager..."
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true \
  --set global.leaderElection.namespace=cert-manager

# Wait for cert-manager to be ready
echo "⏳ Waiting for cert-manager to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s

# Create ClusterIssuer for Let's Encrypt
echo "🔒 Creating ClusterIssuer for Let's Encrypt..."
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: s@sy.sa
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# Deploy infrastructure
echo "🏗️ Deploying infrastructure components..."
kubectl apply -f k8s/infrastructure/

# Wait for infrastructure to be ready
echo "⏳ Waiting for infrastructure to be ready..."
kubectl wait --for=condition=ready pod -l app=registry -n infrastructure --timeout=300s
kubectl wait --for=condition=ready pod -l app=postgresql -n infrastructure --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n infrastructure --timeout=300s
kubectl wait --for=condition=ready pod -l app=minio -n infrastructure --timeout=300s

# Copy Postgresql and Minio secrets to applications namespace 
kubectl get secret postgresql-secret -n infrastructure -o yaml | sed 's/namespace: infrastructure/namespace: applications/' | kubectl apply -f -
kubectl get secret minio-secret -n infrastructure -o yaml | sed 's/namespace: infrastructure/namespace: applications/' | kubectl apply -f -

# Build images
echo "🔨 Building images..."
./scripts/build-images.sh

# Deploy monitoring stack
echo "📊 Deploying monitoring stack..."
kubectl apply -f k8s/monitoring/

# Wait for monitoring to be ready
echo "⏳ Waiting for monitoring to be ready..."
kubectl wait --for=condition=ready pod -l app=prometheus -n monitoring --timeout=300s
kubectl wait --for=condition=ready pod -l app=grafana -n monitoring --timeout=300s

# Deploy security configurations
echo "🔒 Deploying security configurations..."
kubectl apply -f k8s/security/

# Build images
echo "🔨 Building images..."
./scripts/build-images.sh

# Deploy applications
echo "🚀 Deploying applications..."
kubectl apply -f k8s/applications/main-api-service/
kubectl apply -f k8s/applications/auth-service/
kubectl apply -f k8s/applications/image-service/

# Wait for applications to be ready
echo "⏳ Waiting for applications to be ready..."
kubectl wait --for=condition=ready pod -l app=main-api-service -n applications --timeout=300s
kubectl wait --for=condition=ready pod -l app=auth-service -n applications --timeout=300s
kubectl wait --for=condition=ready pod -l app=image-service -n applications --timeout=300s

# Check if everything is ready
./scripts/deploy-all.sh

echo "✅ SRE Kubernetes Environment initialized successfully!"
echo ""
echo "📋 Access Information:"
echo "  • Main API Service: https://api.sy.sa"
echo "  • Grafana Dashboard: https://grafana.sy.sa (admin/admin)"
echo "  • Prometheus: https://prometheus.sy.sa"
echo "  • MinIO Console: https://minio.sy.sa (minioadmin/minioadmin)"
echo "  • Docker Registry: https://registry.sy.sa"
echo ""
echo "🔍 Check status with: kubectl get pods --all-namespaces"
echo "📊 View logs with: kubectl logs -f deployment/main-api-service -n applications" 