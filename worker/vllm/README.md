# vLLM GPU Worker Setup

This directory contains configuration and documentation for running vLLM as a GPU worker for the agent-orchestrator system.

## Overview

vLLM (Very Large Language Model inference) provides high-performance inference for large language models with features like:
- PagedAttention for efficient memory management
- Continuous batching for high throughput
- OpenAI-compatible API
- Support for various model formats (Hugging Face, AWQ, GPTQ)

## Prerequisites

### Hardware Requirements
- NVIDIA GPU with at least 12GB VRAM (RTX 4070 Ti recommended)
- CUDA-compatible GPU driver
- Sufficient system RAM (16GB+ recommended)

### Software Requirements
- Docker with NVIDIA Container Toolkit
- NVIDIA driver 470.57.02 or later
- CUDA 11.8 or later

## Installation

### 1. Install NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Verify GPU Access

```bash
# Test GPU access in Docker
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Model configuration (GPU path / no-compromises)
MODEL_NAME=Qwen/Qwen3.5-9B
HF_TOKEN=your_huggingface_token

# GPU configuration
CUDA_VISIBLE_DEVICES=0
GPU_MEMORY_UTILIZATION=0.92

# API configuration
WORKER_VLLM_PORT=8000
WORKER_PROXY_PORT=8443

# Performance tuning
MAX_MODEL_LEN=32768
DTYPE=bfloat16
ENABLE_PREFIX_CACHING=true
```

### Model Selection

#### Recommended Models for 12GB VRAM

| Model | Size | VRAM Usage | Context Length | Performance |
|-------|------|------------|----------------|-------------|
| Mistral-7B-Instruct-v0.3 | 7B | ~8GB | 32K | Excellent |
| Llama-2-7B-Chat | 7B | ~8GB | 4K | Good |
| CodeLlama-7B-Instruct | 7B | ~8GB | 16K | Good |
| Qwen-7B-Chat | 7B | ~8GB | 32K | Excellent |

#### Quantized Models (Lower VRAM)

| Model | Quantization | VRAM Usage | Quality |
|-------|-------------|------------|---------|
| Mistral-7B-Instruct-AWQ | AWQ | ~4GB | High |
| Llama-2-7B-Chat-GPTQ | GPTQ | ~4GB | High |
| CodeLlama-7B-Instruct-GPTQ | GPTQ | ~4GB | High |

## Running vLLM

### Using Docker Compose

```bash
cd /path/to/server

# Start Qwen3.5-9B vLLM worker on GPU host (paths assume repo root as project directory)
docker compose --project-directory "$(pwd)" -f worker/vllm/docker-compose.vllm.yml up -d

# View logs
docker compose --project-directory "$(pwd)" -f worker/vllm/docker-compose.vllm.yml logs -f qwen-vllm
```

### Manual Docker Run

```bash
docker run --gpus all \
  -p 8000:8000 \
  -e HF_TOKEN=your_token \
  "${VLLM_IMAGE:-vllm/vllm-openai@sha256:7a0f0fdd2771464b6976625c2b2d5dd46f566aa00fbc53eceab86ef50883da90}" \
  --model mistralai/Mistral-7B-Instruct-v0.3 \
  --dtype float16 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.92 \
  --enable-prefix-caching
```

## Performance Tuning

### Memory Optimization

```bash
# Reduce memory usage
--gpu-memory-utilization 0.85  # Use 85% of GPU memory
--max-model-len 4096           # Reduce context length
--dtype float16                # Use half precision
```

### Throughput Optimization

```bash
# Increase throughput
--max-num-seqs 256             # Increase batch size
--max-num-batched-tokens 8192  # Increase token batch size
--enable-prefix-caching        # Enable KV cache
```

### Quantization

```bash
# Use quantized models
--quantization awq             # AWQ quantization
--quantization gptq            # GPTQ quantization
```

## API Usage

### OpenAI-Compatible Endpoints

```bash
# List models
curl http://localhost:8000/v1/models

# Chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistralai/Mistral-7B-Instruct-v0.3",
    "messages": [
      {"role": "user", "content": "Hello, world!"}
    ],
    "max_tokens": 100
  }'
```

### Streaming

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistralai/Mistral-7B-Instruct-v0.3",
    "messages": [
      {"role": "user", "content": "Tell me a story"}
    ],
    "stream": true
  }'
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Metrics

```bash
curl http://localhost:8000/metrics
```

### GPU Monitoring

```bash
# Monitor GPU usage
nvidia-smi -l 1

# Monitor with watch
watch -n 1 nvidia-smi
```

## Troubleshooting

### Common Issues

#### 1. Out of Memory (OOM)
```bash
# Reduce memory usage
--gpu-memory-utilization 0.8
--max-model-len 2048
--dtype float16
```

#### 2. Model Loading Failures
```bash
# Check Hugging Face token
echo $HF_TOKEN

# Verify model exists
curl -H "Authorization: Bearer $HF_TOKEN" \
  https://huggingface.co/api/models/mistralai/Mistral-7B-Instruct-v0.3
```

#### 3. Slow Inference
```bash
# Enable optimizations
--enable-prefix-caching
--max-num-seqs 128
--dtype float16
```

#### 4. Connection Issues
```bash
# Check if service is running
docker ps | grep vllm

# Check logs
docker logs <container-name>

# Test connectivity
curl http://localhost:8000/health
```

### Performance Benchmarks

#### RTX 4070 Ti Performance

| Model | Tokens/sec | Memory Usage | Latency (ms) |
|-------|------------|--------------|--------------|
| Mistral-7B-Instruct | ~45 | 8.2GB | 22 |
| Llama-2-7B-Chat | ~42 | 8.1GB | 24 |
| CodeLlama-7B-Instruct | ~40 | 8.3GB | 25 |

## Security

### Network Security
- vLLM API is only accessible from the control plane
- Use mTLS for secure communication
- Implement IP allowlists

### Model Security
- Use trusted model sources (Hugging Face)
- Verify model checksums
- Regular security updates

## Scaling

### Multi-GPU Setup
```bash
# Use multiple GPUs
--tensor-parallel-size 2
--gpu-memory-utilization 0.9
```

### Horizontal Scaling
- Deploy multiple vLLM instances
- Use load balancer for distribution
- Implement health checks and failover

## Backup and Recovery

### Model Caching
```bash
# Cache models locally
--download-dir /.cache/models/vllm
--cache-dir /cache
```

### Configuration Backup
```bash
# From repository root — backup configuration
cp .env .env.backup
cp docker/compose-profiles/docker-compose.worker.yml docker/compose-profiles/docker-compose.worker.yml.backup
```

## Updates

### Updating vLLM
```bash
# Pull the pinned/default image (or override VLLM_IMAGE first)
docker pull "${VLLM_IMAGE:-vllm/vllm-openai@sha256:7a0f0fdd2771464b6976625c2b2d5dd46f566aa00fbc53eceab86ef50883da90}"

# Restart with new image
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml up -d --force-recreate
```

### Model Updates
```bash
# Clear model cache (vLLM container cache is a bind mount under .docker-data/worker/vllm_cache by default)
rm -rf "${COMPOSE_DATA_ROOT:-.docker-data}/worker/vllm_cache"/*

# Restart with new model (from repository root)
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml up -d
```
