# GPU Worker Setup Runbook

## Overview
This runbook covers setup and operational procedures for the GPU worker workstation running LLM inference services for the Birtha platform.

## GPU Worker Architecture

### Hardware Requirements
- **GPU**: NVIDIA RTX 4070 Ti (12GB VRAM)
- **CPU**: 8+ cores recommended
- **RAM**: 32GB+ recommended
- **Storage**: 100GB+ for models and data
- **Network**: Gigabit Ethernet for server communication

### Software Requirements
- **OS**: Ubuntu 20.04+ or Windows 10/11
- **Docker**: 20.10+
- **NVIDIA Container Toolkit**: Latest version
- **CUDA**: 11.8+ (if using vLLM)
- **Python**: 3.10+ (if using Ollama)

## Initial Setup

### 1. Install NVIDIA Container Toolkit
```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Verify installation
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
```

### 2. Configure Docker for GPU
```bash
# Update Docker daemon configuration
sudo tee /etc/docker/daemon.json <<EOF
{
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtime_args": []
    }
  }
}
EOF

# Restart Docker
sudo systemctl restart docker
```

### 3. Set Up Environment
```bash
# Create environment file
cp machine-config/env.template .env

# Update GPU-specific settings
cat >> .env <<EOF
# GPU Worker Configuration
ENABLE_GPU=true
LLM_BACKEND=vllm
VLLM_MODEL=/.cache/models/vllm/Mistral-7B-Instruct-v0.3
VLLM_MAX_MODEL_LEN=8192
VLLM_GPU_MEMORY_UTILIZATION=0.92
WORKER_VLLM_PORT=8000
WORKER_OLLAMA_PORT=11434
WORKER_PROXY_PORT=8443
EOF
```

## Service Deployment

### 1. Deploy LLM Runner (vLLM)
```bash
# Start vLLM service
make worker-up

# Verify deployment
docker ps | grep llm-runner

# Check GPU usage
nvidia-smi
```

### 2. Deploy Ollama (Alternative)
```bash
# Start Ollama service
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml --profile ollama up -d

# Verify deployment
docker ps | grep ollama-runner

# Check GPU usage
nvidia-smi
```

### 3. Deploy Reverse Proxy
```bash
# Start Caddy proxy
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml up -d caddy

# Verify deployment
curl -f http://localhost:8443/health
```

## Model Management

### 1. Download Models
```bash
# Download vLLM model
docker run --rm -v $(pwd)/.cache/models/vllm:/.cache/models/vllm \
  -e HF_TOKEN=$HF_TOKEN \
  "${VLLM_IMAGE:-vllm/vllm-openai@sha256:7a0f0fdd2771464b6976625c2b2d5dd46f566aa00fbc53eceab86ef50883da90}" \
  python -c "
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
model_name = 'mistralai/Mistral-7B-Instruct-v0.3'
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
tokenizer.save_pretrained('/.cache/models/vllm/Mistral-7B-Instruct-v0.3')
model.save_pretrained('/.cache/models/vllm/Mistral-7B-Instruct-v0.3')
"

# Download Ollama model (Qwen-first; matches docker-compose.worker.yml default OLLAMA_MODEL)
docker run --rm -v ollama_data:/root/.ollama "${OLLAMA_IMAGE:-ollama/ollama@sha256:1375516e575632dd84ad23b2c1cbd5e36ef34ebe8e41f9857545ab9aa72aeec2}" \
  ollama pull qwen3:4b-instruct
```

### 2. Model Configuration
```bash
# Update model settings in .env
VLLM_MODEL=/.cache/models/vllm/Mistral-7B-Instruct-v0.3
OLLAMA_MODEL=qwen3:4b-instruct

# Configure model parameters
VLLM_MAX_MODEL_LEN=8192
VLLM_GPU_MEMORY_UTILIZATION=0.92
VLLM_DTYPE=float16
VLLM_ENABLE_PREFIX_CACHING=true
```

## Health Monitoring

### 1. Service Health Checks
```bash
# Check vLLM service
curl -f http://localhost:8000/health

# Check Ollama service
curl -f http://localhost:11434/api/tags

# Check Caddy proxy
curl -f http://localhost:8443/health
```

### 2. GPU Monitoring
```bash
# Monitor GPU usage
watch -n 1 nvidia-smi

# Check GPU memory
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Monitor GPU temperature
nvidia-smi --query-gpu=temperature.gpu --format=csv
```

### 3. Log Monitoring
```bash
# View vLLM logs
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml logs -f llm-runner

# View Ollama logs
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml logs -f ollama-runner

# View Caddy logs
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml logs -f caddy
```

## Performance Optimization

### 1. GPU Memory Management
```bash
# Monitor GPU memory usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Optimize memory allocation
# Update VLLM_GPU_MEMORY_UTILIZATION in .env
VLLM_GPU_MEMORY_UTILIZATION=0.92  # Use 92% of GPU memory
```

### 2. Model Optimization
```bash
# Use quantized models for better performance
VLLM_DTYPE=float16  # Use half precision
VLLM_ENABLE_PREFIX_CACHING=true  # Enable prefix caching

# Configure batch processing
VLLM_MAX_MODEL_LEN=8192  # Maximum sequence length
VLLM_BATCH_SIZE=32  # Batch size for processing
```

### 3. Network Optimization
```bash
# Configure network settings
# Update Caddy configuration for optimal routing
# Implement connection pooling
# Use HTTP/2 for better performance
```

