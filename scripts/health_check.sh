#!/bin/bash

# Health check script for Birtha + WrkHrs AI stack
# Checks all services and provides status summary

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service URLs
API_URL="http://localhost:8080"
ROUTER_URL="http://localhost:8000"
GATEWAY_URL="http://localhost:8080"
MLFLOW_URL="http://localhost:5000"
GRAFANA_URL="http://localhost:3000"
PROMETHEUS_URL="http://localhost:9090"
QDRANT_URL="http://localhost:6333"
MCP_REGISTRY_URL="http://localhost:8001"
TEMPO_URL="http://localhost:3200"
LOKI_URL="http://localhost:3100"

# Function to check service health
check_service() {
    local name=$1
    local url=$2
    local endpoint=${3:-"/health"}
    
    echo -n "Checking $name... "
    
    if curl -s -f "$url$endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Healthy${NC}"
        return 0
    else
        echo -e "${RED}✗ Unhealthy${NC}"
        return 1
    fi
}

# Function to check Docker service
check_docker_service() {
    local name=$1
    
    echo -n "Checking Docker service $name... "
    
    if docker ps --format "table {{.Names}}" | grep -q "^${name}$"; then
        echo -e "${GREEN}✓ Running${NC}"
        return 0
    else
        echo -e "${RED}✗ Not running${NC}"
        return 1
    fi
}

echo -e "${BLUE}=== Birtha + WrkHrs AI Stack Health Check ===${NC}"
echo

# Core Birtha services
echo -e "${YELLOW}Core Birtha Services:${NC}"
check_service "API" "$API_URL"
check_service "Router" "$ROUTER_URL"
check_docker_service "queue"
check_docker_service "prometheus"
check_docker_service "grafana"
check_docker_service "qdrant"

echo

# WrkHrs AI services
echo -e "${YELLOW}WrkHrs AI Services:${NC}"
check_docker_service "structure-gateway"
check_docker_service "wrkhrs-gateway"
check_docker_service "wrkhrs-agent-platform"
check_docker_service "wrkhrs-rag"
check_docker_service "wrkhrs-asr"
check_docker_service "wrkhrs-tool-registry"
check_docker_service "wrkhrs-mcp"

echo

# Platform services
echo -e "${YELLOW}Platform Services:${NC}"
check_service "MLflow" "$MLFLOW_URL"
check_service "MCP Registry" "$MCP_REGISTRY_URL"
check_service "Tempo" "$TEMPO_URL"
check_service "Loki" "$LOKI_URL"
check_docker_service "postgres"
check_docker_service "minio"
check_docker_service "loki"
check_docker_service "tempo"
check_docker_service "jaeger"

echo

# MCP servers
echo -e "${YELLOW}MCP Servers:${NC}"
check_docker_service "mcp-github"
check_docker_service "mcp-filesystem"
check_docker_service "mcp-secrets"
check_docker_service "mcp-vector-db"

echo

# Worker services (if running)
echo -e "${YELLOW}Worker Services (GPU):${NC}"
if docker ps --format "table {{.Names}}" | grep -q "llm-runner"; then
    check_docker_service "llm-runner"
else
    echo -e "${YELLOW}Worker services not running (expected if not on GPU workstation)${NC}"
fi

echo

# Summary
echo -e "${BLUE}=== Health Check Summary ===${NC}"

# Count healthy services
total_services=0
healthy_services=0

# Core services
for service in "API" "Router" "queue" "prometheus" "grafana" "qdrant"; do
    total_services=$((total_services + 1))
    if check_docker_service "$service" > /dev/null 2>&1; then
        healthy_services=$((healthy_services + 1))
    fi
done

# AI services
for service in "structure-gateway" "wrkhrs-gateway" "wrkhrs-agent-platform" "wrkhrs-rag" "wrkhrs-asr" "wrkhrs-tool-registry" "wrkhrs-mcp"; do
    total_services=$((total_services + 1))
    if check_docker_service "$service" > /dev/null 2>&1; then
        healthy_services=$((healthy_services + 1))
    fi
done

# Platform services
for service in "postgres" "minio" "loki" "tempo" "jaeger"; do
    total_services=$((total_services + 1))
    if check_docker_service "$service" > /dev/null 2>&1; then
        healthy_services=$((healthy_services + 1))
    fi
done

# MCP servers
for service in "mcp-github" "mcp-filesystem" "mcp-secrets" "mcp-vector-db"; do
    total_services=$((total_services + 1))
    if check_docker_service "$service" > /dev/null 2>&1; then
        healthy_services=$((healthy_services + 1))
    fi
done

echo "Healthy services: $healthy_services/$total_services"

if [ $healthy_services -eq $total_services ]; then
    echo -e "${GREEN}All services are healthy! 🎉${NC}"
    exit 0
elif [ $healthy_services -gt $((total_services / 2)) ]; then
    echo -e "${YELLOW}Most services are healthy, but some issues detected.${NC}"
    exit 1
else
    echo -e "${RED}Multiple services are unhealthy. Check logs for details.${NC}"
    exit 2
fi











