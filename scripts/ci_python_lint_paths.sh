#!/usr/bin/env bash
# Shared Ruff/Black path list for GitHub Actions and Makefile lint/fix targets.
# AI control-plane sources live in https://github.com/XLOTYL/xlotyl (not this repo).
#
# Usage from the repository root:
#   source scripts/ci_python_lint_paths.sh
#   ruff check $CI_PYTHON_LINT_PATHS
#   black --check $CI_PYTHON_LINT_PATHS

CI_PYTHON_LINT_PATHS="mcp-servers/mcp/servers/"
export CI_PYTHON_LINT_PATHS
