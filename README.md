# SRE Kubernetes Environment - Practical Assignment

## Overview

This project implements a complete Site Reliability Engineering (SRE) environment with three microservices deployed on Kubernetes, featuring advanced monitoring, security, autoscaling, and failure recovery capabilities.

## Architecture

### Services
1. **Main API Service** (Node.js) - Handles business logic and orchestrates other services
2. **Authentication Service** (Go) - Manages user authentication and authorization
3. **Image Storage Service** (Python) - Handles image upload, storage, and retrieval

### Infrastructure Components
- **Kubernetes Cluster** with RBAC, Network Policies, and Ingress
- **Prometheus & Grafana** for monitoring and alerting
- **Alertmanager** with Slack integration
- **Horizontal Pod Autoscaler (HPA)** for automatic scaling
- **Secrets Management** for secure credential storage
- **TLS/SSL** with Let's Encrypt certificates

## Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                         │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│  │   Ingress-NGINX │    │   Cert-Manager   │    │   Prometheus │  │
│  │   (TLS/SSL)     │    │  (Let's Encrypt) │    │   & Grafana  │  │
│  └─────────────────┘    └──────────────────┘    └──────────────┘  │
│           │                       │                     │         │
│           ▼                       ▼                     ▼         │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Application Layer                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │  │
│  │  │ Main API    │  │ Auth        │  │ Image Storage       │  │  │
│  │  │ Service     │◄─┤ Service     │  │ Service             │  │  │
│  │  │ (Node.js)   │  │ (Go)        │  │ (Python)            │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│           │                       │                     │         │
│           ▼                       ▼                     ▼         │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Data Layer                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │  │
│  │  │ PostgreSQL  │  │ Redis       │  │ MinIO (S3)          │  │  │
│  │  │ Database    │  │ Cache       │  │ Object Storage      │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes cluster (minikube, kind, or cloud provider)
- kubectl configured
- Docker installed
- Helm 3.x installed

## Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/xlmnxp/thmanyah-challenge.git
cd thmanyah-challenage
```

### 2. Initialize the Environment
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Deploy the entire stack
./scripts/deploy-all.sh
```

### 3. Access Services
- **Main API**: https://api.sy.sa
- **Grafana**: https://grafana.sy.sa (admin/admin)
- **Prometheus**: https://prometheus.sy.sa
- **Alertmanager**: https://alertmanager.sy.sa
- **MinIO Console**: https://minio.sy.sa (minioadmin/minioadmin)

### Private Docker Registry
- **Registry URL**: https://registry.sy.sa
- **How to push**:
  ```bash
  docker tag <image> registry.sy.sa/<image>
  docker push registry.sy.sa/<image>
  ```
- **How to pull**:
  ```bash
  docker pull registry.sy.sa/<image>
  ```

## Detailed Deployment Steps

### Step 1: Cluster Initialization
```bash
# Create namespaces
kubectl apply -f k8s/namespaces.yaml

# Install Helm repositories
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add jetstack https://charts.jetstack.io
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Ingress Controller
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace

# Install Cert-Manager
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true
```

### Step 2: Deploy Infrastructure
```bash
# Deploy databases and storage
kubectl apply -f k8s/infrastructure/

# Deploy monitoring stack
kubectl apply -f k8s/monitoring/
```

### Step 3: Deploy Applications
```bash
# Deploy all services
kubectl apply -f k8s/applications/
```

## Failure Simulation and Recovery

### Scenario 1: Database Outage
```bash
# Simulate PostgreSQL pod failure
kubectl delete pod -n infrastructure -l app=postgresql

# Monitor recovery
kubectl get pods -n infrastructure -w
kubectl logs -n monitoring -l app=prometheus
```

### Scenario 2: High Traffic Load
```bash
# Generate load on main API service
kubectl run load-test --image=busybox --rm -it --restart=Never -- \
  sh -c "while true; do wget -qO- http://main-api-service:3000/health; sleep 0.1; done"

# Monitor HPA scaling
kubectl get hpa -w
```

### Scenario 3: Service Failure
```bash
# Simulate auth service crash
kubectl delete pod -n applications -l app=auth-service

# Check liveness/readiness probes
kubectl describe pod -n applications -l app=auth-service
```

## Monitoring and Alerting

### Prometheus Metrics
- Custom metrics for each service
- Business metrics (request rate, error rate, response time)
- Infrastructure metrics (CPU, memory, disk)

### Grafana Dashboards
- Service-specific dashboards
- System overview dashboard
- Alert history dashboard

### Alertmanager Integration
- **Alertmanager Dashboard**: Comprehensive dashboard in Grafana for monitoring alert metrics
- **Alert Routing**: Intelligent routing based on severity levels
- **Slack Integration**: Real-time notifications to Slack channels
- **Email Notifications**: Configurable email alerts for warnings
- **PagerDuty Integration**: On-call escalation for critical incidents
- **Alert Silencing**: Temporary suppression of non-critical alerts
- **Alert Grouping**: Intelligent grouping to reduce alert fatigue

## Security Features

### Network Policies
- Pod-to-pod communication restrictions
- External access controls
- Database access isolation

### Secrets Management
- Kubernetes secrets for sensitive data
- External secrets operator (optional)
- RBAC for secret access

### TLS/SSL
- Let's Encrypt certificates
- Automatic certificate renewal
- HTTPS enforcement

## Autoscaling Configuration

### Horizontal Pod Autoscaler
- CPU-based scaling (70% threshold)
- Memory-based scaling (80% threshold)
- Custom metrics scaling (request rate)

### Pod Disruption Budget
- Minimum availability during maintenance
- Graceful shutdown handling
- Rolling update strategies

## Troubleshooting

### Common Issues
1. **Image pull errors**: Check registry credentials
2. **Service connectivity**: Verify network policies
3. **Certificate issues**: Check cert-manager logs
4. **Scaling problems**: Review HPA configuration

### Debug Commands
```bash
# Check pod status
kubectl get pods --all-namespaces

# View service logs
kubectl logs -f deployment/main-api-service -n applications

# Check Alertmanager status
kubectl get pods -n monitoring -l app=alertmanager

# View Alertmanager logs
kubectl logs -f deployment/alertmanager -n monitoring

# Check events
kubectl get events --sort-by='.lastTimestamp'

# Verify network policies
kubectl get networkpolicies --all-namespaces
```

## Performance Testing

### Load Testing Scripts
```bash
# Run load tests
./scripts/load-test.sh
```

## File Structure

```
.
├── README.md
├── docs
│   ├── failure-scenarios.md
│   └── troubleshooting.md
├── k8s
│   ├── namespaces.yaml
│   ├── applications
│   │   ├── auth-service
│   │   │   └── deployment.yaml
│   │   ├── image-service
│   │   │   └── deployment.yaml
│   │   └── main-api-service
│   │       └── deployment.yaml
│   ├── infrastructure
│   │   ├── minio.yaml
│   │   ├── postgresql.yaml
│   │   ├── redis.yaml
│   │   └── registry.yaml
│   ├── monitoring
│   │   ├── alertmanager.yaml
│   │   ├── grafana-dashboards-config.yaml
│   │   ├── grafana.yaml
│   │   ├── prometheus.yaml
│   │   └── {configs}
│   │       ├── alertmanager-config.yaml
│   │       ├── alertmanager-dashboard.json
│   │       ├── auth-service-dashboard.json
│   │       ├── image-service-dashboard.json
│   │       ├── main-api-dashboard.json
│   │       ├── prometheus-alert-rules.yaml
│   │       ├── service-monitors.yaml
│   │       └── system-overview-dashboard.json
│   └── security
│       ├── network-policies.yaml
│       └── secrets.yaml
├── scripts
│   ├── build-images.sh
│   ├── deploy-all.sh
│   ├── init-cluster.sh
│   └── load-test.sh
└── services
    ├── auth-service
    │   ├── Dockerfile
    │   ├── go.mod
    │   ├── go.sum
    │   └── main.go
    ├── image-service
    │   ├── app.py
    │   ├── Dockerfile
    │   └── requirements.txt
    └── main-api-service
        ├── Dockerfile
        ├── package.json
        ├── package-lock.json
        └── server.js
```