# AI Stack Operations Runbook

## Overview
This runbook covers operational procedures for the WrkHrs AI stack services running on the Birtha platform.

## Services Overview

### Core AI Services
- **wrkhrs-gateway**: Main API gateway for AI requests
- **wrkhrs-agent-platform**: TypeScript orchestration (Open Multi-Agent + LangGraph JS); default replacement for the retired Python orchestrator
- **wrkhrs-rag**: Retrieval-augmented generation service
- **wrkhrs-asr**: Automatic speech recognition service
- **model-runtime**: Bounded local HF model runtime for `/infer/*` roles; defaults to mock inference in dev
- **wrkhrs-tool-registry**: Tool discovery and registration
- **wrkhrs-mcp**: Micro-capability platform service

### Supporting Services
- **qdrant**: Vector database for embeddings
- **mlflow**: Experiment tracking and model registry
- **postgres**: Database for MLflow metadata
- **minio**: Object storage for MLflow artifacts

## Deployment Procedures

### Initial Deployment
```bash
# Start platform services first
make platform-up

# Start AI stack services
make ai-up

# Verify deployment
make health
```

### Service-Specific Deployment
```bash
# Deploy only RAG service
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml up -d wrkhrs-rag

# Deploy only ASR service
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml up -d wrkhrs-asr
```

## Health Monitoring

### Health Check Endpoints
- **Gateway**: `http://localhost:8091/health` (see `WRKHRS_GATEWAY_PORT`)
- **Agent platform (TS orchestrator)**: `http://localhost:8087/health` (see `WRKHRS_AGENT_PLATFORM_PORT`)
- **Legacy Python orchestrator** (opt-in profile `legacy-python-orchestrator`): `http://localhost:8081/health`
- **RAG**: `http://localhost:8082/health`
- **ASR**: `http://localhost:8084/health`
- **Model runtime**: `http://localhost:${MODEL_RUNTIME_PORT:-8765}/health`
- **Tool Registry**: `http://localhost:8086/health`
- **MCP**: `http://localhost:8085/health`

### Health Check Script
```bash
# Run comprehensive health check
./scripts/health_check.sh

# Check specific service
curl -f http://localhost:8080/health
```

### Log Monitoring
```bash
# View all AI stack logs
make logs-ai

# View specific service logs
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml logs -f wrkhrs-gateway
```

## Troubleshooting

### Common Issues

#### 1. Gateway Service Unavailable
**Symptoms**: 503 errors, connection refused
**Diagnosis**:
```bash
# Check service status
docker ps | grep wrkhrs-gateway

# Check logs
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml logs wrkhrs-gateway
```
**Resolution**:
- Restart service: `docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml restart wrkhrs-gateway`
- Check dependencies: Ensure **wrkhrs-agent-platform**, RAG, ASR services are running
- Verify `ORCHESTRATOR_URL` (default `http://wrkhrs-agent-platform:8000`)

### Agent platform (orchestration) configuration

- **Gateway → orchestrator**: `ORCHESTRATOR_URL` on `wrkhrs-gateway` must point at the TS service (default above).
- **LLM**: Set `LLM_BACKEND` (`mock`, `ollama`, `vllm`, `huggingface`) and `LLM_RUNNER_URL` consistently with your worker. Ollama uses native `/api/chat`; vLLM uses OpenAI-compatible `/v1`; hosted Hugging Face uses `HF_INFERENCE_BASE_URL=https://router.huggingface.co/v1` plus `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN`.
- **Per-request routing hints**: `/api/ai/query` and internal workflow runs may set `provider` / `provider_preference` to `local_worker`, `ollama`, `vllm`, `huggingface`, `hosted_api`, or an enabled direct provider. Model, temperature, and max-token hints are forwarded through `workflow_config.model_routing`.
- **Open Multi-Agent team/agent HTTP routes** (`/v1/teams/run`, `/v1/agents/run`): set `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`, plus `OMA_DEFAULT_MODEL` and `OMA_DEFAULT_PROVIDER` as needed.
- **`POST /llm/switch`**: The TS service does not hot-reload backends; change `LLM_BACKEND` / `LLM_RUNNER_URL` and restart the container (legacy Python supported runtime switch).
- **RAG embeddings**: Set `EMBEDDING_BACKEND=auto|openai|ollama|local|mock`. Use `EMBEDDING_ENDPOINT_URL` for OpenAI-compatible `/v1/embeddings` or Ollama `/api/embed` endpoints.
- **RAG reranking**: Set `RERANKER_URL` to a service exposing `/rerank`. RAG falls back to existing BM25 plus embedding scoring if reranking fails.
- **Model-runtime HF mode**: Keep `MOCK_INFER=1` for dev smoke tests. Set `MOCK_INFER=0` and configure `services/model-runtime/config/models.yaml` with `local_model_path` for offline Transformers loading.

#### 2. RAG Service Performance Issues
**Symptoms**: Slow responses, high memory usage
**Diagnosis**:
```bash
# Check resource usage
docker stats wrkhrs-rag

# Check Qdrant connectivity
curl -f http://localhost:6333/collections
```
**Resolution**:
- Scale RAG service: Increase memory limits
- Check Qdrant performance: Monitor vector search latency
- Optimize embedding model: Consider smaller model for production

