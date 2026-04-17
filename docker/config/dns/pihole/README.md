# Pi-hole glue configuration

This directory holds **minimal, repo-tracked** files mounted into the **official Pi-hole Docker image** (`pihole/pihole`). It is **not** a fork of Pi-hole.

- **Upstream image and docs:** [Pi-hole Docker](https://github.com/pi-hole/docker-pi-hole)
- **How we run it:** [`docker/compose-profiles/docker-compose.server.yml`](../../../compose-profiles/docker-compose.server.yml) service `pihole`
- **Runtime state** (`etc/pihole`, lists DB, etc.) lives under `${COMPOSE_DATA_ROOT}/server/pihole_*` on the host—**not** committed; see [docs/compose-data-and-caches.md](../../../docs/compose-data-and-caches.md)

Files here (`custom.list`, `local-dns.conf`) are **operator-maintained glue** for local DNS overrides and dnsmasq snippets.
