SHELL := /bin/bash
ROOT := $(CURDIR)
# Sibling clone of https://github.com/XLOTYL/xlotyl for Makefile targets that run uv/npm in the AI repo.
XLOTYL_ROOT ?= $(ROOT)/../xlotyl
# Resolve relative bind mounts and ${COMPOSE_DATA_ROOT:-.docker-data}/... from repo root (Mac/Linux/Windows).
DOCKER_COMPOSE := docker compose --project-directory $(ROOT) --env-file $(ROOT)/config/xlotyl-images.env
ENV_BOOTSTRAP := source $(ROOT)/scripts/workspace_env.sh
COMPOSE_DIR := docker/compose-profiles
CORE_COMPOSE := -f docker-compose.yml
PLATFORM_COMPOSE := $(CORE_COMPOSE) -f $(COMPOSE_DIR)/docker-compose.platform.yml
AI_COMPOSE := $(PLATFORM_COMPOSE) -f $(COMPOSE_DIR)/docker-compose.ai.yml
FULL_DEV_COMPOSE := $(AI_COMPOSE) -f $(COMPOSE_DIR)/docker-compose.local-ai.yml
SERVER_COMPOSE := $(AI_COMPOSE) -f $(COMPOSE_DIR)/docker-compose.server.yml
WORKER_COMPOSE := -f $(COMPOSE_DIR)/docker-compose.worker.yml
# Local dev + GPU worker: full dev stack + vLLM runner (Qwen).
FULL_DEV_GPU_COMPOSE := $(FULL_DEV_COMPOSE) $(WORKER_COMPOSE)

ADDONS_COMPOSE := $(CORE_COMPOSE) -f $(COMPOSE_DIR)/docker-compose.addons.yml
ADDONS_PROFILES := security,search,ai,media,data,games,apps,network

# Prefer native ARM images on Apple Silicon (and Linux aarch64) so Compose does not run
# stale linux/amd64 layers under QEMU — that shows as "platform does not match host" warnings,
# very slow healthchecks, and stacks stuck below "healthy" (e.g. 23/25).
# To force x86_64 emulation: `make up DOCKER_DEFAULT_PLATFORM=linux/amd64`
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)
ifeq ($(origin DOCKER_DEFAULT_PLATFORM),undefined)
ifneq ($(filter Darwin_arm64 Linux_aarch64,$(UNAME_S)_$(UNAME_M)),)
export DOCKER_DEFAULT_PLATFORM := linux/arm64
endif
endif

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

# Local dev: full AI stack, mock-safe by default.
# --remove-orphans matches fullstack-e2e / dev/scripts/e2e_stack_up.sh (stale service containers).
up:
	$(DOCKER_COMPOSE) $(FULL_DEV_COMPOSE) up -d --remove-orphans

# Full dev + GPU worker (requires NVIDIA runtime on host).
up-gpu:
	OPENAI_BASE_URL=http://llm-runner-gen:8000/v1 \
	OPENAI_API_KEY=local-openai \
	LLM_BACKEND=vllm \
	LLM_RUNNER_URL=http://llm-runner-gen:8000 \
	VLLM_MODEL=$${VLLM_MODEL:-Qwen/Qwen2.5-7B-Instruct} \
	$(DOCKER_COMPOSE) $(FULL_DEV_GPU_COMPOSE) up -d --remove-orphans

# Rebuild all images in the full dev compose chain for the active DOCKER_DEFAULT_PLATFORM.
# Use once after platform mismatch warnings or pulled AMD64-only cache on an ARM host.
compose-rebuild:
	$(DOCKER_COMPOSE) $(FULL_DEV_COMPOSE) build

# Same compose as `up`, then wait for api /health and print OpenClaw host instructions.
e2e-up:
	@bash "$(ROOT)/dev/scripts/e2e_stack_up.sh"

# CLI-only backend orchestration smoke (no OpenClaw UI).
smoke-orchestration:
	@bash "$(ROOT)/dev/scripts/smoke_orchestration_cli.sh"

# Bundle logs + snapshots for orchestration debugging
bundle-orchestration-logs:
	@bash "$(ROOT)/dev/scripts/bundle_orchestration_logs.sh"

