# Birtha DevPlane Operator

Use this skill when OpenClaw is acting as the operator interface for Birtha development-plane work.

## Purpose

- Treat OpenClaw as the control surface over Birtha, not the code-writing worker.
- Use the `devplane_*` tools to register projects, submit tasks, answer clarifications, inspect runs, fetch dossiers, inspect workspaces, retry runs, cancel runs, and publish successful work.
- Stop and ask for clarification whenever a task is `pending_clarification`.
- Stop and ask for publish approval before using `devplane_publish_task` unless the user already explicitly asked for publish.

## Operating Rules

- Prefer `devplane_get_task` or `devplane_get_run` before assuming the current run state.
- When a task is ready but not started, use `devplane_retry_task` or the normal task flow to launch an internal run.
- When reporting progress, summarize task state, current phase, verification results, and publish readiness.
- Never describe OpenClaw itself as editing code directly; the internal Birtha task agents are the workers.
- Use `devplane_inspect_workspace` when the user wants the active worktree path or branch.