#### 3. ASR Service GPU Issues
**Symptoms**: CUDA errors, slow transcription
**Diagnosis**:
```bash
# Check GPU availability
nvidia-smi

# Check ASR logs
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml logs wrkhrs-asr
```
**Resolution**:
- Verify NVIDIA Container Toolkit installation
- Check GPU memory allocation
- Fallback to CPU mode if GPU unavailable

#### 4. Tool Registry Service Issues
**Symptoms**: Tools not discovered, MCP connection failures
**Diagnosis**:
```bash
# Check tool registry
curl -f http://localhost:8086/health

# Check MCP service
curl -f http://localhost:8085/health
```
**Resolution**:
- Restart tool registry: `docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml restart wrkhrs-tool-registry`
- Check MCP server connectivity
- Verify tool registration

### Performance Optimization

#### Memory Management
```bash
# Monitor memory usage
docker stats

# Set memory limits
# In compose/docker-compose.ai.yml:
deploy:
  resources:
    limits:
      memory: 2G
    reservations:
      memory: 1G
```

#### CPU Optimization
```bash
# Monitor CPU usage
docker stats

# Set CPU limits
# In compose/docker-compose.ai.yml:
deploy:
  resources:
    limits:
      cpus: '2.0'
    reservations:
      cpus: '1.0'
```

## Scaling Procedures

### Horizontal Scaling
```bash
# Scale RAG service
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml up -d --scale wrkhrs-rag=3

# Scale ASR service
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml up -d --scale wrkhrs-asr=2
```

### Vertical Scaling
```bash
# Update resource limits in compose/docker-compose.ai.yml
# Then restart services
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml up -d
```

## Backup and Recovery

### Data Backup
```bash
# Backup Qdrant data
docker run --rm -v qdrant_data:/data -v $(pwd):/backup alpine tar czf /backup/qdrant_backup.tar.gz -C /data .

# Backup MLflow data
docker run --rm -v mlflow_data:/data -v $(pwd):/backup alpine tar czf /backup/mlflow_backup.tar.gz -C /data .
```

### Data Recovery
```bash
# Restore Qdrant data
docker run --rm -v qdrant_data:/data -v $(pwd):/backup alpine tar xzf /backup/qdrant_backup.tar.gz -C /data

# Restore MLflow data
docker run --rm -v mlflow_data:/data -v $(pwd):/backup alpine tar xzf /backup/mlflow_backup.tar.gz -C /data
```

## Security Considerations

### API Key Management
```bash
# Set environment variables
export WRKHRS_API_KEY="your-api-key"
export MLFLOW_TRACKING_URI="http://mlflow:5000"
```

### Network Security
- Use internal networks for service communication
- Implement TLS for external access
- Configure firewall rules for service ports

### Data Privacy
- Encrypt sensitive data in transit
- Implement access controls for MLflow
- Regular security audits of AI models

## Monitoring and Alerting

### Metrics Collection
- **Response Time**: Monitor API response times
- **Error Rate**: Track service error rates
- **Resource Usage**: Monitor CPU, memory, disk usage
- **Model Performance**: Track AI model accuracy and latency

### Alerting Rules
```yaml
# Example Prometheus alerting rules
- alert: WrkHrsGatewayDown
  expr: up{job="wrkhrs-gateway"} == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "WrkHrs Gateway is down"

- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "High error rate detected"
```

## Maintenance Procedures

### Regular Maintenance
```bash
# Weekly health check
make health

# Monthly log cleanup
docker system prune -f

# Quarterly model updates
# Update embedding models
# Update ASR models
# Update LLM models
```

### Service Updates
```bash
# Update AI stack
git pull origin main
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml build
docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml up -d

# Verify update
make health
```

## Emergency Procedures

### Service Outage
1. **Immediate Response**:
   - Check service status: `docker ps`
   - Check logs: `make logs-ai`
   - Restart affected services

2. **Escalation**:
   - Contact system administrator
   - Check infrastructure status
   - Implement fallback procedures

3. **Recovery**:
   - Restore from backup if needed
   - Verify service functionality
   - Update monitoring alerts

### Data Loss
1. **Assessment**:
   - Identify affected data
   - Check backup availability
   - Assess impact

2. **Recovery**:
   - Restore from latest backup
   - Verify data integrity
   - Update service configurations

3. **Prevention**:
   - Review backup procedures
   - Implement additional safeguards
   - Update documentation

## Contact Information

### Support Team
- **Primary**: AI Operations Team
- **Secondary**: Platform Engineering Team
- **Emergency**: On-call Engineer

### Escalation Path
1. Level 1: AI Operations Team
2. Level 2: Platform Engineering Team
3. Level 3: Engineering Management
4. Level 4: CTO Office

### Communication Channels
- **Slack**: #ai-operations
- **Email**: ai-ops@company.com
- **Phone**: +1-555-AI-OPS










