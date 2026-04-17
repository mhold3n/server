# Local docs and artifact directories

Some paths **fill in on a real machine** (compose bind mounts, caches, operator notes). **Do not** commit generated blobs or full “local docs” dumps into this repo. Instead:

## Pattern

For each logical directory (or class of paths):

1. Add or maintain a **`README.md`** next to the glue (or under `docs/`) that describes:
   - **Purpose** of the directory
   - **What artifacts** appear (file name patterns, not the files themselves)
   - **What creates them** (Makefile target, compose service, script)
   - That the path is **gitignored** or **machine-local** where applicable

2. Keep **canonical prose** in [`docs/`](.) (reviewable, linked from the stub).

## Examples in this repo

| Topic | Where |
|-------|--------|
| Compose durable data root | [`compose-data-and-caches.md`](compose-data-and-caches.md) (`COMPOSE_DATA_ROOT`, `.docker-data/`) |
| Pi-hole config glue vs image | [`runbooks/third-party-components.md`](runbooks/third-party-components.md) and `docker/config/dns/pihole/README.md` |
| Dev caches | [`dev-environment.md`](dev-environment.md) (`CACHE_ROOT`, `.cache/`) |

## “Local docs”

If operators keep notes beside the repo on disk, prefer a **short pointer** in tracked docs (e.g. “team wiki URL” or “path convention”) rather than copying those files into `docs/`.
