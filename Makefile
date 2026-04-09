SHELL := /bin/bash
ROOT := $(CURDIR)
ENV_BOOTSTRAP := source $(ROOT)/scripts/workspace_env.sh

sync:
	@bash -lc '$(ENV_BOOTSTRAP) && uv sync --python 3.11'

node-install:
	@bash -lc '$(ENV_BOOTSTRAP) && npm install'

tool-env-marker:
	@bash -lc '$(ENV_BOOTSTRAP) && scripts/bootstrap_tool_env.sh marker-pdf'

tool-env-whisper:
	@bash -lc '$(ENV_BOOTSTRAP) && scripts/bootstrap_tool_env.sh whisper-asr'

tool-env-qwen:
	@bash -lc '$(ENV_BOOTSTRAP) && scripts/bootstrap_tool_env.sh qwen-runtime'

tool-env-mbmh:
	@bash -lc '$(ENV_BOOTSTRAP) && scripts/bootstrap_tool_env.sh mbmh'

tool-env-larrak:
	@bash -lc '$(ENV_BOOTSTRAP) && scripts/bootstrap_tool_env.sh larrak-audio'

# Local dev
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test-chat:
	curl -s http://localhost:8080/v1/chat/completions \
		-H 'Content-Type: application/json' \
		-d '{"model":"mistralai/Mistral-7B-Instruct-v0.3","messages":[{"role":"user","content":"Hello"}]}' | jq .

# Server deployment
up-server:
	docker compose -f docker-compose.yml -f compose/docker-compose.server.yml up -d --build

logs-server:
	docker compose -f docker-compose.yml -f compose/docker-compose.server.yml logs -f

redeploy-caddy:
	./dev/scripts/redeploy_caddy.sh

# Addons
up-addons:
	COMPOSE_PROFILES=security,search,ai,media,data,games,apps,network docker compose -f compose/docker-compose.addons.yml up -d

logs-addons:
	COMPOSE_PROFILES=security,search,ai,media,data,games,apps,network docker compose -f compose/docker-compose.addons.yml logs -f

up-all:
	COMPOSE_PROFILES=security,search,ai,media,data,games,apps,network docker compose -f docker-compose.yml -f compose/docker-compose.server.yml -f compose/docker-compose.addons.yml up -d --build

# Worker deployment
up-worker:
	docker compose -f compose/docker-compose.worker.yml up -d

logs-worker:
	docker compose -f compose/docker-compose.worker.yml logs -f

# Platform services (MLflow, observability)
platform-up:
	docker compose -f docker-compose.yml -f compose/docker-compose.platform.yml up -d

platform-down:
	docker compose -f docker-compose.yml -f compose/docker-compose.platform.yml down

logs-platform:
	docker compose -f docker-compose.yml -f compose/docker-compose.platform.yml logs -f

# AI stack (WrkHrs services)
ai-up:
	docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml up -d

ai-down:
	docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml down

logs-ai:
	docker compose -f docker-compose.yml -f compose/docker-compose.ai.yml logs -f

# Full server deployment (platform + AI + server)
server-up:
	docker compose -f docker-compose.yml -f compose/docker-compose.platform.yml -f compose/docker-compose.ai.yml -f compose/docker-compose.server.yml up -d

server-down:
	docker compose -f docker-compose.yml -f compose/docker-compose.platform.yml -f compose/docker-compose.ai.yml -f compose/docker-compose.server.yml down

logs-server-full:
	docker compose -f docker-compose.yml -f compose/docker-compose.platform.yml -f compose/docker-compose.ai.yml -f compose/docker-compose.server.yml logs -f

# Worker (GPU) deployment
worker-up:
	docker compose -f compose/docker-compose.worker.yml up -d

worker-down:
	docker compose -f compose/docker-compose.worker.yml down

logs-worker:
	docker compose -f compose/docker-compose.worker.yml logs -f

# Health checks
health:
	@./scripts/health_check.sh

# Smoke test
smoke-test:
	@./scripts/smoke_test.sh

# Seed corpora
seed-corpora:
	@bash -lc '$(ENV_BOOTSTRAP) && uv run python scripts/ingest/ingest_code.py'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run python scripts/ingest/ingest_docs.py'

