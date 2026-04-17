#!/usr/bin/env bash
set -euo pipefail

# This repository no longer vendors AI product sources as submodules.
# Clone https://github.com/XLOTYL/xlotyl beside this repo (default: ../xlotyl) for AI development.
echo "No git submodules to sync for infra. For the AI stack, clone XLOTYL/xlotyl and run:"
echo "  cd ../xlotyl && git submodule update --init --recursive"
