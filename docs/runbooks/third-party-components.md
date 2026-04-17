# Third-party components (link-first)

For software we **do not** maintain (DNS, dashboards, base images, databases), this repo should record:

1. **Official upstream** — project home page or GitHub org (link).
2. **How we run it** — pinned **image** (`image:repo:tag` or digest), compose **service name**, and **minimal glue** under `docker/` (config mounts, env).
3. **What we do not vendor** — upstream source trees stay upstream.

## Pi-hole

- **Upstream:** [https://github.com/pi-hole/docker-pi-hole](https://github.com/pi-hole/docker-pi-hole) — official Docker image and documentation.
- **This repo:** [`docker/compose-profiles/docker-compose.server.yml`](../../docker/compose-profiles/docker-compose.server.yml) service `pihole` uses `pihole/pihole` with env-driven settings; small read-only config under [`docker/config/dns/pihole/`](../../docker/config/dns/pihole/README.md).

## AdGuard Home (optional add-on)

- **Upstream:** follow [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) documentation for installation; this repo’s add-on profile is scaffolded in [`docker/compose-profiles/docker-compose.addons.yml`](../../docker/compose-profiles/docker-compose.addons.yml) — do not run alongside Pi-hole on the same host ports without stopping one first (see root [README.md](../../README.md) DNS section).

## Adding a new third-party service

1. Add compose glue + pins under `docker/`.
2. Document the upstream link here (or in a focused runbook) and in the root README if user-facing.
