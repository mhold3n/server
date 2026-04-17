#!/bin/bash
set -euo pipefail

echo "Setting up Agent Orchestrator development environment..."

# Install pre-commit
echo "Installing pre-commit..."
pip install pre-commit
pre-commit install

# Install development dependencies
echo "Installing development dependencies..."

# MCP servers
cd /workspace/mcp-servers/mcp/servers/filesystem-mcp
pip install -e ".[dev]"

cd /workspace/mcp-servers/mcp/servers/secrets-mcp
pip install -e ".[dev]"

cd /workspace/mcp-servers/mcp/servers/vector-db-mcp
pip install -e ".[dev]"

# GitHub MCP server (Node.js)
cd /workspace/mcp-servers/mcp/servers/github-mcp
if [ -f package.json ]; then
    npm install
    npm run build
fi

# Make scripts executable
echo "Making scripts executable..."
chmod +x /workspace/deploy/ci/scripts/*.sh
chmod +x /workspace/dev/scripts/*.sh

# Create .env file if it doesn't exist
if [ ! -f /workspace/.env ]; then
    echo "Creating .env file from example..."
    cp /workspace/.env.example /workspace/.env
fi

echo "Development environment setup completed!"
echo ""
echo "AI control-plane (api-service, router, WrkHrs, OpenClaw): clone https://github.com/XLOTYL/xlotyl"
echo "beside this repo and run uv sync / npm ci there. Compose pulls pinned OCI images (XLOTYL_IMAGE_PREFIX + XLOTYL_VERSION in config/xlotyl-images.env)."
echo ""
echo "Next steps:"
echo "1. Configure your .env file with your settings"
echo "2. Run 'make up' to start the local development stack"
echo "3. Run 'make test-chat' to verify the API endpoint"
echo ""
echo "Available services (after make up):"
echo "- API: http://localhost:8080"
echo "- Router: http://localhost:8000"
echo "- Grafana: http://localhost:3000"
echo "- Prometheus: http://localhost:9090"
