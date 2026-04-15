#!/usr/bin/env python3
"""Validate AI runtime dependency tracking policy.

The policy for Hugging Face, Ollama, and vLLM is locks plus inventory:
package managers track libraries, OCI digests track runtime images, and source
submodules are only allowed when upstream source is directly imported/patched.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "ai-runtime-dependencies.md"

PINNED_IMAGES = {
    "ollama/ollama": re.compile(r"ollama/ollama@sha256:[0-9a-f]{64}"),
    "vllm/vllm-openai": re.compile(r"vllm/vllm-openai@sha256:[0-9a-f]{64}"),
}

IMAGE_POLICY_FILES = [
    ROOT / ".env.example",
    ROOT / "services" / "ai-gateway-service" / "env.example",
    ROOT / "docker" / "compose-profiles" / "docker-compose.worker.yml",
    ROOT / "worker" / "vllm" / "docker-compose.vllm.yml",
    ROOT / "services" / "ai-gateway-service" / "compose" / "docker-compose.base.yml",
    ROOT / "services" / "ai-gateway-service" / "compose" / "docker-compose.prod.yml",
]

HF_RUNTIME_REQUIREMENTS = {
    "services/model-runtime/pyproject.toml": ["torch", "transformers", "accelerate"],
    "uv.lock": ["name = \"torch\"", "name = \"transformers\"", "name = \"accelerate\""],
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"AI runtime dependency check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_inventory() -> None:
    if not INVENTORY.exists():
        fail("missing docs/ai-runtime-dependencies.md")
    text = read(INVENTORY)
    for image, pattern in PINNED_IMAGES.items():
        if not pattern.search(text):
            fail(f"inventory missing pinned digest for {image}")
    for phrase in [
        "Hugging Face and Ollama upstream source repositories are not submodules",
        "Git submodules are used only when this repo imports, patches, or vendors",
    ]:
        if phrase not in text:
            fail(f"inventory missing policy phrase: {phrase}")


def check_images() -> None:
    for path in IMAGE_POLICY_FILES:
        if not path.exists():
            fail(f"expected image policy file missing: {path.relative_to(ROOT)}")
        text = read(path)
        for image, pattern in PINNED_IMAGES.items():
            if image in text and not pattern.search(text):
                fail(f"{path.relative_to(ROOT)} references {image} without a sha256 digest")
            if f"{image}:latest" in text:
                fail(f"{path.relative_to(ROOT)} references forbidden {image}:latest")


def check_package_locks() -> None:
    for rel, needles in HF_RUNTIME_REQUIREMENTS.items():
        path = ROOT / rel
        if not path.exists():
            fail(f"missing package tracking file: {rel}")
        text = read(path)
        for needle in needles:
            if needle not in text:
                fail(f"{rel} missing tracked dependency marker: {needle}")
    if not (ROOT / "package-lock.json").exists():
        fail("missing package-lock.json for Node workspace dependencies")


def check_source_submodules() -> None:
    gitmodules = ROOT / ".gitmodules"
    if not gitmodules.exists():
        fail("missing .gitmodules for external source inventory")
    text = read(gitmodules).lower()
    for forbidden in ["huggingface", "ollama"]:
        if forbidden in text:
            fail(
                f".gitmodules contains {forbidden}; document repo, branch/tag, commit, "
                "license, update command, and source import reason before adding it"
            )


def main() -> int:
    check_inventory()
    check_images()
    check_package_locks()
    check_source_submodules()
    print("AI runtime dependency tracking check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