## Troubleshooting

### Common Issues

#### 1. GPU Not Detected
**Symptoms**: CUDA errors, GPU not available
**Diagnosis**:
```bash
# Check GPU availability
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
```
**Resolution**:
- Install NVIDIA Container Toolkit
- Restart Docker daemon
- Verify GPU drivers

#### 2. Out of Memory Errors
**Symptoms**: CUDA out of memory, service crashes
**Diagnosis**:
```bash
# Check GPU memory usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Check service logs
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml logs llm-runner
```
**Resolution**:
- Reduce model size
- Decrease batch size
- Optimize memory allocation

#### 3. Model Loading Issues
**Symptoms**: Model not found, loading failures
**Diagnosis**:
```bash
# Check model files
ls -la models/

# Check service logs
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml logs llm-runner
```
**Resolution**:
- Verify model path
- Check model format
- Re-download model

#### 4. Network Connectivity Issues
**Symptoms**: Connection refused, timeout errors
**Diagnosis**:
```bash
# Check service status
docker ps | grep llm-runner

# Test connectivity
curl -f http://localhost:8000/health
```
**Resolution**:
- Restart services
- Check firewall settings
- Verify network configuration

### Performance Issues

#### High Latency
**Symptoms**: Slow responses, timeout errors
**Diagnosis**:
```bash
# Monitor GPU usage
watch -n 1 nvidia-smi

# Check service logs
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml logs llm-runner
```
**Resolution**:
- Optimize model parameters
- Increase GPU memory allocation
- Implement caching

#### Low Throughput
**Symptoms**: Low requests per second
**Diagnosis**:
```bash
# Monitor system resources
htop
iostat -x 1
```
**Resolution**:
- Scale services horizontally
- Optimize batch processing
- Implement load balancing

## Scaling Procedures

### Horizontal Scaling
```bash
# Scale vLLM service
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml up -d --scale llm-runner=3

# Use load balancer for multiple instances
# Configure nginx or similar
```

### Vertical Scaling
```bash
# Update resource limits in docker/compose-profiles/docker-compose.worker.yml
# Then restart services
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml up -d
```

## Security Management

### Access Control
```bash
# Set up authentication
export LLM_API_KEY="your-api-key"
export LLM_SECRET="your-secret"

# Configure service authentication
# Update service configurations
```

### Network Security
```bash
# Configure firewall rules
sudo ufw allow 8000/tcp  # vLLM service
sudo ufw allow 11434/tcp  # Ollama service
sudo ufw allow 8443/tcp  # Caddy proxy

# Implement TLS
# Configure SSL certificates
# Enable HTTPS
```

### Data Encryption
```bash
# Encrypt model storage
# Implement disk encryption
# Secure model access
```

## Backup and Recovery

### Model Backup
```bash
# Backup models
tar czf models_backup.tar.gz models/

# Backup Ollama models
docker run --rm -v ollama_data:/root/.ollama -v $(pwd):/backup alpine tar czf /backup/ollama_backup.tar.gz -C /root/.ollama .
```

### Model Recovery
```bash
# Restore models
tar xzf models_backup.tar.gz

# Restore Ollama models
docker run --rm -v ollama_data:/root/.ollama -v $(pwd):/backup alpine tar xzf /backup/ollama_backup.tar.gz -C /root/.ollama
```

## Maintenance Procedures

### Regular Maintenance
```bash
# Weekly health check
make health

# Monthly log cleanup
docker system prune -f

# Quarterly model updates
# Update model versions
# Update service configurations
```

### Service Updates
```bash
# Update worker services
git pull origin main
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml build
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml up -d

# Verify update
make health
```

## Integration with Birtha Server

### 1. Configure Server Connection
```bash
# Update server configuration
# Set worker URL in server .env
WORKER_URL=http://gpu-worker:8443
WORKER_API_KEY=your-api-key
```

### 2. Test Integration
```bash
# Test LLM inference
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistralai/Mistral-7B-Instruct-v0.3",
    "messages": [{"role": "user", "content": "Hello, world!"}]
  }'
```

### 3. Monitor Integration
```bash
# Check server logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.server.yml logs -f

# Check worker logs
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml logs -f
```

## Emergency Procedures

### Service Outage
1. **Immediate Response**:
   - Check service status
   - Review logs
   - Restart affected services

2. **Escalation**:
   - Contact GPU operations team
   - Check hardware status
   - Implement fallback procedures

3. **Recovery**:
   - Restart services
   - Verify GPU functionality
   - Update monitoring alerts

### Hardware Issues
1. **Assessment**:
   - Check GPU status
   - Verify hardware connectivity
   - Assess impact

2. **Recovery**:
   - Restart GPU services
   - Check driver status
   - Verify model loading

3. **Prevention**:
   - Implement hardware monitoring
   - Set up alerts
   - Update documentation

## Contact Information

### Support Team
- **Primary**: GPU Operations Team
- **Secondary**: AI Engineering Team
- **Emergency**: On-call Engineer

### Escalation Path
1. Level 1: GPU Operations Team
2. Level 2: AI Engineering Team
3. Level 3: Engineering Management
4. Level 4: CTO Office

### Communication Channels
- **Slack**: #gpu-operations
- **Email**: gpu-ops@company.com
- **Phone**: +1-555-GPU-OPS