# Run evaluation
eval:
	@bash -lc '$(ENV_BOOTSTRAP) && cd services/api && PYTEST_ADDOPTS="-o cache_dir=$(ROOT)/.cache/pytest/services-api $$PYTEST_ADDOPTS" uv run --package agent-orchestrator-api pytest tests/eval/ -v --tb=short'

# MLflow UI
mlflow-ui:
	@echo "MLflow UI: http://localhost:5000"
	@echo "Grafana: http://localhost:3000"

# Testing
test-api:
	@bash -lc '$(ENV_BOOTSTRAP) && cd services/api && PYTEST_ADDOPTS="-o cache_dir=$(ROOT)/.cache/pytest/services-api $$PYTEST_ADDOPTS" uv run --package agent-orchestrator-api pytest -q tests --maxfail=1 --cov=src --cov-report= --cov-append=no'

test-router:
	@bash -lc '$(ENV_BOOTSTRAP) && cd services/router && PYTEST_ADDOPTS="-o cache_dir=$(ROOT)/.cache/pytest/services-router $$PYTEST_ADDOPTS" uv run --package agent-orchestrator-router pytest -q tests --maxfail=1 --cov=src --cov-report= --cov-append'

test-combined: test-api test-router
	@bash -lc '$(ENV_BOOTSTRAP) && uv run python -m coverage combine || true'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run python -m coverage report --fail-under=80'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run python -m coverage xml'

test: test-combined

lint:
	@bash -lc '$(ENV_BOOTSTRAP) && uv run ruff check services mcp/servers --force-exclude'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run black --check services mcp/servers'

type:
	@bash -lc '$(ENV_BOOTSTRAP) && cd services/api && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/services-api uv run --package agent-orchestrator-api mypy --strict src'
	@bash -lc '$(ENV_BOOTSTRAP) && cd services/router && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/services-router uv run --package agent-orchestrator-router mypy --strict src'
	@bash -lc '$(ENV_BOOTSTRAP) && cd services/worker_client && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/services-worker-client uv run --package agent-orchestrator-worker-client mypy --strict src'
	@bash -lc '$(ENV_BOOTSTRAP) && cd mcp/servers/filesystem-mcp && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/mcp-filesystem uv run --package filesystem-mcp-server mypy --strict src'
	@bash -lc '$(ENV_BOOTSTRAP) && cd mcp/servers/secrets-mcp && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/mcp-secrets uv run --package secrets-mcp-server mypy --strict src'
	@bash -lc '$(ENV_BOOTSTRAP) && cd mcp/servers/vector-db-mcp && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/mcp-vector-db uv run --package vector-db-mcp-server mypy --strict src'

fix:
	@bash -lc '$(ENV_BOOTSTRAP) && uv run ruff check --fix services mcp/servers --force-exclude'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run black services mcp/servers'

# CI simulation
ci: lint type test-combined

# Deployment helpers
deploy-server:
	./deploy/ci/scripts/remote_deploy.sh server

deploy-worker:
	./deploy/ci/scripts/remote_deploy.sh worker

# Workstation setup
setup-workstation:
	chmod +x dev/scripts/setup_workstation.sh
	./dev/scripts/setup_workstation.sh

detect-hardware:
	python3 dev/scripts/detect_hardware.py

configure-network:
	python3 dev/scripts/configure_network.py

# Development helpers
install-pre-commit:
	pre-commit install

dev-setup: install-pre-commit
	@echo "Setting up development environment..."
	@echo "1. Run 'make sync' to create the root uv workspace env"
	@echo "2. Run 'make node-install' for the root npm workspace"
	@echo "3. Run 'make detect-hardware' to detect hardware"
	@echo "4. Run 'make configure-network' to setup network"
	@echo "5. Copy machine-config/env.template to .env and configure"
	@echo "6. Run 'make up' to start local stack"
	@echo "7. Run 'make test-chat' to verify setup"

# Cleanup
clean:
	docker compose down -v
	docker system prune -f

clean-all: clean
	docker system prune -a -f
