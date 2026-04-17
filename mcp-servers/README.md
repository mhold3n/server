# MCP implementations (tracked in the superproject)

This directory holds **implementation checkouts** for MCP server processes that are **built, tested in CI, and deployed** from the **mhold3n/server** repository onto **primary server hardware**.

## Ownership (canonical vs tracking)

- **xlotyl** **owns** MCP servers as a product: the authoritative catalog, registry, and semantics live in the **[xlotyl](https://github.com/mhold3n/xlotyl)** repo under **`mcp-servers/mcp/config/mcp_servers.yaml`** (see [mcp-servers/README in xlotyl](https://github.com/mhold3n/xlotyl/blob/main/mcp-servers/README.md)).
- **This repo does not own MCP product definitions.** It **tracks**:
  - that these implementations **exist** and are wired in compose where applicable,
  - **validation** via [`scripts/run_ci_local.sh`](../scripts/run_ci_local.sh) and [`.github/workflows/ci.yml`](../.github/workflows/ci.yml),
  - **infrastructure iteration** (Dockerfiles, ports, env) alongside the rest of the mothership stack.

Implementation sources may **migrate** fully into **xlotyl** later; until then, paths under **`mcp/mcp/servers/`** are a **tracked mirror** for deployment and CI, not a claim of product ownership.

## GitHub vs on-premises truth

Operational durability relies on **local RAID** and **secondary-machine backups** of critical files. **GitHub** is a **tertiary** layer: it records **git history** and **diffs** between developed/deployed systems and copies elsewhere as codebases mature — not a substitute for primary or secondary backups. See [`docs/infrastructure-and-git.md`](../docs/infrastructure-and-git.md).

## Layout

- [`mcp/servers/`](mcp/servers/) — per-server packages (Python/Node), Dockerfiles, and [`mcp/servers/README.md`](mcp/servers/README.md) (architecture notes).
