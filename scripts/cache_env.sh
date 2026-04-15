#!/usr/bin/env bash
# cache_env.sh — canonical CACHE_ROOT layout for uv, npm, Hugging Face weights,
# tool virtualenvs (TOOL_ENV_ROOT), and small dev caches (ruff, mypy, pytest, xdg).
#
# Why: Parent shells (sandboxes, mis-set CI) may export a usable CACHE_ROOT but
# broken child paths (e.g. UV_CACHE_DIR=//.cache/uv). Child vars must always be
# derived from a validated CACHE_ROOT, not merged with stale overrides.
#
# Intended use: source from bash only — e.g. scripts/workspace_env.sh or
# scripts/prove_engineering_harness.sh after optionally exporting CACHE_ROOT
# (including HARNESS_CACHE_ROOT → CACHE_ROOT in the harness).

# Do not `set -e` here: when sourced, the caller owns errexit; nested set can
# surprise callers. Individual mkdir failures are handled explicitly.

_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_ROOT="$(cd "$_SCRIPTS_DIR/.." && pwd)"
_default_cache="$SERVER_ROOT/.cache"

_candidate="${CACHE_ROOT:-$_default_cache}"
if [[ "$_candidate" == //* ]] || ! mkdir -p "$_candidate" 2>/dev/null; then
  CACHE_ROOT="$_default_cache"
  mkdir -p "$CACHE_ROOT"
else
  CACHE_ROOT="$_candidate"
fi

export SERVER_ROOT
export CACHE_ROOT

unset UV_CACHE_DIR TOOL_ENV_ROOT HF_HOME MODEL_CACHE_DIR TRANSFORMERS_CACHE \
  WHISPER_CACHE_DIR NPM_CONFIG_CACHE npm_config_cache XDG_CACHE_HOME \
  RUFF_CACHE_DIR MYPY_CACHE_ROOT PYTEST_CACHE_ROOT 2>/dev/null || true

export UV_CACHE_DIR="$CACHE_ROOT/uv"
export NPM_CONFIG_CACHE="$CACHE_ROOT/npm"
export npm_config_cache="$NPM_CONFIG_CACHE"
export XDG_CACHE_HOME="$CACHE_ROOT/xdg"
export RUFF_CACHE_DIR="$CACHE_ROOT/ruff"
export MYPY_CACHE_ROOT="$CACHE_ROOT/mypy"
export PYTEST_CACHE_ROOT="$CACHE_ROOT/pytest"
export TOOL_ENV_ROOT="$CACHE_ROOT/envs"
export HF_HOME="$CACHE_ROOT/models/hf"
export MODEL_CACHE_DIR="$HF_HOME"
export TRANSFORMERS_CACHE="$HF_HOME"
export WHISPER_CACHE_DIR="$CACHE_ROOT/models/whisper"

mkdir -p \
  "$UV_CACHE_DIR" \
  "$NPM_CONFIG_CACHE" \
  "$XDG_CACHE_HOME" \
  "$RUFF_CACHE_DIR" \
  "$MYPY_CACHE_ROOT" \
  "$PYTEST_CACHE_ROOT" \
  "$TOOL_ENV_ROOT" \
  "$HF_HOME" \
  "$WHISPER_CACHE_DIR" || {
  echo "ERROR: could not create cache directories under CACHE_ROOT=$CACHE_ROOT" >&2
  return 1 2>/dev/null || exit 1
}
