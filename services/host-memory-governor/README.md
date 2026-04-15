# Host Memory Governor (macOS)

This service runs on the **macOS host** (outside Docker) and exposes a small, authenticated HTTP API that reports:

- Unified-memory pressure (`memory_pressure` where available)
- Best-effort available/free memory derived from `vm_stat` + `sysctl`
- A conservative **protected baseline** for essential OS stability
- A computed **optional headroom** budget for non-essential workloads (e.g. Docker Ollama)
- A recommendation envelope (`allow_start`, `target_profile`) that the orchestrator can use to **gate** Ollama usage and scale it up as headroom grows.

It is intentionally **non-destructive**: it never kills processes. It only reports and recommends.

## Security model

- The HTTP listener binds to `0.0.0.0` so containers can reach it via `host.docker.internal`.
- Every request requires a bearer token header: `Authorization: Bearer $HOST_MEMORY_GOVERNOR_TOKEN`.
- Bind the port to the loopback interface at the firewall level if you’re on an untrusted network.

## Run locally (manual)

```bash
python3 services/host-memory-governor/src/server.py \
  --host 0.0.0.0 \
  --port 8766 \
  --token "dev-token"
```

## Launchd (recommended)

Install the plist (see `dev/launchd/com.server.host-memory-governor.plist`) and provide the token via environment.

## API

- `GET /v1/status`
- `GET /v1/top?limit=20`
- `GET /v1/recommendation?workload=ollama`

