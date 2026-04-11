#!/bin/bash
# =============================================================================
# Workstation Setup Script for Agent Orchestrator
# =============================================================================
# This script sets up the RTX 4070 Ti workstation for GPU inference

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Windows
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || -n "${WINDIR:-}" ]]; then
    log_warning "Detected Windows environment. Some commands may need adjustment."
    IS_WINDOWS=true
else
    IS_WINDOWS=false
fi

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker Desktop."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    # Check NVIDIA Docker runtime
    if ! docker info | grep -q nvidia; then
        log_warning "NVIDIA Docker runtime not detected. GPU acceleration may not work."
        log_info "Install nvidia-docker2 for GPU support:"
        log_info "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    fi
    
    # Check nvidia-smi
    if ! command -v nvidia-smi &> /dev/null; then
        log_warning "nvidia-smi not found. GPU detection may not work."
    else
        log_info "GPU Information:"
        nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    fi
    
    log_success "Prerequisites check completed"
}

# Detect hardware
detect_hardware() {
    log_info "Detecting hardware configuration..."
    
    # Run hardware detection script
    if [[ -f "dev/scripts/detect_hardware.py" ]]; then
        python3 dev/scripts/detect_hardware.py
    else
        log_warning "Hardware detection script not found. Creating basic configuration..."
        
        # Create basic workstation config
        cat > .env.workstation << EOF
# Workstation Configuration (RTX 4070 Ti)
WORKER_HOST=localhost
WORKER_INTERNAL_IP=192.168.1.101
GPU_MODEL=RTX_4070_TI
GPU_MEMORY_GB=12
MODEL_GPU_MEMORY_UTILIZATION=0.9
MODEL_MAX_MODEL_LEN=4096
DEBUG=true
LOG_LEVEL=DEBUG
EOF
    fi
    
    log_success "Hardware detection completed"
}

# Setup environment files
setup_environment() {
    log_info "Setting up environment configuration..."
    
    # Copy template if .env doesn't exist
    if [[ ! -f ".env" ]]; then
        if [[ -f "machine-config/env.template" ]]; then
            cp machine-config/env.template .env
            log_info "Created .env from template"
        else
            log_warning "No environment template found. Please create .env manually."
        fi
    fi
    
    # Merge workstation-specific config
    if [[ -f ".env.workstation" ]]; then
        log_info "Merging workstation-specific configuration..."
        cat .env.workstation >> .env
    fi
    
    log_success "Environment configuration completed"
}

# Test GPU availability
test_gpu() {
    log_info "Testing GPU availability..."
    
    # Test nvidia-smi
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
    fi
    
    # Test Docker GPU access
    if docker info | grep -q nvidia; then
        log_info "Testing Docker GPU access..."
        docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi || {
            log_warning "Docker GPU test failed. Check nvidia-docker2 installation."
        }
    fi
    
    log_success "GPU testing completed"
}

# Setup vLLM worker
setup_vllm_worker() {
    log_info "Setting up vLLM worker configuration..."
    
    # Create worker directory if it doesn't exist
    mkdir -p worker/vllm
    
    # Create vLLM docker-compose if it doesn't exist
    if [[ ! -f "worker/vllm/docker-compose.vllm.yml" ]]; then
        cat > worker/vllm/docker-compose.vllm.yml << 'EOF'
version: '3.8'

services:
  vllm:
    image: ${VLLM_IMAGE:-vllm/vllm-openai@sha256:7a0f0fdd2771464b6976625c2b2d5dd46f566aa00fbc53eceab86ef50883da90}
    container_name: vllm-worker
    ports:
      - "8000:8000"
    environment:
      - MODEL_NAME=${MODEL_NAME:-microsoft/DialoGPT-medium}
      - MODEL_REVISION=${MODEL_REVISION:-main}
      - MAX_MODEL_LEN=${MODEL_MAX_MODEL_LEN:-4096}
      - GPU_MEMORY_UTILIZATION=${MODEL_GPU_MEMORY_UTILIZATION:-0.9}
      - HF_TOKEN=${HF_TOKEN:-}
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
EOF
    fi
    
    log_success "vLLM worker configuration completed"
}

# Test local stack
test_local_stack() {
    log_info "Testing local development stack..."
    
    # Start basic services
    if [[ -f "docker-compose.yml" ]]; then
        log_info "Starting local development stack..."
        docker-compose up -d redis prometheus grafana
        
        # Wait for services to be ready
        sleep 10
        
        # Test Redis
        if docker-compose exec -T redis redis-cli ping | grep -q PONG; then
            log_success "Redis is running"
        else
            log_warning "Redis health check failed"
        fi
        
        # Test Prometheus
        if curl -s http://localhost:9090/-/healthy > /dev/null; then
            log_success "Prometheus is running"
        else
            log_warning "Prometheus health check failed"
        fi
        
        # Test Grafana
        if curl -s http://localhost:3000/api/health > /dev/null; then
            log_success "Grafana is running"
        else
            log_warning "Grafana health check failed"
        fi
    else
        log_warning "docker-compose.yml not found. Skipping local stack test."
    fi
}

# Main setup function
main() {
    log_info "🚀 Setting up Agent Orchestrator Workstation..."
    
    check_prerequisites
    detect_hardware
    setup_environment
    test_gpu
    setup_vllm_worker
    test_local_stack
    
    log_success "✅ Workstation setup completed!"
    
    echo ""
    log_info "📋 Next steps:"
    echo "  1. Review and update .env with your specific configuration"
    echo "  2. Update network settings (IP addresses, hostnames)"
    echo "  3. Configure server settings when Proxmox is online"
    echo "  4. Test GPU inference: make up-worker"
    echo "  5. Run local development: make up"
    echo ""
    log_info "🔧 Useful commands:"
    echo "  make up          - Start local development stack"
    echo "  make up-worker   - Start GPU worker (vLLM)"
    echo "  make test-chat   - Test chat completion"
    echo "  make logs        - View service logs"
    echo ""
}

# Run main function
main "$@"
