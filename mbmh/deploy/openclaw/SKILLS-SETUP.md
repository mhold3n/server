# OpenClaw bundled skills: the “42 blocked” situation

Run this any time:

```bash
openclaw skills check
```

You will see **~50 total**, **~8 eligible**, **~42 missing requirements**. That is **normal**: bundled skills are optional integrations (CLIs, API keys, channels). You do **not** need to “unblock” all 42 unless you intentionally want every integration.

## Strategies

### 1. Do nothing (recommended default)

Use the **8 ready** skills (`gh-issues`, `github`, `healthcheck`, `imsg`, `node-connect`, `skill-creator`, `video-frames`, `weather`) and ignore the rest. Built-in OpenClaw tools (chat, exec, browser, etc.) still work; **skills** are extra playbooks.

### 2. Enable only what you need

Pick rows from `openclaw skills check` → **Missing requirements** and fix **only** those:

| Requirement type | What to do |
|------------------|------------|
| `bins: foo` | Install the binary (often `brew install …`; name may differ, e.g. `rg` → `brew install ripgrep`) |
| `env: VAR` | Export `VAR` or set `skills.entries."skill-name".env` / secrets in `~/.openclaw/openclaw.json` ([Skills config](https://docs.openclaw.ai/tools/skills-config)) |
| `config: channels.*` | Configure that channel in `openclaw.json` (Discord, Slack, BlueBubbles, etc.) |
| `anyBins: a, b, c` | Install **at least one** of the listed CLIs |

Docs: [Skills](https://docs.openclaw.ai/tools/skills), [Skills config](https://docs.openclaw.ai/tools/skills-config).

### 3. Turn off skills you will never use

If the UI noise bothers you, disable specific bundled skills:

```json5
{
  skills: {
    entries: {
      "spotify-player": { enabled: false },
      sonoscli: { enabled: false },
    },
  },
}
```

Optional **allowlist** (only these bundled skills can load):

```json5
{
  skills: {
    allowBundled: ["github", "gh-issues", "weather", "healthcheck", "skill-creator"],
  },
}
```

Restart the gateway after edits.

## Quick wins (common, low effort)

- **`session-logs` (`bins: rg`)** — install Ripgrep: `brew install ripgrep` (`rg` on PATH).
- **`tmux` (`bins: tmux`)** — `brew install tmux`.
- **`coding-agent` (`anyBins: claude, codex, opencode, pi`)** — install **one** CLI you already use (e.g. Codex or Claude Code).

## What the 42 typically need (reference)

From `openclaw skills check` (your machine may vary slightly):

- **macOS / Apple ecosystem CLIs:** `op`, `memo`, `remindctl`, `grizzly`, `things`, `peekaboo`, `sag`, etc. — install from each tool’s docs or brew taps; many are niche.
- **Third-party CLIs:** `gemini`, `himalaya`, `wacli`, `blogwatcher`, `clawhub`, `mcporter`, … — install only if you use that product.
- **API keys:** `NOTION_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_PLACES_API_KEY`, `TRELLO_*`, `ELEVENLABS_API_KEY`, Sherpa env dirs, etc. — add via env or `skills.entries.*.apiKey` / `env`.
- **Channels:** `channels.discord.token`, `channels.slack`, `channels.bluebubbles`, `plugins.entries.voice-call.enabled` — configure in `openclaw.json` when you use those features.

## Inspect one skill

```bash
openclaw skills info <skill-name>
```

## MBMH runtime

Your local **MBMH** `serve_local.py` setup is unrelated to skill gating. Skills are **OpenClaw gateway + host tools + secrets**, not the OpenAI-compatible server on `:8000`.
