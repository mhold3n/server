# MLflow Management Runbook

## Overview
This runbook covers operational procedures for MLflow experiment tracking and model registry on the Birtha platform.

## MLflow Architecture

### Components
- **MLflow Server**: Experiment tracking and model registry
- **PostgreSQL**: Metadata storage
- **MinIO**: Artifact storage
- **MLflow Client**: Python SDK for logging

### Service Endpoints
- **MLflow UI**: `http://localhost:5000`
- **MLflow API**: `http://localhost:5000/api`
- **PostgreSQL**: `localhost:5432`
- **MinIO**: `http://localhost:9000`

## Deployment Procedures

### Initial Setup
```bash
# Start platform services
make platform-up

# Verify MLflow is running
curl -f http://localhost:5000/health
```

### Environment Configuration
```bash
# Set MLflow environment variables
export MLFLOW_TRACKING_URI="http://localhost:5000"
export MLFLOW_S3_ENDPOINT_URL="http://localhost:9000"
export AWS_ACCESS_KEY_ID="minioadmin"
export AWS_SECRET_ACCESS_KEY="minioadmin"
```

## Experiment Management

### Creating Experiments
```python
import mlflow

# Set tracking URI
mlflow.set_tracking_uri("http://localhost:5000")

# Create experiment
experiment_id = mlflow.create_experiment("WrkHrs_Birtha_Integration")
mlflow.set_experiment("WrkHrs_Birtha_Integration")
```

### Logging Runs
```python
# Start run
with mlflow.start_run(run_name="test-run") as run:
    # Log parameters
    mlflow.log_params({
        "model_type": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 1000
    })
    
    # Log metrics
    mlflow.log_metrics({
        "accuracy": 0.95,
        "latency": 150.5
    })
    
    # Log artifacts
    mlflow.log_artifact("model.pkl")
    mlflow.log_dict({"config": "value"}, "config.json")
```

### Querying Experiments
```python
# List experiments
experiments = mlflow.search_experiments()
for exp in experiments:
    print(f"Experiment: {exp.name}, ID: {exp.experiment_id}")

# Search runs
runs = mlflow.search_runs(experiment_ids=["1"])
print(runs.head())
```

## Model Registry

### Registering Models
```python
# Register model
model_version = mlflow.register_model(
    model_uri="runs:/{run_id}/model",
    name="wrkhrs-gateway-model"
)

# Add model description
mlflow.update_model_version(
    name="wrkhrs-gateway-model",
    version=1,
    description="WrkHrs Gateway AI Model"
)
```

### Model Lifecycle Management
```python
# Transition model stage
mlflow.transition_model_version_stage(
    name="wrkhrs-gateway-model",
    version=1,
    stage="Production"
)

# Get model for inference
model = mlflow.pyfunc.load_model(
    model_uri="models:/wrkhrs-gateway-model/Production"
)
```

## Data Management

### Backup Procedures
```bash
# Backup MLflow database
docker exec postgres pg_dump -U mlflow mlflow_db > mlflow_backup.sql

# Backup MinIO artifacts
docker run --rm -v minio_data:/data -v $(pwd):/backup alpine tar czf /backup/minio_backup.tar.gz -C /data .
```

### Restore Procedures
```bash
# Restore MLflow database
docker exec -i postgres psql -U mlflow mlflow_db < mlflow_backup.sql

# Restore MinIO artifacts
docker run --rm -v minio_data:/data -v $(pwd):/backup alpine tar xzf /backup/minio_backup.tar.gz -C /data
```

## Monitoring and Maintenance

### Health Checks
```bash
# Check MLflow server
curl -f http://localhost:5000/health

# Check PostgreSQL
docker exec postgres pg_isready -U mlflow

# Check MinIO
curl -f http://localhost:9000/minio/health/live
```

### Performance Monitoring
```bash
# Monitor database size
docker exec postgres psql -U mlflow -c "SELECT pg_size_pretty(pg_database_size('mlflow_db'));"

# Monitor MinIO usage
docker exec minio mc du /data
```

### Log Management
```bash
# View MLflow logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml logs mlflow

# View PostgreSQL logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml logs postgres

# View MinIO logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml logs minio
```

## Troubleshooting

### Common Issues

#### 1. MLflow Server Unavailable
**Symptoms**: 503 errors, connection refused
**Diagnosis**:
```bash
# Check service status
docker ps | grep mlflow

# Check logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml logs mlflow
```
**Resolution**:
- Restart MLflow: `docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml restart mlflow`
- Check PostgreSQL connectivity
- Verify MinIO access

#### 2. Database Connection Issues
**Symptoms**: Database connection errors
**Diagnosis**:
```bash
# Check PostgreSQL status
docker exec postgres pg_isready -U mlflow

# Check database connectivity
docker exec postgres psql -U mlflow -c "SELECT 1;"
```
**Resolution**:
- Restart PostgreSQL: `docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml restart postgres`
- Check database credentials
- Verify network connectivity

