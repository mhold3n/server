# Infrastructure state vs GitHub

This document explains how **on-premises infrastructure**, **backups**, and **Git** fit together for the **mhold3n/server** mothership and its **xlotyl** submodule.

## Layers of truth

1. **Primary** — Live systems on the **primary server** (including **RAID-backed** storage where applicable). This is the running source of truth for what is actually deployed.
2. **Secondary** — **Backups of critical files** on **secondary machines** (and offline media if you use them). Use these for recovery when the primary site fails or data is corrupted.
3. **Tertiary — GitHub** — **Git** records **commits**, **branches**, and **pull requests**. It is the main **web-based tracker** for **differences** between:
   - copies on secondary machines and **developed** trees,
   - **developed** revisions and what is **deployed** on primary/secondary,
   - **iteration** and **maturity** of codebases across machines over time.

GitHub is **not** a backup replacement for RAID or secondary backups. Treat it as **version control and collaboration history**, not durable archival storage.

## Server repo role

The **server** repository primarily exists to **track** infrastructure layout, compose, CI, and **pinned** submodule state (**xlotyl**, etc.) so that changes are reviewable and reproducible. It complements — but does not replace — local operational practices.

## Related

- MCP ownership vs tracking: [`mcp-servers/README.md`](../mcp-servers/README.md), [`xlotyl/mcp-servers/README.md`](../xlotyl/mcp-servers/README.md) (submodule).
- Dev bootstrap: [`dev-environment.md`](dev-environment.md).
