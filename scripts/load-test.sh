#!/bin/bash

set -e

echo "🚀 Starting Load Testing..."

# Check if kubectl is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster."
    exit 1
fi

# Function to run load test
run_load_test() {
    local service_name=$1
    local endpoint=$2
    local duration=$3
    local rate=$4
    
    echo "📊 Testing $service_name at $rate requests/second for $duration seconds..."
    
    # Create load test pod
    kubectl run load-test-$service_name \
        --image=busybox \
        --rm -it --restart=Never \
        -- sh -c "
        echo 'Starting load test for $service_name...'
        for i in \$(seq 1 $duration); do
            for j in \$(seq 1 $rate); do
                wget -qO- http://$service_name:${endpoint#*:}${endpoint%:*}/health > /dev/null 2>&1 &
            done
            sleep 1
        done
        wait
        echo 'Load test completed for $service_name'
    "
}

# Test Main API Service
echo "🎯 Testing Main API Service..."
run_load_test "main-api-service" "3000" 60 10

# Test Auth Service
echo "🎯 Testing Auth Service..."
run_load_test "auth-service" "8080" 60 5

# Test Image Service
echo "🎯 Testing Image Service..."
run_load_test "image-service" "5000" 60 3

echo "✅ Load testing completed!"
echo ""
echo "📊 Monitor results:"
echo "  • kubectl get hpa -A"
echo "  • kubectl top pods -A"
echo "  • kubectl logs -f deployment/main-api-service -n applications" 