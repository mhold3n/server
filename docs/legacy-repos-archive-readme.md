# README snippets for archived legacy repositories

After **`mhold3n/server`** is the active remote and CI is green, archive the old repositories and replace each `README.md` with the matching block below.

## `mhold3n/Birtha_bigger_n_badder`

```markdown
# Moved

This project continues as **[server](https://github.com/mhold3n/server)** — the active Birtha + WrkHrs orchestration repo.

Clone: `git clone https://github.com/mhold3n/server.git`
```

## `mhold3n/WrkHrs`

```markdown
# Moved

The WrkHrs stack is **vendored** in **[server](https://github.com/mhold3n/server)** under [`services/wrkhrs/`](https://github.com/mhold3n/server/tree/main/services/wrkhrs).

Clone: `git clone https://github.com/mhold3n/server.git`
```

## `mhold3n/MBMH-Training`

See [mbmh-training-archive-readme.md](mbmh-training-archive-readme.md).

Then for each repo: **Settings → General → Archive this repository**.

## GitHub Actions secrets

If the old **Birtha_bigger_n_badder** repo had **Actions secrets** or **environments**, copy them into **Settings → Secrets and variables → Actions** on [`mhold3n/server`](https://github.com/mhold3n/server). Archived repos cannot receive new workflow runs, but CI on `server` may need the same credentials.
