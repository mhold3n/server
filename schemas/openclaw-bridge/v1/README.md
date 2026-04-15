# OpenClaw bridge v1 (Birtha shell handshake)

For agents: this folder is the **versioned JSON Schema** for the thin envelope carried in `POST /api/ai/query` under `context.openclaw_bridge`. It is **not** a control-plane orchestration language; Birtha’s task-packet and related schemas remain internal.

## Transport

- **Ingress:** `POST /api/ai/query` on `services/api-service`.
- **Field:** `context.openclaw_bridge` must match `openclaw-bridge-envelope.schema.json` when present. If the key is absent, the request is a normal web/API caller (no bridge validation).

## Idempotency (Phase 1)

OpenClaw-originated turns **must** include `idempotency_key` (required in the envelope schema).

- **Hit:** same `idempotency_key` and identical **idempotency payload hash** → API returns the **cached JSON body** from the prior successful turn (HTTP 200, same shape as a fresh orchestration response).
- **Conflict:** same `idempotency_key` and a **different** payload hash → HTTP **409** with a typed error (`idempotency_key_conflict`). The server does **not** append silently to an existing run.
- **Miss:** unknown key → normal orchestration; on success the response is stored keyed by `idempotency_key` with a TTL (default 24h server-side).
- **Redis unavailable:** replay is skipped (no duplicate suppression); conflicts are still detected if a record appears later.

The payload hash is computed server-side from a canonical encoding of the full `QueryRequest` fields that influence orchestration (see `src/openclaw_bridge/idempotency.py`).

## Attachments (v1)

See `openclaw-bridge-envelope.schema.json` `$defs.attachment`. Summary:

- **References:** `kind: "url"` with `https` only (Birtha may tighten host allowlists later), or `kind: "storage_ref"` with an opaque `ref` string.
- **Inline:** `kind: "inline_base64"` with `media_type` + base64 `data`; **total decoded inline bytes per turn** must not exceed **65536** (64 KiB). Oversize requests fail validation (HTTP 400) with a typed error—**no silent truncation**.

## Streaming (Phase 3+)

Typed events are defined in `events/stream-event.schema.json`. The primary UX stream must **not** be raw workflow logs; use discriminated `type` values such as `run.started`, `run.completed`, etc.

## MCP as primary bridge

Cross-exposing Birtha MCP tools to OpenClaw as the **primary** shell path is explicitly **Phase 4** (see `docs/external-orchestration-interfaces.md` in the Birtha repo). Phase 1 uses HTTPS + this envelope only.