# Docker + layered health + API smoke + optional pytest + OpenClaw host install + optional managed gateway + hooks.
fullstack-e2e:
	@bash "$(ROOT)/dev/scripts/fullstack_e2e_bootstrap.sh"

# Stop managed OpenClaw gateway (and optionally compose down — see script header).
fullstack-e2e-down:
	@bash "$(ROOT)/dev/scripts/fullstack_e2e_teardown.sh"

down:
	$(DOCKER_COMPOSE) $(FULL_DEV_COMPOSE) down --remove-orphans

logs:
	$(DOCKER_COMPOSE) $(FULL_DEV_COMPOSE) logs -f

docker-validate:
	@bash -lc '$(ENV_BOOTSTRAP) && python scripts/validate_docker_topology.py'

# Compile orchestration wiki (``xlotyl/knowledge/wiki/orchestration/``) into
# ``xlotyl/knowledge/response-control/*.json``. Prefer ``uv run`` when available so
# Pydantic/contracts resolve; otherwise requires a venv with api-service installed.
wiki-compile:
	@$(MAKE) -C "$(XLOTYL_ROOT)" wiki-compile

wiki-check:
	@$(MAKE) -C "$(XLOTYL_ROOT)" wiki-check

wiki-proposals-check:
	@$(MAKE) -C "$(XLOTYL_ROOT)" wiki-proposals-check

wiki-promote:
	@$(MAKE) -C "$(XLOTYL_ROOT)" wiki-promote

core-up:
	$(DOCKER_COMPOSE) $(CORE_COMPOSE) up -d

core-down:
	$(DOCKER_COMPOSE) $(CORE_COMPOSE) down

core-logs:
	$(DOCKER_COMPOSE) $(CORE_COMPOSE) logs -f

test-chat:
	curl -s http://localhost:8080/v1/chat/completions \
		-H 'Content-Type: application/json' \
		-d '{"model":"mistralai/Mistral-7B-Instruct-v0.3","messages":[{"role":"user","content":"Hello"}]}' | jq .

# Server deployment
up-server:
	$(DOCKER_COMPOSE) $(SERVER_COMPOSE) up -d --build

logs-server:
	$(DOCKER_COMPOSE) $(SERVER_COMPOSE) logs -f

redeploy-caddy:
	./dev/scripts/redeploy_caddy.sh

# Addons
addons-up:
	COMPOSE_PROFILES=$(ADDONS_PROFILES) $(DOCKER_COMPOSE) $(ADDONS_COMPOSE) up -d

addons-logs:
	COMPOSE_PROFILES=$(ADDONS_PROFILES) $(DOCKER_COMPOSE) $(ADDONS_COMPOSE) logs -f

up-addons: addons-up

logs-addons: addons-logs

up-all:
	COMPOSE_PROFILES=$(ADDONS_PROFILES) $(DOCKER_COMPOSE) $(SERVER_COMPOSE) -f $(COMPOSE_DIR)/docker-compose.addons.yml up -d --build

# Worker deployment
up-worker:
	$(DOCKER_COMPOSE) $(WORKER_COMPOSE) up -d

logs-worker:
	$(DOCKER_COMPOSE) $(WORKER_COMPOSE) logs -f

# Platform services (MLflow, observability)
platform-up:
	$(DOCKER_COMPOSE) $(PLATFORM_COMPOSE) up -d

platform-down:
	$(DOCKER_COMPOSE) $(PLATFORM_COMPOSE) down

logs-platform:
	$(DOCKER_COMPOSE) $(PLATFORM_COMPOSE) logs -f

# AI stack (WrkHrs services)
ai-up:
	$(DOCKER_COMPOSE) $(AI_COMPOSE) up -d

ai-down:
	$(DOCKER_COMPOSE) $(AI_COMPOSE) down

logs-ai:
	$(DOCKER_COMPOSE) $(AI_COMPOSE) logs -f

# Full server deployment (platform + AI + server)
server-up:
	$(DOCKER_COMPOSE) $(SERVER_COMPOSE) up -d

server-down:
	$(DOCKER_COMPOSE) $(SERVER_COMPOSE) down

