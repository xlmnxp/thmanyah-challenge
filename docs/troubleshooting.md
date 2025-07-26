# Troubleshooting Guide

This guide provides solutions for common issues encountered in the SRE Kubernetes environment.

## Common Issues and Solutions

### 1. Pod Startup Issues

#### Problem: Pods stuck in Pending state
```bash
# Check pod status
kubectl get pods --all-namespaces

# Check events
kubectl get events --sort-by='.lastTimestamp'

# Check node resources
kubectl describe nodes
```

**Solutions:**
- Ensure cluster has sufficient resources
- Check if there are resource quotas limiting pod creation
- Verify node selectors and affinity rules

#### Problem: Pods stuck in CrashLoopBackOff
```bash
# Check pod logs
kubectl logs -f pod/<pod-name> -n <namespace>

# Check pod description
kubectl describe pod <pod-name> -n <namespace>

# Check previous logs if container restarted
kubectl logs -f pod/<pod-name> -n <namespace> --previous
```

**Solutions:**
- Check application logs for errors
- Verify environment variables and secrets
- Check resource limits and requests
- Verify health check endpoints

### 2. Service Connectivity Issues

#### Problem: Services cannot communicate
```bash
# Check service endpoints
kubectl get endpoints -n <namespace>

# Test connectivity from within cluster
kubectl run test-pod --image=busybox --rm -it --restart=Never -- \
  sh -c "wget -qO- http://<service-name>:<port>/health"

# Check network policies
kubectl get networkpolicies --all-namespaces
```

**Solutions:**
- Verify service selectors match pod labels
- Check network policies are not blocking traffic
- Ensure services are in the same namespace or properly configured for cross-namespace communication

#### Problem: External access not working
```bash
# Check ingress status
kubectl get ingress --all-namespaces

# Check ingress controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller

# Check service type and ports
kubectl get svc --all-namespaces
```

**Solutions:**
- Verify ingress controller is running
- Check ingress rules and hostnames
- Ensure services are properly exposed
- Verify TLS certificates if using HTTPS

### 3. Database Connection Issues

#### Problem: Cannot connect to PostgreSQL
```bash
# Check database pod status
kubectl get pods -n infrastructure -l app=postgresql

# Check database logs
kubectl logs -n infrastructure deployment/postgresql

# Test database connectivity
kubectl run test-db --image=postgres:15-alpine --rm -it --restart=Never -- \
  sh -c "psql -h postgresql-service -U postgres -d sre_db -c 'SELECT 1;'"
```

**Solutions:**
- Verify database pod is running
- Check database credentials in secrets
- Ensure network policies allow database access
- Verify database initialization completed

#### Problem: Redis connection issues
```bash
# Check Redis pod status
kubectl get pods -n infrastructure -l app=redis

# Check Redis logs
kubectl logs -n infrastructure deployment/redis

# Test Redis connectivity
kubectl run test-redis --image=redis:7-alpine --rm -it --restart=Never -- \
  sh -c "redis-cli -h redis-service ping"
```

**Solutions:**
- Verify Redis pod is running
- Check Redis configuration
- Ensure network policies allow Redis access

### 4. Monitoring Issues

#### Problem: Prometheus not scraping metrics
```bash
# Check Prometheus pod status
kubectl get pods -n monitoring -l app=prometheus

# Check Prometheus logs
kubectl logs -n monitoring deployment/prometheus

# Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Then visit http://localhost:9090/targets
```

**Solutions:**
- Verify Prometheus configuration
- Check if services have proper annotations for scraping
- Ensure RBAC permissions are correct
- Verify network policies allow scraping

#### Problem: Grafana cannot access Prometheus
```bash
# Check Grafana pod status
kubectl get pods -n monitoring -l app=grafana

# Check Grafana logs
kubectl logs -n monitoring deployment/grafana

# Verify datasource configuration
kubectl get configmap -n monitoring grafana-datasources -o yaml
```

**Solutions:**
- Verify Prometheus service is accessible
- Check Grafana datasource configuration
- Ensure both services are in the same namespace

### 5. Autoscaling Issues

#### Problem: HPA not scaling
```bash
# Check HPA status
kubectl get hpa -A

# Check HPA description
kubectl describe hpa <hpa-name> -n <namespace>

# Check metrics server
kubectl top pods -A
```

**Solutions:**
- Verify metrics server is running
- Check resource requests and limits are set
- Ensure HPA metrics are available
- Check HPA configuration and thresholds

### 6. Security Issues

#### Problem: Network policies blocking legitimate traffic
```bash
# Check network policies
kubectl get networkpolicies --all-namespaces

# Test connectivity with network policies
kubectl run test-connectivity --image=busybox --rm -it --restart=Never -- \
  sh -c "wget -qO- http://<target-service>:<port>/health"
```

