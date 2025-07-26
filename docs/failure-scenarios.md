# Failure Simulation and Recovery Scenarios

This document outlines various failure scenarios that can be simulated in the SRE Kubernetes environment to test resilience and recovery mechanisms.

## Scenario 1: Database Outage

### Description
Simulate a PostgreSQL database failure to test application resilience and recovery.

### Simulation Steps
```bash
# 1. Monitor current state
kubectl get pods -n infrastructure -l app=postgresql

# 2. Simulate database pod failure
kubectl delete pod -n infrastructure -l app=postgresql

# 3. Monitor recovery
kubectl get pods -n infrastructure -w
kubectl logs -n monitoring -l app=prometheus
```

### Expected Behavior
- Applications should show degraded health status
- Prometheus should detect the failure and trigger alerts
- Database pod should be recreated automatically
- Applications should recover once database is back

### Recovery Verification
```bash
# Check if database is back online
kubectl get pods -n infrastructure -l app=postgresql

# Verify application health
kubectl exec -n applications deployment/main-api-service -- curl -s http://localhost:3000/health
```

## Scenario 2: High Traffic Load

### Description
Generate high traffic to test autoscaling and performance under load.

### Simulation Steps
```bash
# 1. Start load testing
./scripts/load-test.sh

# 2. Monitor HPA scaling
kubectl get hpa -A -w

# 3. Check resource usage
kubectl top pods -A
```

### Expected Behavior
- HPA should scale up pods based on CPU/memory usage
- Response times should remain acceptable
- No service downtime during scaling

### Recovery Verification
```bash
# Check if scaling worked
kubectl get pods -n applications

# Verify performance metrics
kubectl logs -n monitoring deployment/prometheus
```

## Scenario 3: Service Failure

### Description
Simulate a service crash to test liveness/readiness probes and restart mechanisms.

### Simulation Steps
```bash
# 1. Monitor service health
kubectl get pods -n applications -l app=auth-service

# 2. Simulate service crash
kubectl delete pod -n applications -l app=auth-service

# 3. Monitor restart
kubectl describe pod -n applications -l app=auth-service
```

### Expected Behavior
- Kubernetes should detect the failure via liveness probe
- Pod should be restarted automatically
- Service should remain available through other replicas
- Health checks should pass after restart

### Recovery Verification
```bash
# Check pod status
kubectl get pods -n applications -l app=auth-service

# Verify service health
kubectl exec -n applications deployment/main-api-service -- curl -s http://auth-service:8080/health
```

## Scenario 4: Network Policy Violation

### Description
Test network policies by attempting unauthorized access between services.

### Simulation Steps
```bash
# 1. Try to access service from unauthorized pod
kubectl run test-pod --image=busybox --rm -it --restart=Never -- \
  sh -c "wget -qO- http://main-api-service:3000/health"

# 2. Check if access is blocked
kubectl logs -n applications deployment/main-api-service
```

### Expected Behavior
- Network policies should block unauthorized access
- Security logs should show blocked connections
- Only authorized communication should succeed

## Scenario 5: Resource Exhaustion

### Description
Simulate resource exhaustion to test resource limits and monitoring.

### Simulation Steps
```bash
# 1. Create resource-intensive workload
kubectl run stress-test --image=busybox --rm -it --restart=Never -- \
  sh -c "while true; do dd if=/dev/zero of=/tmp/stress bs=1M count=100; done"

# 2. Monitor resource usage
kubectl top nodes
kubectl top pods -A
```

### Expected Behavior
- Resource limits should prevent excessive consumption
- Monitoring should detect high resource usage
- Alerts should be triggered for resource exhaustion

## Scenario 6: Certificate Expiration

### Description
Test TLS certificate management and renewal processes.

### Simulation Steps
```bash
# 1. Check certificate status
kubectl get certificates -A

# 2. Monitor cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager
```

### Expected Behavior
- Cert-manager should automatically renew certificates
- No service interruption during renewal
- Proper certificate rotation

## Monitoring and Alerting

### Prometheus Alerts
The following alerts are configured:
- High CPU usage (>80%)
- High memory usage (>85%)
- Service down
- High error rate (>5%)
- High response time (>2s)
- Pod restarting frequently

### Alert Verification
```bash
# Check alert status
kubectl logs -n monitoring deployment/prometheus

# View Grafana dashboards
# Access: http://grafana.sy.sa (admin/admin)
```

## Recovery Procedures

### 1. Service Recovery
```bash
# Restart failed service
kubectl rollout restart deployment/main-api-service -n applications

# Check rollout status
kubectl rollout status deployment/main-api-service -n applications
```

### 2. Database Recovery
```bash
# Check database status
kubectl get pods -n infrastructure -l app=postgresql

# Restart if needed
kubectl rollout restart deployment/postgresql -n infrastructure
```

### 3. Monitoring Recovery
```bash
# Restart monitoring components
kubectl rollout restart deployment/prometheus -n monitoring
kubectl rollout restart deployment/grafana -n monitoring
```

## Lessons Learned

1. **Probe Configuration**: Proper liveness/readiness probes are crucial for detecting failures
2. **Resource Limits**: Setting appropriate limits prevents resource exhaustion
3. **Monitoring**: Comprehensive monitoring helps detect issues before they become critical
4. **Network Policies**: Defense in depth with network policies improves security
5. **Automation**: Automated recovery mechanisms reduce manual intervention

## Improvement Suggestions

1. **Chaos Engineering**: Implement chaos monkey for automated failure testing
2. **Backup Strategy**: Implement automated backup and disaster recovery
3. **Service Mesh**: Consider Istio for advanced traffic management
4. **GitOps**: Use ArgoCD or Flux for GitOps deployment
5. **Cost Optimization**: Implement resource quotas and cost monitoring 