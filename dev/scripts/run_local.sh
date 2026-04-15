#!/bin/bash
set -euo pipefail

# Run local development stack
# Usage: ./run_local.sh [up|down|logs|restart]

ACTION=${1:-up}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Match Makefile `make up` compose chain; paths resolve from repo root.
LOCAL_COMPOSE=(
  -f docker-compose.yml
  -f docker/compose-profiles/docker-compose.platform.yml
  -f docker/compose-profiles/docker-compose.ai.yml
  -f docker/compose-profiles/docker-compose.local-ai.yml
)

case $ACTION in
    up)
        echo "🚀 Starting local development stack..."
        docker compose --project-directory "$PROJECT_ROOT" "${LOCAL_COMPOSE[@]}" up -d
        echo "⏳ Waiting for services to be ready..."
        sleep 10
        echo "✅ Local stack is running!"
        echo ""
        echo "🔗 Available services:"
        echo "- API: http://localhost:8080"
        echo "- Router: http://localhost:8000"
        echo "- Grafana: http://localhost:3000"
        echo "- Prometheus: http://localhost:9090"
        echo ""
        echo "📋 To view logs: $0 logs"
        echo "🛑 To stop: $0 down"
        ;;
    
    down)
        echo "🛑 Stopping local development stack..."
        docker compose --project-directory "$PROJECT_ROOT" "${LOCAL_COMPOSE[@]}" down
        echo "✅ Local stack stopped!"
        ;;
    
    logs)
        echo "📋 Showing logs for all services..."
        docker compose --project-directory "$PROJECT_ROOT" "${LOCAL_COMPOSE[@]}" logs -f
        ;;
    
    restart)
        echo "🔄 Restarting local development stack..."
        docker compose --project-directory "$PROJECT_ROOT" "${LOCAL_COMPOSE[@]}" down
        docker compose --project-directory "$PROJECT_ROOT" "${LOCAL_COMPOSE[@]}" up -d
        echo "✅ Local stack restarted!"
        ;;
    
    status)
        echo "📊 Service status:"
        docker compose --project-directory "$PROJECT_ROOT" "${LOCAL_COMPOSE[@]}" ps
        ;;
    
    *)
        echo "❌ Invalid action: $ACTION"
        echo "Usage: $0 [up|down|logs|restart|status]"
        exit 1
        ;;
esac
