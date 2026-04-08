# Larrak Audio (services)

Re-homed local audiobook pipeline service.

Bootstrap from the repo root:

```bash
scripts/bootstrap_tool_env.sh marker-pdf
scripts/bootstrap_tool_env.sh larrak-audio
export MARKER_BIN="$PWD/.cache/envs/marker-pdf/bin/marker_single"
source .cache/envs/larrak-audio/bin/activate
```

CLI entrypoint:

```bash
larrak-audio doctor
```

Default cache and tool locations:

- Marker runtime: `.cache/envs/marker-pdf`
- Larrak runtime: `.cache/envs/larrak-audio`
- HF/model cache: `.cache/models/hf`

See this folder’s `src/larrak_audio/` package for details.
