# Compose data root and local caches

This repo tracks **how** services run (compose files, pins, config snippets). It does **not** track **runtime data** written under the compose data root.

## `COMPOSE_DATA_ROOT`

Docker Compose profiles use a configurable root for bind-mounted volumes (default **`.docker-data/`** at the repository root). That directory is **gitignored**—see the root [`.gitignore`](../.gitignore).

**What typically appears there (examples, not exhaustive):**

- Per-service state directories (e.g. Pi-hole `etc/pihole`, Caddy data, observability stores) as declared in `docker/compose-profiles/`.
- Paths are defined next to each service in compose; image versions are pinned or tagged in compose/env files.

**Operators:** after `compose up`, inspect the tree under `${COMPOSE_DATA_ROOT:-.docker-data}` on your host to see actual layout for your profile.

## Application caches (non-compose)

Development tool caches and model caches default under **`.cache/`** when using [`scripts/workspace_env.sh`](../scripts/workspace_env.sh)—see [dev-environment.md](dev-environment.md).
