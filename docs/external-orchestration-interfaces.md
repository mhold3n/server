# External orchestration interfaces

This document explains how the managed external repos at the repository root:

- `claw-code-main/`
- `openclaw/`

relate to the active control plane, DevPlane, and engineering-governed execution pipeline.

## Managed paths

These paths are intentional and are refreshed from GitHub with:

```bash
npm run deps:external
```

They are not ad hoc local mirrors:

- `claw-code-main/` is the tracked checkout of `ultraworkers/claw-code`
- `openclaw/` is the tracked checkout of `openclaw/openclaw`

## What is active in this repo

The active execution stack in this repository is:

1. `services/api`
2. `services/agent-platform/server`
3. `services/model-runtime`
4. `schemas/control-plane/v1`

Those services implement the live orchestration and engineering pipeline.

## Where Claw Code fits today

`claw-code-main/` is currently an upstream checkout and reference codebase, not a first-class executor in the active pipeline.

Today there is no direct runtime import or dispatch from the control plane, DevPlane, or agent-platform into `claw-code-main/`.

Practical implication:

- Claw Code can be used as an external operator tool or future integration target.
- It is not one of the governed `selected_executor` values in the active task-packet routing model.
- It does not bypass the control-plane gating or DevPlane workspace lifecycle.

## Where OpenClaw fits today

`openclaw/` is also an upstream checkout, but its relationship to the active stack is closer: it maps to the operator/client role rather than the executor role.

In the active services, OpenClaw is treated as an external operator surface, not an internal execution backend:

- DevPlane supports `execution_mode="external"` runs.
- External runs can carry an `agent_session_id`.
- External operators can post run events and completion callbacks back into DevPlane.

That means OpenClaw can sit in front of the active platform as a client/operator shell, but the internal governed execution path still belongs to the control plane plus agent-platform.

## Engineering-governed execution path

The active engineering pipeline is packet-driven:

1. A request enters the API layer and may be promoted into `engineering_task` or `strict_engineering`.
2. The control-plane engineering intake builds governed artifacts:
   - `problem_brief`
   - `engineering_state`
   - `task_queue`
   - `task_packet`
3. DevPlane refuses launch until the problem brief is valid and the engineering state is ready for task decomposition.
4. DevPlane provisions an isolated git worktree and writes `.birtha/task-packet.json` plus the typed engineering artifacts.
5. Internal execution dispatches to `services/agent-platform/server` through `/v1/devplane/runs`.
6. The agent-platform runner reads the active task packet and routes by `routing_metadata.selected_executor`.
7. Deterministic verification runs before the task can become `ready_to_publish`.

## Executor model in the active pipeline

The active routing model is not “OpenClaw vs Claw Code”. It is task-packet executor selection.

Current governed executors are:

- `coding_model`
- `local_general_model`
- `multimodal_model`
- `strategic_reviewer`
- `deterministic_validator`

For code implementation specifically:

- `coding_model` runs through the in-repo TypeScript `OpenMultiAgent` orchestration plus workspace tools.
- `multimodal_model` calls the model-runtime HTTP surface.
- Verification is always brought back under deterministic control-plane commands.

## Net effect

The clean mental model is:

- `openclaw/`: external operator/client surface
- `claw-code-main/`: external coding-agent/reference surface
- `services/api` + `services/agent-platform/server`: authoritative orchestration and DevPlane runtime
- `schemas/control-plane/v1`: authoritative engineering contract surface

So if OpenClaw or Claw Code are used, they should consume the same governed worktree and `.birtha/task-packet.json` artifacts and report back through DevPlane. They are adjacent to the engineering pipeline, not replacements for it.