logs-server-full:
	$(DOCKER_COMPOSE) $(SERVER_COMPOSE) logs -f

# Worker (GPU) deployment
worker-up:
	$(DOCKER_COMPOSE) $(WORKER_COMPOSE) up -d

worker-down:
	$(DOCKER_COMPOSE) $(WORKER_COMPOSE) down

# Health checks
health:
	@./scripts/health_check.sh

# Smoke test
smoke-test:
	@./scripts/smoke_test.sh

# model-runtime /health + POST /infer/multimodal (host URL from MODEL_RUNTIME_PORT)
smoke-model-runtime-hf:
	@bash dev/scripts/smoke_model_runtime_hf.sh

# API strict_engineering query (opt-in: RUN_STRICT_ENGINEERING_SMOKE=1; needs api + agent-platform stack)
smoke-strict-engineering:
	@bash dev/scripts/smoke_strict_engineering_multimodal.sh

# Probative local engineering harness (schemas + engineering-core + model-runtime + npm workspaces).
prove-engineering-harness:
	@./scripts/prove_engineering_harness.sh

# Seed corpora
seed-corpora:
	@bash -lc '$(ENV_BOOTSTRAP) && uv run python scripts/ingest/ingest_code.py'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run python scripts/ingest/ingest_docs.py'

# Run evaluation
eval:
	@bash -lc 'cd "$(XLOTYL_ROOT)" && uv sync --python 3.11 && cd services/api-service && PYTEST_ADDOPTS="-o cache_dir=$(ROOT)/.cache/pytest/services-api $$PYTEST_ADDOPTS" uv run --package agent-orchestrator-api pytest tests/eval/ -v --tb=short'

# MLflow UI
mlflow-ui:
	@echo "MLflow UI: http://localhost:5000"
	@echo "Grafana: http://localhost:3000"

# Testing
test-api:
	@$(MAKE) -C "$(XLOTYL_ROOT)" test-api

test-router:
	@$(MAKE) -C "$(XLOTYL_ROOT)" test-router

test-worker:
	@$(MAKE) -C "$(XLOTYL_ROOT)" test-worker

test-combined: test-api test-router test-worker

test: test-combined

lint:
	@$(MAKE) -C "$(XLOTYL_ROOT)" lint
	@bash -lc '$(ENV_BOOTSTRAP) && uv run ruff check mcp-servers/mcp/servers/ --force-exclude'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run black --check mcp-servers/mcp/servers/'

type:
	@$(MAKE) -C "$(XLOTYL_ROOT)" type
	@bash -lc '$(ENV_BOOTSTRAP) && cd mcp-servers/mcp/servers/filesystem-mcp && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/mcp-filesystem uv run --package filesystem-mcp-server mypy --strict src'
	@bash -lc '$(ENV_BOOTSTRAP) && cd mcp-servers/mcp/servers/secrets-mcp && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/mcp-secrets uv run --package secrets-mcp-server mypy --strict src'
	@bash -lc '$(ENV_BOOTSTRAP) && cd mcp-servers/mcp/servers/vector-db-mcp && MYPY_CACHE_DIR=$(ROOT)/.cache/mypy/mcp-vector-db uv run --package vector-db-mcp-server mypy --strict src'

fix:
	@bash -lc 'cd "$(XLOTYL_ROOT)" && uv sync --python 3.11 >/dev/null && uv run ruff check --fix services/api-service services/router-service services/worker-service services/model-runtime services/engineering-core services/mcp-registry-service services/response-control-framework services/domain-engineering services/domain-research services/domain-content services/ai-shared-service services/structure-service services/media-service --force-exclude && uv run black services/api-service services/router-service services/worker-service services/model-runtime services/engineering-core services/mcp-registry-service services/response-control-framework services/domain-engineering services/domain-research services/domain-content services/ai-shared-service services/structure-service services/media-service'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run ruff check --fix mcp-servers/mcp/servers/ --force-exclude'
	@bash -lc '$(ENV_BOOTSTRAP) && uv run black mcp-servers/mcp/servers/'

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
	$(DOCKER_COMPOSE) $(FULL_DEV_COMPOSE) down -v
	docker system prune -f

clean-all: clean
	docker system prune -a -f
