"""Resolve repository paths when the server workspace vendors AI packages under ``./xlotyl``."""

from __future__ import annotations

from pathlib import Path


def server_repo_root() -> Path:
    """Return the platform ``server`` repository root (parent of ``services/api-service``)."""
    return Path(__file__).resolve().parent.parent.parent


def xlotyl_root() -> Path | None:
    """Return ``server/xlotyl`` when present, else ``None``."""
    candidate = server_repo_root() / "xlotyl"
    if candidate.is_dir() and (candidate / "services" / "response-control-framework").is_dir():
        return candidate.resolve()
    return None


def openclaw_stream_event_schema_path() -> Path:
    """Locate ``stream-event.schema.json`` (under server or xlotyl)."""
    rel = Path("schemas") / "openclaw-bridge" / "v1" / "events" / "stream-event.schema.json"
    for base in (server_repo_root(), xlotyl_root()):
        if base is None:
            continue
        path = base / rel
        if path.is_file():
            return path
    raise FileNotFoundError(
        "OpenClaw stream-event schema not found; expected under server or xlotyl at "
        f"{rel.as_posix()}"
    )


def openclaw_event_fixtures_dir() -> Path:
    """Directory of golden stream-event JSON fixtures."""
    rel = Path("schemas") / "openclaw-bridge" / "v1" / "events" / "fixtures"
    for base in (server_repo_root(), xlotyl_root()):
        if base is None:
            continue
        path = base / rel
        if path.is_dir():
            return path
    raise FileNotFoundError(
        "OpenClaw event fixtures directory not found; expected under server or xlotyl at "
        f"{rel.as_posix()}"
    )


def engineering_coding_tools_root() -> Path:
    """Return the on-disk engineering knowledge pool (matches ``resolve_engineering_knowledge_pool_root`` order)."""
    rel = (
        Path("services")
        / "domain-engineering"
        / "src"
        / "domain_engineering"
        / "data"
        / "coding-tools"
    )
    repo = server_repo_root()
    candidates: list[Path] = []
    xroot = xlotyl_root()
    if xroot is not None:
        candidates.append(xroot / rel)
    candidates.extend([repo / rel, repo / "knowledge" / "coding-tools"])
    for root in candidates:
        if (root / "substrate" / "knowledge-packs.json").is_file():
            return root.resolve()
    raise FileNotFoundError(
        "Engineering coding-tools tree not found (expected substrate/knowledge-packs.json); "
        f"tried under xlotyl and server at {rel.as_posix()}"
    )
