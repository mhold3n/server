# Birtha infrastructure + Xlotyl AI deployment

**Goal:** Run the **Birtha / WrkHrs AI product** (see submodule **`xlotyl/`**) on hardened **infrastructure**: Proxmox VMs/LXCs, Docker Compose, reverse proxy (Caddy), queues (Redis), observability (MLflow, Prometheus, Grafana, Loki, Tempo), optional security (Fail2ban/CrowdSec), and DNS/homelab add-ons. A **workstation** with an RTX 4070 Ti hosts GPU inference workers, reachable from the server over LAN/mTLS.

## High-level Architecture

- **Server stack (Proxmox VM/LXC):** Compose-driven **platform** services (observability, registry, Redis, reverse proxy), **host MCP** servers, and **lifecycle for the `xlotyl` AI stack** (images/build contexts point at `./xlotyl/...`). AI ingress API, router, worker, gateway, and agent platform **code live in `xlotyl`**, not as first-class members of the server root Python/Node workspaces.
- **Workstation (RTX 4070 Ti):** vLLM/Ollama LLM runners in Docker with `nvidia-container-toolkit`, exposed only to the server via LAN/mTLS.
- **Dev flow:** Remote dev via VS Code Dev Containers → CI builds in **server** (including checks executed **inside `xlotyl/`**) → Deploy to server → Running containers use **xlotyl**-built images for AI control plane.

### Active vs archived code

- **This repo** — **Infrastructure and deployment**: compose profiles, CI, MCP host packages, observability base, networking/media infra, scripts that pin or update submodules, and glue that **starts** the AI product from `./xlotyl`.
- **Legacy archive** — The historical MBMH training/runtime tree and the retired `engineering_physics_v1` harness were moved out of this repo into the sibling legacy archive at `../server-local-archive/2026-04-08/server/`.

### Role of this repo and GitHub

This repository is the **primary web-based tracker** for **infrastructure layout**, **compose**, **CI**, and **submodule pins** so changes are reviewable and reproducible. It does **not** replace on-machine operational truth.

**GitHub** is **tertiary** relative to **local RAID** (primary server) and **backups on secondary machines**: use **git** for history, **diffs**, and collaboration; use **RAID and secondary copies** for durability and recovery. See [`docs/infrastructure-and-git.md`](docs/infrastructure-and-git.md).

### External GitHub repos

