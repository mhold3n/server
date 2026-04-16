# Domain Content

Orchestration sources for **content** mode and the **video_editing** pool, plus **Whisper** SRT helpers used by media tooling.

## Wiki ownership

Markdown under `wiki/orchestration/` is merged into the super-project tree by `scripts/sync_domain_orchestration_wiki.py`.

## Public API

- `default_content_pool_keys()` — default pools for content workflows.
- `domain_content.whisper` — `run_whisper_srt` and related types (CLI-based Whisper).

[`martymedia`](../../media-service) re-exports the Whisper helpers from this package.

## Tests

```bash
cd services/domain-content
pytest -q
```
