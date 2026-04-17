# Legacy archive (off-repo)

Historical **MBMH** training/runtime material, the retired `engineering_physics_v1` harness, and related trees **do not** live in this repository’s default branch as a bulk import. They were moved to keep the **server** repo focused on **infrastructure tracking** and **cloneable glue**—see [repository-content-model.md](repository-content-model.md).

## Default location (sibling checkout)

By convention, a **dated snapshot** may live beside this clone:

- Path: **`../server-local-archive/2026-04-08/server/`** (relative to the repository root)

That path contains (among other things) **`mbmh/`** for anyone who needs the historical training/runtime environment.

## Environment variable

Scripts that reference the archive use:

- **`LEGACY_ARCHIVE_ROOT`** — absolute or relative path to the directory that **contains** `mbmh/` (i.e. the `server` folder inside the dated snapshot, not the `mbmh` folder itself).

Default in [`scripts/bootstrap_tool_env.sh`](../scripts/bootstrap_tool_env.sh): `$ROOT/../server-local-archive/2026-04-08/server` when unset.

Override when your team stores the archive elsewhere (NAS, different folder name):

```bash
export LEGACY_ARCHIVE_ROOT=/path/to/2026-04-08/server
```

CI jobs that do not need MBMH should not require this path to exist.

## Optional: submodule or private repo

If you need **versioned linkage** without committing the full tree to **mhold3n/server**, a **private** repository or **git submodule** pointed at that snapshot is acceptable. The public repo should still document **what** the archive is and **where** operators find it, not duplicate multi-gigabyte trees by default.