- **`claw-code-main/`** — Git submodule tracking our fork [`mhold3n/claw-code`](https://github.com/mhold3n/claw-code) on `main` (upstream: [`ultraworkers/claw-code`](https://github.com/ultraworkers/claw-code)).
- **`openclaw/`** — Git submodule tracking our fork [`mhold3n/openclaw`](https://github.com/mhold3n/openclaw) on `main` (upstream: [`openclaw/openclaw`](https://github.com/openclaw/openclaw)).
- **`void/`** — Git submodule tracking [`mhold3n/void`](https://github.com/mhold3n/void) on `main`.
- **`xlotyl/`** — Git submodule tracking [`mhold3n/xlotyl`](https://github.com/mhold3n/xlotyl) on `main` (**full AI product**: API, router, worker, gateway, agent-platform, domains, `model-runtime`, orchestration wiki, response-control). The super-project pins an exact submodule commit for CI and releases; compose **build contexts and bind mounts** read from `./xlotyl/...` without treating xlotyl as a nested Node/Python workspace at the server root.
- Refresh all with `npm run deps:external`. See [`docs/external-repos.md`](docs/external-repos.md) for the rationale and workflow, and [`docs/external-orchestration-interfaces.md`](docs/external-orchestration-interfaces.md) for how they relate to the active control plane.

## Project Management

This project uses GitHub Projects for task tracking and project management.

- **Project Board**: https://github.com/users/mhold3n/projects/3
- **Issue Templates**: Available in `.github/ISSUE_TEMPLATE/`
- **Automation**: Configured via `.github/workflows/project-automation.yml`

### Creating Issues

Use the appropriate issue template:
- **WrkHrs Features**: Use `feature-wrkhrs.md` template
- **MCP Servers**: Use `mcp-server.md` template  
- **Observability**: Use `observability.md` template

### Project Views

- **Backlog**: All open issues with `wrkhrs-convergence` label
- **In Progress**: Assigned issues currently being worked on
- **Done**: Completed issues
- **Blocked**: Issues that are blocked or waiting for dependencies

## Quickstart

### 0) Prerequisites
- Proxmox host ready; create a VM/LXC for `agent-server`.
- Docker + Compose on server and workstation.
- (Workstation) NVIDIA driver + `nvidia-container-toolkit`.
- `uv` for the server-root Python workspace (host MCP tooling) and for work inside `xlotyl/`.
- `npm` for optional root scripts (`deps:external`) and for **xlotyl** Node workspaces under `xlotyl/`.

### 1) Bootstrap the workspace

```bash
npm run deps:external
uv sync --python 3.11
# Root package.json is infra-only; install inside xlotyl for agent-platform Node builds:
(cd xlotyl && npm ci)
```

Focused tool envs are bootstrapped explicitly and live under `.cache/envs/`:

```bash
scripts/bootstrap_tool_env.sh marker-pdf
scripts/bootstrap_tool_env.sh whisper-asr
scripts/bootstrap_tool_env.sh qwen-runtime
```

Shared caches and reproducible local model state live under `.cache/`.

### 2) Configure environment
Copy `.env.example` to `.env` and fill values:
```bash
cp .env.example .env
```

### 3) Start server stack (control plane)

```bash
# Platform services (MLflow, observability)
make platform-up

# AI stack (WrkHrs services)
make ai-up

# Full server deployment (platform + AI + server)
make server-up

# addons (security/search/media/etc.; host/homelab-only)
make addons-up

# full AI dev stack (base + platform + AI + local overrides)
make up
```

### 4) Start GPU worker on workstation

```bash
# Start GPU worker
make worker-up

# Or start with Ollama instead of vLLM
docker compose --project-directory "$(pwd)" -f docker/compose-profiles/docker-compose.worker.yml --profile ollama up -d
```

### 5) Test

```bash
# Health check all services
make health

# Smoke test with trace propagation
make smoke-test

# Test WrkHrs gateway
curl -s http://localhost:8080/health

# Test LLM inference via worker
curl -s https://worker.local:8443/v1/models

# Test MLflow UI
open http://localhost:5000
```

### 6) Dev UX

* All devs SSH or VS Code Remote into the **server** (or work standalone in the **`xlotyl`** clone for product code).
* **API and Router** run from **`xlotyl`** service images; the server repo wires compose, ports, and env — it does not own that application source at the repo root.
* **WrkHrs / gateway** stacks run from **`xlotyl/services/ai-gateway-service`** build contexts.
* Internal services call the **worker** via OpenAI-compatible endpoints for LLM inference.
* **MCP catalog** (xlotyl-owned): `xlotyl/mcp-servers/mcp/config/mcp_servers.yaml` (with submodule initialized). **Implementations** under `mcp-servers/` here are **tracked** for build/CI on primary hardware — see [`mcp-servers/README.md`](mcp-servers/README.md).
* MLflow provides experiment tracking and model registry for all AI operations.

## WrkHrs AI Stack Integration (sources in `xlotyl/`)

### AI Services Architecture
- **WrkHrs Gateway**: Main API gateway for AI requests with domain classification and request conditioning
- **WrkHrs Orchestrator**: Task orchestration and workflow management using LangChain/LangGraph
- **WrkHrs RAG**: Retrieval-augmented generation with Qdrant vector database
- **WrkHrs ASR**: Automatic speech recognition with Whisper integration
- **WrkHrs Tool Registry**: Tool discovery and registration for MCP integration
- **WrkHrs MCP**: Micro-capability platform service for tool and resource management

### Policy Enforcement
- **Evidence Policy**: Requires citations and evidence in AI responses
- **Citation Policy**: Validates citation quality and format
- **Hedging Policy**: Detects and flags hedging language
- **Units Policy**: Normalizes and validates SI units
- **Policy Registry**: Dynamic policy discovery and validation
- **Policy Middleware**: Automatic policy enforcement in chat completions with MLflow logging

### Observability & Provenance
- **MLflow**: Experiment tracking, model registry, and artifact storage
- **OpenTelemetry**: Distributed tracing with Tempo integration
- **Prometheus**: Metrics collection and monitoring
- **Grafana**: Dashboards and visualization
- **Loki**: Log aggregation and analysis
- **Request Context Middleware**: Automatic trace/run/policy header propagation
- **Golden Trace**: End-to-end trace validation from gateway to worker

## Models & Sizing

* Default assumes models fit in **12 GB** (e.g., 7–13B, FP16 or low-bit). Use vLLM paged attention & quantization for longer contexts.
* When models outgrow 12 GB: consider quantized variants or re-evaluate GPU topology.
* WrkHrs supports both vLLM and Ollama backends for LLM inference.

## MCP Hybrid Architecture

This system implements a hybrid MCP (Model Context Protocol) architecture:

| Dimension                    | Install **globally** on control plane                                                    | Install **per-repo** (in the project)                                        |
| ---------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Scope & reuse**            | Cross-project tools (GitHub, Jira, search, vector DB, secrets broker, artifact registry) | Repo-unique tools (custom code indexer, domain schema, one-off integrations) |
| **Versioning stability**     | You want **one version** for all teams; change managed by infra                          | The repo must **pin** exact versions compatible with its code/tooling        |
| **Security & secrets**       | Centralized secret custody, auditing, network ACLs                                       | Least-privilege, repo-scoped tokens, sandboxes per project                   |
| **Isolation / blast radius** | Lower isolation (shared process) unless namespaced                                       | High isolation; failures/updates affect only that repo                       |
| **Reproducibility / CI**     | Good for common infra; less deterministic per-repo without careful tagging               | Strong: repo contains its MCP stack → portable dev/CI                        |
| **Performance / caching**    | Shared caches (code search, embeddings) benefit all repos                                | Tailored indexes/caches per repo; no cross-pollution                         |
| **Ops overhead**             | Lower (one place to patch/observe)                                                       | Higher (N stacks), but automated with templates                              |

### Global MCP Servers (Control Plane)
- **GitHub MCP**: Repository operations, issue tracking, pull requests, GitHub Projects integration
- **Filesystem MCP**: File operations, code analysis, dependency tracking
- **Code Resources MCP**: Indexed codebase datasets with embeddings for code search
- **Document Resources MCP**: PDF/textbook datasets with chunking for document search
- **Secrets MCP**: Secure secrets management with Vault integration
- **Vector DB MCP**: Embedding search, knowledge retrieval
- **MCP Registry**: Auto-registration and discovery of MCP servers with health monitoring

### Per-Repo MCP Servers
- Custom code indexers
- Domain-specific schemas
- Project-unique integrations

## Quick Start: End-to-End Trace

### Golden Trace Example

Test the complete observability stack with a golden trace:

```bash
# Start the full stack
make up-all

# Run smoke test with golden trace
make smoke-test

# Send a chat request with trace headers
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-trace-id: golden-trace-001" \
  -H "x-run-id: golden-run-001" \
  -H "x-policy-set: golden-policy" \
  -d '{
    "model": "mistralai/Mistral-7B-Instruct-v0.3",
    "messages": [{"role": "user", "content": "Explain quantum computing with proper citations."}],
    "temperature": 0.7,
    "max_tokens": 200
  }'
```

### Policy Enforcement

The system automatically enforces policies on all chat completions:

- **Hedging Detection**: Flags uncertain language ("might", "could", "seems")
- **Citation Requirements**: Validates proper citations and references
- **Evidence Standards**: Ensures factual claims are supported
- **SI Units**: Normalizes measurements to standard units

Policy verdicts are logged to MLflow and included in response headers:

```bash
# Check policy verdict headers
curl -I -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "test", "messages": [{"role": "user", "content": "This might be correct."}]}'

# Response headers include:
# x-policy-verdict: False
# x-policy-score: 0.3
```

### MCP Auto-Registration

MCP servers automatically register on startup:

```bash
# Register a new MCP server
curl -X POST http://localhost:8001/mcp/registry/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-mcp",
    "type": "tool",
    "url": "http://test-mcp:7000",
    "tools": [{"name": "test_tool", "description": "A test tool"}]
  }'

# List registered servers
curl http://localhost:8001/mcp/registry
```

## Observability

* **MLflow**: Experiment tracking, model registry, and artifact storage for all AI operations
* **Prometheus**: Scrapes vLLM, WrkHrs services, and system metrics
* **Grafana**: Dashboards for service health, performance, and resource usage
* **Loki**: Log aggregation and analysis for all services
* **Tempo**: Distributed tracing for request flow analysis
* **Jaeger**: Trace visualization and analysis
* Comprehensive alerting for service health, performance, and resource usage

## Security

* LAN allowlist, mTLS (Caddy), token auth for internal APIs.
* Optional WireGuard/Tailscale for remote laptops into the server.
* Vault integration for secrets management.

## Development Workflow

1. **Local Development**: Use VS Code Dev Containers for consistent environment
2. **Testing**: Comprehensive test suite with pytest, mypy, ruff, black
3. **CI/CD**: Automated testing, building, and deployment via GitHub Actions
4. **Deployment**: SSH-based deployment to server and worker nodes

## Proxmox Setup

See `deploy/server/provision_proxmox.md` for VM/LXC creation, cloud-init, and networking (VLANs, bridges).

## Makefile Commands

```bash
# Platform services (MLflow, observability)
make platform-up    # Start platform services
make platform-down   # Stop platform services
make logs-platform   # View platform logs

# AI stack (WrkHrs services)
make ai-up           # Start AI stack services
make ai-down         # Stop AI stack services
make logs-ai         # View AI stack logs

# Full server deployment (platform + AI + server)
make server-up       # Start full server stack
make server-down     # Stop full server stack
make logs-server-full # View full server logs

# Worker deployment
make worker-up       # Start GPU worker
make worker-down     # Stop GPU worker
make logs-worker     # View worker logs

# Health and testing
make health          # Health check all services
make smoke-orchestration # CLI smoke: orchestrator + gateway (no OpenClaw)
make bundle-orchestration-logs # Bundle logs + snapshots for debugging
make seed-corpora    # Seed RAG corpora
make eval            # Run evaluation harness
make mlflow-ui       # Open MLflow UI

# Local development
make up              # Start local stack
make down            # Stop local stack
make logs            # View logs
make test-chat       # Test chat endpoint

# Addons
make up-addons       # Start addon stack (profiles)
make logs-addons     # View addon logs
make up-all          # Start core + server + addons

# Testing
make test            # Run all tests
make lint            # Run linting
make type            # Run type checking
make fix             # Fix linting issues

# CI simulation
make ci              # Run full CI pipeline
```

### Subdomain Routing (Caddy)

- The reverse proxy uses subdomains with internal TLS. We now prefer the `.lan` domain to avoid mDNS conflicts with `.local`. Add DNS/hosts entries pointing these to the server IP (e.g., via Pi‑hole):
  - api.lan, router.lan
  - ai.lan (WrkHrs AI stack)
  - mlflow.lan, tempo.lan, loki.lan, jaeger.lan (observability)
  - grafana.lan, prometheus.lan
  - homarr.lan, pihole.lan
  - meili.lan, searx.lan
  - sso.lan (Authentik)
  - nextcloud.lan, immich.lan, vikunja.lan, pelican.lan
  - mcp-github.lan, mcp-files.lan, mcp-secrets.lan, mcp-vector.lan
- When accessing from a browser, use port 8443 (example: https://grafana.lan:8443).

### DNS Blocker Choice (Pi‑hole vs AdGuard)

- Pi-hole is available in the host/homelab server profile. AdGuard Home is scaffolded in its own add-on profile and is not started by default dev.
- Use only one DNS blocker at a time. To test AdGuard:
  1) Stop Pi-hole: `docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.platform.yml -f docker/compose-profiles/docker-compose.ai.yml -f docker/compose-profiles/docker-compose.server.yml stop pihole`
  2) Start AdGuard: `docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.addons.yml --profile adguard up -d`
  3) Visit https://adguard.local:8443 after adding DNS/hosts entries

## Project Structure

Canonical Git remote: **[github.com/mhold3n/server](https://github.com/mhold3n/server)**. Use a **single clone** for day-to-day work; optional legacy repos belong **outside** this tree; see [`docs/dev-environment.md`](docs/dev-environment.md). WrkHrs-derived gateway and Birtha API/router/worker sources live under **`xlotyl/services/...`** ([`docs/migration-wrkhrs-path.md`](docs/migration-wrkhrs-path.md) is being updated for the new paths).

```
server/   # repository root (suggested clone folder name)
├── claw-code-main/             # Git submodule: fork mhold3n/claw-code (Birtha-local patches)
├── openclaw/                   # Git submodule: fork mhold3n/openclaw (Birtha-local patches)
├── void/                       # Git submodule: mhold3n/void
├── xlotyl/                     # Git submodule: mhold3n/xlotyl (AI product sources)
│   └── services/               # API, router, worker, gateway, domains, model-runtime, …
├── services/                    # Infra / platform services remaining on server (no AI control-plane copies)
├── mcp-servers/mcp/            # MCP servers
│   ├── servers/                # Global and per-repo MCP servers
│   │   ├── github-mcp/         # GitHub MCP with Projects integration
│   │   ├── code-resources-mcp/ # Code indexing and search
│   │   └── doc-resources-mcp/  # Document indexing and search
│   └── config/                 # MCP server configuration
├── docker/
│   ├── compose-profiles/       # Canonical repo-level Compose profiles
│   └── config/                 # Reverse proxy and observability config
├── worker/                     # GPU worker configuration
│   ├── vllm/                   # vLLM setup and docs
│   └── tgi/                    # TGI alternative
├── deploy/                     # Deployment scripts and guides
│   ├── server/                 # Proxmox provisioning
│   └── ci/                     # CI/CD scripts
├── scripts/                    # Helper scripts
│   ├── health_check.sh         # Unified health check
│   └── ingest/                 # Corpus ingestion scripts
├── docs/                       # Documentation
│   ├── runbooks/               # Operational runbooks
│   └── adr/                    # Architecture Decision Records
└── dev/                        # Development tools
    ├── containers/             # Dev container configuration
    └── scripts/                # Helper scripts
```

## Contributing

1. Install pre-commit hooks: `make install-pre-commit`
2. Follow the coding standards (ruff, black, mypy --strict)
3. Write tests for new functionality
4. Update documentation as needed
5. Submit pull requests with clear descriptions

## License

MIT License - see [LICENSE](LICENSE) for details.
