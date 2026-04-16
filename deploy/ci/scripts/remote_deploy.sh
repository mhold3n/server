#!/bin/bash
set -euo pipefail

# Remote deployment script for agent-orchestrator
# Usage: ./remote_deploy.sh [server|worker]

TARGET=${1:-server}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "🚀 Starting deployment to $TARGET..."

case $TARGET in
    server)
        echo "📦 Deploying server stack..."
        cd "$PROJECT_ROOT"
        
        # Copy files to server
        echo "📋 Copying files to server..."
        rsync -avz --delete \
            --exclude='.git' \
            --exclude='node_modules' \
            --exclude='__pycache__' \
            --exclude='.pytest_cache' \
            --exclude='*.pyc' \
            --exclude='.env' \
            --exclude='*.log' \
            ./ "$SERVER_USER@$SERVER_HOST:~/agent-orchestrator/"
        # AI stack: copy dereferenced tree (works with ../xlotyl symlink locally).
        if [[ -d "$PROJECT_ROOT/xlotyl" ]]; then
            rsync -avzL --delete "$PROJECT_ROOT/xlotyl/" "$SERVER_USER@$SERVER_HOST:~/agent-orchestrator/xlotyl/"
        fi
        
        # Deploy on server
        echo "🔧 Deploying on server..."
        ssh "$SERVER_USER@$SERVER_HOST" << 'EOF'
            cd ~/agent-orchestrator
            cp .env.example .env || true
            
            # Pull latest images
            docker compose --project-directory "$HOME/agent-orchestrator" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml -f docker/compose-profiles/docker-compose.ai.yml -f docker/compose-profiles/docker-compose.server.yml pull
            
            # Deploy with health checks
            docker compose --project-directory "$HOME/agent-orchestrator" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml -f docker/compose-profiles/docker-compose.ai.yml -f docker/compose-profiles/docker-compose.server.yml up -d --build
            
            # Wait for services to be healthy
            ./deploy/ci/scripts/wait_for_healthy.sh api 8080 60
            ./deploy/ci/scripts/wait_for_healthy.sh router 8000 60
            ./deploy/ci/scripts/wait_for_healthy.sh prometheus 9090 60
            ./deploy/ci/scripts/wait_for_healthy.sh grafana 3000 60
            
            echo "✅ Server deployment completed successfully!"
EOF
        ;;
    
    worker)
        echo "🖥️ Deploying worker stack..."
        cd "$PROJECT_ROOT"
        
        # Copy worker files
        echo "📋 Copying worker files..."
        rsync -avz \
            docker/compose-profiles/docker-compose.worker.yml \
            docker/config/reverse-proxy/Caddyfile.worker \
            worker/vllm/ \
            "$WORKER_USER@$WORKER_HOST:~/agent-orchestrator/"
        
        # Deploy on worker
        echo "🔧 Deploying on worker..."
        ssh "$WORKER_USER@$WORKER_HOST" << 'EOF'
            cd ~/agent-orchestrator
            export HF_TOKEN="$HF_TOKEN"
            
            # Stop existing worker
            docker compose --project-directory "$HOME/agent-orchestrator" -f docker/compose-profiles/docker-compose.worker.yml down || true
            
            # Pull latest images
            docker compose --project-directory "$HOME/agent-orchestrator" -f docker/compose-profiles/docker-compose.worker.yml pull
            
            # Deploy worker
            docker compose --project-directory "$HOME/agent-orchestrator" -f docker/compose-profiles/docker-compose.worker.yml up -d
            
            # Wait for worker to be healthy
            sleep 30
            curl -f http://localhost:8000/health || exit 1
            
            echo "✅ Worker deployment completed successfully!"
EOF
        ;;
    
    *)
        echo "❌ Invalid target: $TARGET"
        echo "Usage: $0 [server|worker]"
        exit 1
        ;;
esac

echo "🎉 Deployment to $TARGET completed successfully!"
