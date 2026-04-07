# Birtha DevPlane OpenClaw Plugin

Native OpenClaw operator plugin for the Birtha development plane.

## What it does

- exposes `devplane_*` operator tools over the Birtha `/api/dev` control-plane API
- ships the `devplane-operator` skill for the OpenClaw-facing control agent
- keeps OpenClaw in the operator role while `services/agent-platform` performs the actual task-agent execution

## Local files

- `openclaw.plugin.json` — native plugin manifest
- `index.ts` — plugin entry and tool registration
- `src/operator-client.js` — lightweight API client helpers
- `skills/devplane-operator/SKILL.md` — operator guidance
- `tests/operator-client.test.mjs` — mocked API-client coverage
