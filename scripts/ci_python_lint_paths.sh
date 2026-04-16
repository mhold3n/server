#!/usr/bin/env bash
# Shared Ruff/Black path list for GitHub Actions and Makefile lint/fix targets.
# Keeps local `make lint` aligned with `.github/workflows/ci.yml`.
#
# Usage from the repository root:
#   source scripts/ci_python_lint_paths.sh
#   ruff check $CI_PYTHON_LINT_PATHS
#   black --check $CI_PYTHON_LINT_PATHS

CI_PYTHON_LINT_PATHS="services/api-service services/router-service services/worker-service services/media-service mcp-servers/mcp/servers/"
export CI_PYTHON_LINT_PATHS
