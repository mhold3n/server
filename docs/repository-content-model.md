# Repository content model (pointer-first)

This document describes what belongs in **mhold3n/server** on GitHub versus what stays **out of the default clone**. The goal is **reproducible infrastructure**: another developer can clone this repo and follow docs to **recreate the shape** of how our stack is wired, without inheriting full backups or machine-local blobs.

## What this repo is for

| Category | In-repo treatment |
|----------|-------------------|
| **Runs / processes / layout** | Compose profiles, Makefiles, shell scripts, env templates, CI workflows—**executable glue** |
| **Third-party maintained software** (e.g. Pi-hole, base images) | **Links** to upstream projects, official docs, and **pinned image names/tags** in compose—**not** vendoring upstream source trees |
| **Machine-local or backup-style trees** (e.g. dated MBMH snapshots, full disk backups) | **Outside** the default tracked tree—**pointers and index docs** only; see [legacy-archive.md](legacy-archive.md) |
| **Artifact output directories** (build outputs, caches, compose bind mounts) | **Not** committed; **README stubs** (this doc + [local-docs-and-artifacts.md](local-docs-and-artifacts.md)) describe what appears where |
| **Custom packages we author** (must travel with automation) | **Portable sources**: either **separate GitHub repos** with thin CI callers into this repo’s reusable workflow, and/or **canonical copies under [XLOTYL/xlotyl](https://github.com/XLOTYL/xlotyl)**—see [xlotyl-and-standalone-packages.md](xlotyl-and-standalone-packages.md) |

Rough target: most of what you see on GitHub is **pointers, glue, and documentation**; a smaller fraction is **first-party code** (e.g. host MCP servers under `mcp-servers/`) that clones must carry.

## Related

- [infrastructure-and-git.md](infrastructure-and-git.md) — Git vs on-prem truth
- [legacy-archive.md](legacy-archive.md) — off-repo legacy snapshot pointer
- [local-docs-and-artifacts.md](local-docs-and-artifacts.md) — README pattern for generated paths
- [xlotyl-and-standalone-packages.md](xlotyl-and-standalone-packages.md) — domain packages and xlotyl