**Solutions:**
- Review network policy rules
- Add necessary ingress/egress rules
- Test connectivity step by step
- Use temporary policy to isolate issues

#### Problem: Certificate issues
```bash
# Check certificate status
kubectl get certificates -A

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager

# Check certificate events
kubectl get events --field-selector involvedObject.kind=Certificate
```

**Solutions:**
- Verify cert-manager is running
- Check ClusterIssuer configuration
- Ensure domain ownership for Let's Encrypt
- Check certificate renewal process

### 7. Resource Issues

#### Problem: High resource usage
```bash
# Check resource usage
kubectl top nodes
kubectl top pods -A

# Check resource limits
kubectl describe pod <pod-name> -n <namespace>

# Check node capacity
kubectl describe nodes
```

**Solutions:**
- Adjust resource requests and limits
- Scale up cluster nodes
- Optimize application resource usage
- Implement resource quotas

### 8. Application-Specific Issues

#### Problem: Main API Service issues
```bash
# Check service health
kubectl exec -n applications deployment/main-api-service -- curl -s http://localhost:3000/health

# Check service logs
kubectl logs -f deployment/main-api-service -n applications

# Check service metrics
kubectl exec -n applications deployment/main-api-service -- curl -s http://localhost:3000/metrics
```

#### Problem: Auth Service issues
```bash
# Check service health
kubectl exec -n applications deployment/auth-service -- wget -qO- http://localhost:8080/health

# Check service logs
kubectl logs -f deployment/auth-service -n applications

# Check JWT secret
kubectl get secret jwt-secret -n applications -o yaml
```

#### Problem: Image Service issues
```bash
# Check service health
kubectl exec -n applications deployment/image-service -- curl -s http://localhost:5000/health

# Check service logs
kubectl logs -f deployment/image-service -n applications

# Check MinIO connectivity
kubectl exec -n applications deployment/image-service -- curl -s http://minio-service:9000/minio/health/live
```

## Debug Commands

### General Debugging
```bash
# Get all resources in a namespace
kubectl get all -n <namespace>

# Describe any resource
kubectl describe <resource-type> <resource-name> -n <namespace>

# Get events for a namespace
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Check resource quotas
kubectl get resourcequota --all-namespaces

# Check limit ranges
kubectl get limitrange --all-namespaces
```

### Network Debugging
```bash
# Check DNS resolution
kubectl run test-dns --image=busybox --rm -it --restart=Never -- nslookup <service-name>

# Check network connectivity
kubectl run test-connectivity --image=busybox --rm -it --restart=Never -- \
  sh -c "wget -qO- http://<service-name>:<port>/health"

# Check network policies
kubectl get networkpolicies --all-namespaces -o yaml
```

### Storage Debugging
```bash
# Check persistent volumes
kubectl get pv,pvc --all-namespaces

# Check storage classes
kubectl get storageclass

# Check volume mounts
kubectl describe pod <pod-name> -n <namespace>
```

## Performance Optimization

### Resource Optimization
```bash
# Analyze resource usage
kubectl top pods -A --sort-by=cpu
kubectl top pods -A --sort-by=memory

# Check resource efficiency
kubectl describe nodes | grep -A 5 "Allocated resources"
```

### Scaling Optimization
```bash
# Check HPA behavior
kubectl describe hpa -A

# Monitor scaling events
kubectl get events --field-selector reason=ScalingReplicaSet
```

## Recovery Procedures

### Service Recovery
```bash
# Restart a deployment
kubectl rollout restart deployment/<deployment-name> -n <namespace>

# Check rollout status
kubectl rollout status deployment/<deployment-name> -n <namespace>

# Rollback if needed
kubectl rollout undo deployment/<deployment-name> -n <namespace>
```

### Data Recovery
```bash
# Backup PostgreSQL
kubectl exec -n infrastructure deployment/postgresql -- pg_dump -U postgres sre_db > backup.sql

# Restore PostgreSQL
kubectl exec -i -n infrastructure deployment/postgresql -- psql -U postgres sre_db < backup.sql
```

### Cluster Recovery
```bash
# Check cluster health
kubectl get componentstatuses

# Check node health
kubectl get nodes
kubectl describe nodes

# Check system pods
kubectl get pods -n kube-system
```

## Prevention Best Practices

1. **Regular Monitoring**: Set up comprehensive monitoring and alerting
2. **Resource Planning**: Properly size resource requests and limits
3. **Security**: Implement network policies and RBAC
4. **Backup Strategy**: Regular backups of critical data
5. **Testing**: Regular load testing and failure simulation
6. **Documentation**: Keep runbooks and procedures updated
7. **Automation**: Automate recovery procedures where possible

## Getting Help

If you encounter issues not covered in this guide:

1. Check the application logs for specific error messages
2. Review the failure scenarios documentation
3. Check Kubernetes and application documentation
4. Monitor the system metrics and alerts
5. Consider implementing additional monitoring and alerting 