#!/usr/bin/env python3
"""
Serve the local runtime with the OpenAI-compatible API.

Usage:
    python scripts/serve_local.py \
        --config configs/runtime/openai-compatible.yaml \
        --bundle latest \
        --agents-dir configs/agents \
        --api-keys configs/auth/api_keys.yaml
"""

import argparse
import sys
import os
import yaml

# Ensure the repo root is on sys.path so `src.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.runtime.config import RuntimeConfig
from src.runtime.server import create_and_run_server


def main():
    parser = argparse.ArgumentParser(description="Start the local runtime server")
    parser.add_argument("--config", type=str, default="configs/runtime/openai-compatible.yaml",
                        help="Runtime config YAML")
    parser.add_argument("--bundle", type=str, default="latest",
                        help="Runtime bundle ID to load")
    parser.add_argument("--agents-dir", type=str, default=None,
                        help="Directory containing agent YAML configs")
    parser.add_argument("--api-keys", type=str, default=None,
                        help="Path to api_keys.yaml")
    parser.add_argument("--host", type=str, default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--hf-hub-timeout",
        type=int,
        default=None,
        metavar="SEC",
        help="HF_HUB_* HTTP timeout seconds (default from YAML or 300)",
    )
    args = parser.parse_args()

    with open(args.config, "r") as f:
        conf_dict = yaml.safe_load(f) or {}

    # CLI overrides
    if args.agents_dir:
        conf_dict["agents_dir"] = args.agents_dir
    if args.api_keys:
        conf_dict["api_keys_path"] = args.api_keys
    if args.bundle:
        conf_dict["bundle_id"] = args.bundle
    if args.host:
        conf_dict["host"] = args.host
    if args.port:
        conf_dict["port"] = args.port
    if args.hf_hub_timeout is not None:
        conf_dict["hf_hub_timeout_seconds"] = args.hf_hub_timeout

    cfg = RuntimeConfig(**conf_dict)
    create_and_run_server(cfg)


if __name__ == "__main__":
    main()
