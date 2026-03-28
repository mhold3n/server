#!/usr/bin/env python3
"""
Emit an OpenClaw config fragment for wiring the MBMH OpenAI-compatible server.

This turns (1) "what should be in openclaw.json" into something you can merge
or apply with `openclaw config set`, and optionally verifies the runtime with
HTTP checks (same as OpenClaw will call).

Usage:
  cd mbmh
  .venv/bin/python scripts/emit_openclaw_provider_config.py --check
  .venv/bin/python scripts/emit_openclaw_provider_config.py --provider-slug mbmh-local \\
      --primary-model openclaw-agent > /tmp/mbmh-openclaw-models.json

Then merge the printed JSON under your ~/.openclaw/openclaw.json (see deploy/openclaw/README.md).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml


def _load_runtime(path: str | None) -> dict:
    if not path or not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _first_api_key(keys_path: str) -> str:
    with open(keys_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    keys = data.get("keys") or []
    if not keys or not keys[0].get("key"):
        raise SystemExit(f"No keys found in {keys_path}")
    return str(keys[0]["key"])


def _agent_model_ids(agents_dir: str) -> list[str]:
    if not os.path.isdir(agents_dir):
        raise SystemExit(f"Agents directory not found: {agents_dir}")
    paths = sorted(glob.glob(os.path.join(agents_dir, "*.yaml")))
    return [os.path.splitext(os.path.basename(p))[0] for p in paths]


def _build_models_block(
    *,
    base_url: str,
    api_key: str,
    provider_slug: str,
    model_ids: list[str],
    default_context: int,
    default_max_tokens: int,
) -> dict:
    models_meta = []
    for mid in model_ids:
        models_meta.append(
            {
                "id": mid,
                "name": f"MBMH {mid}",
                "reasoning": False,
                "input": ["text"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": default_context,
                "maxTokens": default_max_tokens,
            }
        )
    return {
        "mode": "merge",
        "providers": {
            provider_slug: {
                "baseUrl": base_url,
                "apiKey": api_key,
                "api": "openai-completions",
                "models": models_meta,
            }
        },
    }


def _check_http(base_url: str, api_key: str, expect_ids: list[str]) -> None:
    try:
        import httpx
    except ImportError:
        print("httpx not installed; skip --check or pip install httpx", file=sys.stderr)
        raise SystemExit(1)
    headers = {"Authorization": f"Bearer {api_key}"}
    url = base_url.rstrip("/") + "/models"
    r = httpx.get(url, headers=headers, timeout=10.0)
    r.raise_for_status()
    data = r.json()
    found = {m.get("id") for m in data.get("data", [])}
    missing = [x for x in expect_ids if x not in found]
    if missing:
        raise SystemExit(
            f"GET {url}: model ids missing from server: {missing}. Got: {sorted(found)}"
        )
    print(f"OK GET {url} -> {len(found)} models", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--runtime",
        default="configs/runtime/openai-compatible.yaml",
        help="Runtime YAML (host/port)",
    )
    parser.add_argument(
        "--api-keys",
        default="configs/auth/api_keys.yaml",
        help="api_keys.yaml (first key used unless --api-key)",
    )
    parser.add_argument(
        "--agents-dir",
        default="configs/agents",
        help="Directory of *.yaml agent configs (stems = OpenAI model ids)",
    )
    parser.add_argument("--host", default=None, help="Override host from runtime YAML")
    parser.add_argument("--port", type=int, default=None, help="Override port")
    parser.add_argument(
        "--provider-slug",
        default="mbmh-local",
        help="OpenClaw provider key under models.providers",
    )
    parser.add_argument(
        "--primary-model",
        default="openclaw-agent",
        help="Agent id for agents.defaults.model.primary (must exist under --agents-dir)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Bearer token for OpenClaw→MBMH (default: first key in --api-keys)",
    )
    parser.add_argument(
        "--context-window",
        type=int,
        default=32768,
        help=(
            "OpenClaw models.providers.*.models[].contextWindow "
            "(OpenClaw warns if <32000; Qwen2.5 is typically 32k+)"
        ),
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="OpenClaw model catalog maxTokens hint (completion budget OpenClaw may assume)",
    )
    parser.add_argument(
        "--models-only",
        action="store_true",
        help="Emit only the models.* object (safer merge)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="GET /v1/models against baseUrl before printing JSON",
    )
    parser.add_argument(
        "--list-agent-ids",
        action="store_true",
        help="Print agent ids (model names) and exit",
    )
    args = parser.parse_args()

    rt = _load_runtime(args.runtime)
    host = args.host or rt.get("host") or "127.0.0.1"
    port = args.port if args.port is not None else int(rt.get("port") or 8000)
    base_url = f"http://{host}:{port}/v1"

    model_ids = _agent_model_ids(args.agents_dir)
    if args.list_agent_ids:
        for m in model_ids:
            print(m)
        return

    if args.primary_model not in model_ids:
        raise SystemExit(
            f"--primary-model {args.primary_model!r} not in agents dir; "
            f"available: {model_ids}"
        )

    api_key = args.api_key or _first_api_key(args.api_keys)

    if args.check:
        _check_http(base_url, api_key, model_ids)

    models_block = _build_models_block(
        base_url=base_url,
        api_key=api_key,
        provider_slug=args.provider_slug,
        model_ids=model_ids,
        default_context=args.context_window,
        default_max_tokens=args.max_tokens,
    )

    if args.models_only:
        out = {"models": models_block}
    else:
        out = {
            "models": models_block,
            "agents": {
                "defaults": {
                    "model": {
                        "primary": f"{args.provider_slug}/{args.primary_model}",
                    }
                }
            },
        }

    print(json.dumps(out, indent=2))

    if not args.models_only:
        primary = f"{args.provider_slug}/{args.primary_model}"
        print(
            "\n# To set only the default model (keeps other agents.defaults.*):\n"
            f"#   openclaw config set agents.defaults.model.primary {json.dumps(primary)} --strict-json\n"
            "# Or merge the printed JSON in Control UI → Config → raw editor.\n",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
