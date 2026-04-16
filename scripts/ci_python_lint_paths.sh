#!/usr/bin/env bash
# Shared Ruff/Black path list for GitHub Actions and Makefile lint/fix targets.
# Infra packages live under `server/`; AI control-plane services live under `xlotyl/`.
#
# Usage from the repository root:
#   source scripts/ci_python_lint_paths.sh
#   ruff check $CI_PYTHON_LINT_PATHS
#   black --check $CI_PYTHON_LINT_PATHS

CI_PYTHON_LINT_PATHS="mcp-servers/mcp/servers/ xlotyl/services/api-service xlotyl/services/router-service xlotyl/services/worker-service xlotyl/services/model-runtime xlotyl/services/engineering-core xlotyl/services/mcp-registry-service xlotyl/services/response-control-framework xlotyl/services/domain-engineering xlotyl/services/domain-research xlotyl/services/domain-content xlotyl/services/ai-shared-service xlotyl/services/structure-service xlotyl/services/media-service"
export CI_PYTHON_LINT_PATHS
