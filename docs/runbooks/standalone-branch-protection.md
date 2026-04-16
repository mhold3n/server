# Branch protection for standalone package repos

These five repos should require green CI on `main` before merge:

- `mhold3n/response-control-framework`
- `mhold3n/ai-shared-service`
- `mhold3n/domain-engineering`
- `mhold3n/domain-research`
- `mhold3n/domain-content`

## Required check name

After `.github/workflows/ci.yml` is merged, open any PR and note the **exact** check name shown. For the current thin callers (job id `package-ci` calling the reusable workflow’s `lint-typecheck-test`), GitHub reports:

**`package-ci / lint-typecheck-test`**

Use that string as the required status check context in rulesets or classic branch protection.

## Organization ruleset (recommended)

If your GitHub org supports **repository rulesets**, create one ruleset targeting all five repositories (or one ruleset per repo) that:

- Applies to the `main` branch (or `include: ref: refs/heads/main`).
- Requires status checks: add the CI job from the caller workflow.
- Optionally: require pull request before merging, dismiss stale reviews, required reviewers.

Configure under **Organization → Settings → Rules → Rulesets** (or **Repository → Settings → Rules → Rulesets**).

## Classic branch protection (per repo)

**Repository → Settings → Branches → Branch protection rule** for `main`:

- Require a pull request before merging (optional but typical).
- Require status checks to pass: enable the CI workflow’s check.
- Optionally: require branches to be up to date before merging.

## CLI

The GitHub CLI evolves; prefer `gh help ruleset` and the REST API for rulesets (`/repos/{owner}/{repo}/rulesets` or org-level) if you need automation. Exact payloads depend on whether you use classic protection or rulesets—copy from the UI “View YAML” or API examples in GitHub’s docs when available.