#### 3. Artifact Storage Issues
**Symptoms**: Artifact upload/download failures
**Diagnosis**:
```bash
# Check MinIO status
curl -f http://localhost:9000/minio/health/live

# Check MinIO logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml logs minio
```
**Resolution**:
- Restart MinIO: `docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml restart minio`
- Check storage permissions
- Verify S3 credentials

#### 4. High Database Usage
**Symptoms**: Slow queries, high CPU usage
**Diagnosis**:
```bash
# Check database size
docker exec postgres psql -U mlflow -c "SELECT pg_size_pretty(pg_database_size('mlflow_db'));"

# Check active connections
docker exec postgres psql -U mlflow -c "SELECT count(*) FROM pg_stat_activity;"
```
**Resolution**:
- Optimize database queries
- Implement connection pooling
- Consider database scaling

### Performance Optimization

#### Database Optimization
```sql
-- Create indexes for common queries
CREATE INDEX idx_runs_experiment_id ON runs(experiment_id);
CREATE INDEX idx_runs_start_time ON runs(start_time);
CREATE INDEX idx_metrics_run_id ON metrics(run_id);

-- Analyze table statistics
ANALYZE runs;
ANALYZE metrics;
ANALYZE params;
```

#### Storage Optimization
```bash
# Clean up old artifacts
docker exec minio mc rm --recursive --force /data/old-artifacts

# Compress large artifacts
docker exec minio mc cp --recursive /data/artifacts /data/compressed-artifacts
```

## Security Management

### Access Control
```bash
# Set up MLflow authentication
export MLFLOW_TRACKING_USERNAME="admin"
export MLFLOW_TRACKING_PASSWORD="secure-password"

# Configure PostgreSQL authentication
# Update postgresql.conf and pg_hba.conf
```

### Data Encryption
```bash
# Enable SSL for PostgreSQL
# Update postgresql.conf:
ssl = on
ssl_cert_file = '/etc/ssl/certs/server.crt'
ssl_key_file = '/etc/ssl/private/server.key'

# Enable HTTPS for MinIO
# Update MinIO configuration
```

### Backup Security
```bash
# Encrypt backups
gpg --symmetric --cipher-algo AES256 mlflow_backup.sql

# Secure backup storage
# Store backups in encrypted storage
# Implement backup rotation
```

## Scaling Procedures

### Horizontal Scaling
```bash
# Scale MLflow server
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml up -d --scale mlflow=3

# Use load balancer for multiple instances
# Configure nginx or similar
```

### Vertical Scaling
```bash
# Update resource limits in docker/compose-profiles/docker-compose.platform.yml
# Then restart services
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml up -d
```

## Data Retention

### Retention Policies
```python
# Implement retention policy
import mlflow
from datetime import datetime, timedelta

# Delete old runs
cutoff_date = datetime.now() - timedelta(days=90)
runs = mlflow.search_runs()
old_runs = runs[runs['start_time'] < cutoff_date]

for run_id in old_runs['run_id']:
    mlflow.delete_run(run_id)
```

### Archival Procedures
```bash
# Archive old experiments
# Move to cold storage
# Implement tiered storage
```

## Integration with AI Services

### WrkHrs Integration
```python
# Log WrkHrs requests
from src.observability.mlflow_logger import MLflowLogger

logger = MLflowLogger()
with logger.start_run("wrkhrs-request") as run:
    logger.log_params({
        "domain": "rag",
        "model": "gpt-3.5-turbo",
        "temperature": 0.7
    })
    
    # Make WrkHrs request
    response = await gateway_client.chat_completion(payload)
    
    logger.log_metrics({
        "response_time": response_time,
        "token_count": len(response['content'])
    })
```

### Policy Enforcement Logging
```python
# Log policy violations
logger.log_metrics({
    "evidence_violations": len(evidence_violations),
    "citation_count": len(citations),
    "hedging_detected": hedging_detected
})
```

## Emergency Procedures

### Service Outage
1. **Immediate Response**:
   - Check service status
   - Review logs
   - Restart affected services

2. **Data Recovery**:
   - Restore from backup
   - Verify data integrity
   - Update service configurations

3. **Communication**:
   - Notify stakeholders
   - Update status page
   - Document incident

### Data Corruption
1. **Assessment**:
   - Identify affected data
   - Check backup integrity
   - Assess impact

2. **Recovery**:
   - Restore from clean backup
   - Verify data consistency
   - Update monitoring

3. **Prevention**:
   - Review backup procedures
   - Implement additional checks
   - Update documentation

## Contact Information

### Support Team
- **Primary**: MLflow Operations Team
- **Secondary**: Data Engineering Team
- **Emergency**: On-call Engineer

### Escalation Path
1. Level 1: MLflow Operations Team
2. Level 2: Data Engineering Team
3. Level 3: Engineering Management
4. Level 4: CTO Office

### Communication Channels
- **Slack**: #mlflow-operations
- **Email**: mlflow-ops@company.com
- **Phone**: +1-555-MLFLOW











