# Mobile Offline Surrogates

Use this profile to validate mobile-side behavior when desktop/server infrastructure is unavailable.

## What it provides

- Deterministic API surrogates for:
  - `orchestrator`
  - `rag-api`
  - `asr-api`
  - `mcp`
  - `tool-registry`
- Same service names and routes as the normal stack.
- Scenario profiles for realistic behavior:
  - `nominal`
  - `degraded`
  - `flaky`
  - `rate-limited`
  - `auth-error`
  - `outage`
- Fault and latency injection via headers for targeted mobile tests.

## Start mobile profile

```bash
cd services/wrkhrs
make up-mobile
```

Health check:

```bash
make health-mobile
```

Quick end-to-end test through gateway:

```bash
make test-mobile
```

## Per-request behavior controls

Set these headers on API calls:

- `X-Surrogate-Profile`: override profile for one request.
- `X-Surrogate-Fault`: force specific failure (`429`, `401`, `500`, `503`, `timeout`).
- `X-Surrogate-Latency-Ms`: force exact latency for one request.

Example:

```bash
curl -X POST http://localhost:8081/chat \
  -H "Content-Type: application/json" \
  -H "X-Surrogate-Profile: degraded" \
  -H "X-Surrogate-Latency-Ms: 250" \
  -d '{"messages":[{"role":"user","content":"Summarize stress and deflection assumptions"}]}'
```

Gateway and orchestrator now forward these headers downstream, so the same controls work end-to-end from `POST /v1/chat/completions`.

## Determinism model

- Surrogate output is hash-seeded by `SURROGATE_SEED`.
- Same input + same profile + same seed produces stable output shape and content.
- `request_no` and profile metadata are returned to support replay/debugging.

## Notes

- The mobile profile is intended for contract and UX validation, not scientific fidelity.
- Keep the normal `make up-dev` path for real integration and performance baselining.
