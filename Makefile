SHELL := /bin/bash

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
	docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build

logs-server:
	docker compose -f docker-compose.yml -f docker-compose.server.yml logs -f

redeploy-caddy:
	./dev/scripts/redeploy_caddy.sh

# Addons
up-addons:
	COMPOSE_PROFILES=security,search,ai,media,data,games,apps,network docker compose -f docker-compose.addons.yml up -d

logs-addons:
	COMPOSE_PROFILES=security,search,ai,media,data,games,apps,network docker compose -f docker-compose.addons.yml logs -f

up-all:
	COMPOSE_PROFILES=security,search,ai,media,data,games,apps,network docker compose -f docker-compose.yml -f docker-compose.server.yml -f docker-compose.addons.yml up -d --build

# Worker deployment
up-worker:
	docker compose -f docker-compose.worker.yml up -d

logs-worker:
	docker compose -f docker-compose.worker.yml logs -f

# Platform services (MLflow, observability)
platform-up:
	docker compose -f docker-compose.yml -f docker-compose.platform.yml up -d

platform-down:
	docker compose -f docker-compose.yml -f docker-compose.platform.yml down

logs-platform:
	docker compose -f docker-compose.yml -f docker-compose.platform.yml logs -f

# AI stack (WrkHrs services)
ai-up:
	docker compose -f docker-compose.yml -f docker-compose.ai.yml up -d

ai-down:
	docker compose -f docker-compose.yml -f docker-compose.ai.yml down

logs-ai:
	docker compose -f docker-compose.yml -f docker-compose.ai.yml logs -f

# Full server deployment (platform + AI + server)
server-up:
	docker compose -f docker-compose.yml -f docker-compose.platform.yml -f docker-compose.ai.yml -f docker-compose.server.yml up -d

server-down:
	docker compose -f docker-compose.yml -f docker-compose.platform.yml -f docker-compose.ai.yml -f docker-compose.server.yml down

logs-server-full:
	docker compose -f docker-compose.yml -f docker-compose.platform.yml -f docker-compose.ai.yml -f docker-compose.server.yml logs -f

# Worker (GPU) deployment
worker-up:
	docker compose -f docker-compose.worker.yml up -d

worker-down:
	docker compose -f docker-compose.worker.yml down

logs-worker:
	docker compose -f docker-compose.worker.yml logs -f

# Health checks
health:
	@./scripts/health_check.sh

# Smoke test
smoke-test:
	@./scripts/smoke_test.sh

# Seed corpora
seed-corpora:
	python scripts/ingest/ingest_code.py
	python scripts/ingest/ingest_docs.py

# Run evaluation
eval:
	pytest services/api/tests/eval/ -v --tb=short

# MLflow UI
mlflow-ui:
	@echo "MLflow UI: http://localhost:5000"
	@echo "Grafana: http://localhost:3000"

# Testing
test-api:
	set -e; \
	export PYTHONPATH=services/api; \
	pytest -q services/api/tests --maxfail=1 --cov=services/api/src --cov-report= --cov-append=no

test-router:
	set -e; \
	export PYTHONPATH=services/router; \
	pytest -q services/router/tests --maxfail=1 --cov=services/router/src --cov-report= --cov-append

test-combined: test-api test-router
	set -e; \
	python -m coverage combine || true; \
	python -m coverage report --fail-under=80; \
	python -m coverage xml

test: test-combined

lint:
	ruff check services mcp/servers --force-exclude && black --check services mcp/servers --extend-exclude '/services/wrkhrs/'

type:
	set -e; \
	(cd services/api && mypy --strict src); \
	(cd services/router && mypy --strict src); \
	(cd services/worker_client && mypy --strict src); \
	(cd mcp/servers/filesystem-mcp && mypy --strict src); \
	(cd mcp/servers/secrets-mcp && mypy --strict src); \
	(cd mcp/servers/vector-db-mcp && mypy --strict src)

fix:
	ruff check --fix services mcp/servers --force-exclude && black services mcp/servers --extend-exclude '/services/wrkhrs/'

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
	@echo "1. Run 'make detect-hardware' to detect hardware"
	@echo "2. Run 'make configure-network' to setup network"
	@echo "3. Copy machine-config/env.template to .env and configure"
	@echo "4. Run 'make up' to start local stack"
	@echo "5. Run 'make test-chat' to verify setup"

# Cleanup
clean:
	docker compose down -v
	docker system prune -f

clean-all: clean
	docker system prune -a -f
