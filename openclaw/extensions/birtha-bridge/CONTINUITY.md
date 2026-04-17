# Session mirror vs authority

The **session mirror** (plugin-local JSON keyed by `session_key`) may hold **opaque string refs** copied from `result.referential_state` returned by Birtha.

- **Authoritative** engineering artifacts, task packets, publish decisions, and referential truth live in **Xlotyl** (api-service, control plane, DevPlane).
- **Tool-model lane** responses (`POST /api/ai/tool-query`) are **never authoritative**: they include provenance with `authoritative=false` and `requires_validation=true`. They may be used as local UI hints or as **evidence** fed into governed flows — not as final answers.

See also: [`docs/runbooks/openclaw-birtha-bridge.md`](../../../docs/runbooks/openclaw-birtha-bridge.md) in the server repo.
