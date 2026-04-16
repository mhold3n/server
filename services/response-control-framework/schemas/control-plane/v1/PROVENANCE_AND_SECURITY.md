# Provenance, replay, and local security (production-internal)

<!--
For agents: single-user local deployment still needs auditability and safe defaults.
Structured contracts live in `*.schema.json`; this file captures policy choices.
-->

## Identifiers

- **`trace_id`**: correlates one engineer-facing run (problem brief through verification).
- **`artifact_id` / `artifact://` refs**: content-addressed or stable logical ids in the local artifact store.
- **`inputs_hash` / `input_digest_sha256`**: hash of normalized inputs for cache keys (see `routing-policy.cache_policy`).

## What to log (minimum)

| Event | Record |
|-------|--------|
| Model or tool invocation | `trace_id`, contract kind, schema ids, token/cost estimates, outcome |
| Artifact write | `artifact_id`, `artifact_type`, `schema_version`, producer, `input_artifact_refs` |
| Validation failure | `contract-error.schema.json` envelope with paths |

## Redaction

- Never persist raw API keys or OAuth tokens in artifact payloads or logs.
- For prompts that may contain secrets, store **redacted text + sha256** of the raw blob in a separate local-only file if replay is required.

## Replay (best effort)

- Re-running a trace requires the same **schema versions**, **routing_policy** version, **tool versions**, and input artifact hashes. Record these in the decision log or run metadata.

## Local sandbox (filesystem / tools)

- **Repo boundary**: coding-plane tools only touch paths under the registered project root; deny `..` escapes and absolute paths outside allowlists.
- **Network**: off by default for codegen tasks unless `routing_policy` and task packet explicitly allow `NETWORK` side effects.
- **Multimodal / PDF inputs**: treat documents as untrusted; extraction output is **provisional** until schema and citation gates pass (prompt-injection aware).

## Cache privacy

- `persist_tier=disk_allowed` must not write unredacted third-party PDFs to shared caches; prefer hashed keys and encrypted at-rest storage for sensitive workspaces.
