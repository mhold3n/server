# Canonical server clone (retire duplicate checkouts)

Use **one** working copy of **[mhold3n/server](https://github.com/mhold3n/server)** for day-to-day development. A second full clone (e.g. a directory used only for CI experiments) creates **drift**: branches and uncommitted changes only exist on one disk.

## Consolidation steps

1. In the **duplicate** clone, list branches not merged to `origin/main` (`git branch -a`, `git log origin/main..HEAD`).
2. Push unique work as branches to **origin** and open PRs from the **canonical** clone, or cherry-pick commits.
3. After `main` contains everything you need, **delete** the extra clone directory locally to avoid confusion.

## Reference

- [dev-environment.md](../dev-environment.md) — single clone + sibling `xlotyl`
- [repository-content-model.md](../repository-content-model.md) — what belongs in the tracked repo
