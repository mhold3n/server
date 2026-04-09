#!/usr/bin/env bash
set -euo pipefail

# Keep the GitHub-backed external repos pinned to their configured upstream
# branches in .gitmodules.
git submodule sync --recursive -- claw-code-main openclaw
git submodule update --init --remote --recursive claw-code-main openclaw
git submodule status -- claw-code-main openclaw
