# Ollama memory governor (macOS) — runbook

## Problem statement

On a 32GB unified-memory Mac, bringing Ollama online with a large model can trigger extreme memory pressure (or container/VM instability). We want **orchestrator-driven safety**:

- Never crash the OS (no window crashes / data loss).
- Never weaken security posture.
- Let non-essential processes keep running until they naturally exit.
- As memory is freed, automatically allow Ollama to load larger models / do more work.

## Design summary

- A **host daemon** (`services/host-memory-governor/`) runs under `launchd` and exposes a small authenticated HTTP API with memory pressure + headroom recommendations.
- The TypeScript orchestrator’s **Ollama adapter** polls the daemon and blocks Ollama calls until the daemon reports it is safe, then chooses a model tag based on the recommended profile.

## Components

### 1) Host memory governor (launchd)

- **Source**: `services/host-memory-governor/src/server.py`
- **Port**: `8766` (default)
- **Auth**: `Authorization: Bearer $HOST_MEMORY_GOVERNOR_TOKEN`
- **Key endpoints**:
  - `GET /v1/status`
  - `GET /v1/top?limit=20`
  - `GET /v1/recommendation?workload=ollama`

#### Install (local dev)

1) Pick a token (treat it like a password).
2) Copy `dev/launchd/com.server.host-memory-governor.plist` somewhere under your user LaunchAgents (or keep it in-repo and symlink).
3) Replace `__REPLACE_WITH_TOKEN__` in the plist with your token.
4) Load with launchd.

The service logs to:
- `/tmp/host-memory-governor.out.log`
- `/tmp/host-memory-governor.err.log`

### 2) Orchestrator integration

The Ollama adapter will only apply memory governance when `HOST_MEMORY_GOVERNOR_URL` is set.

#### Required environment (wrkhrs-agent-platform container)

- `HOST_MEMORY_GOVERNOR_URL` (recommended: `http://host.docker.internal:8766`)
- `HOST_MEMORY_GOVERNOR_TOKEN`

#### Optional: profile-based Ollama model tags

When the governor recommends a profile, the adapter picks the matching tag if set:

- `OLLAMA_MODEL_TINY`
- `OLLAMA_MODEL_SMALL`
- `OLLAMA_MODEL_MEDIUM`
- `OLLAMA_MODEL_LARGE`

If not set, it uses the requested model unchanged.

## Docker: enabling Ollama locally on macOS

The Mac dev stack uses `docker/compose-profiles/docker-compose.local-ai.yml`. Ollama is opt-in:

- service: `ollama-runner`
- profile: `ollama-macos`

Enable it by adding `--profile ollama-macos` to your compose command chain.

## Expected behavior

- If memory pressure is high / headroom is low, Ollama requests will **wait** (poll ~1.5s) rather than attempting to load and potentially destabilize the system.
- As non-essential processes exit and headroom increases, the governor will return a larger profile and the adapter will start using larger model tags (if configured).

## Troubleshooting

- Ollama calls hang forever:
  - Confirm governor is reachable from the container (`HOST_MEMORY_GOVERNOR_URL`).
  - Confirm the token matches.
  - Check `/v1/recommendation?workload=ollama` — if it returns `allow_start=false`, this is expected.\n+
- Unauthorized errors:
  - Ensure `HOST_MEMORY_GOVERNOR_TOKEN` is set in the orchestrator container environment and the launchd daemon uses the same token.\n+

