"""Wiki proposal queue helpers for editorial governance."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from .contracts import (
    WikiEditKind,
    WikiEditProposalPayload,
    WikiEditProposalStatus,
)
from .validation import validate_wiki_edit_proposal_json

CAUTION_TEXT = "unapproved source, proceed with caution"
WIKI_SHARDS: dict[str, str] = {
    "modes": "response_mode_id",
    "pools": "knowledge_pool_id",
    "modules": "module_card_id",
    "techniques": "technique_card_id",
    "theory": "theory_card_id",
}


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "knowledge" / "wiki").exists():
            return parent
    raise RuntimeError("Could not locate repo root (knowledge/wiki missing)")


def queue_root() -> Path:
    root = _repo_root() / "knowledge" / "wiki" / "_proposals"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _split_front_matter(raw: str, path: Path) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        raise ValueError(f"{path}: proposal must start with front matter delimiter ---")
    rest = raw[3:].lstrip("\n")
    marker = "\n---\n"
    idx = rest.find(marker)
    if idx == -1:
        raise ValueError(f"{path}: proposal missing closing front matter delimiter")
    front = rest[:idx].strip()
    body = rest[idx + len(marker) :]
    parsed = json.loads(front)
    if not isinstance(parsed, dict):
        raise ValueError(f"{path}: front matter must be a JSON object")
    return parsed, body


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return cleaned.strip("_") or "proposal"


def proposal_path(proposal_id: str | UUID) -> Path:
    return queue_root() / f"{proposal_id}.md"


def write_proposal_file(payload: WikiEditProposalPayload) -> Path:
    path = proposal_path(payload.wiki_edit_proposal_id)
    front = json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True)
    content = f"---\n{front}\n---\n\n{payload.summary}\n"
    path.write_text(content, encoding="utf-8")
    return path


def load_proposal_file(path: Path) -> WikiEditProposalPayload:
    data, _body = _split_front_matter(path.read_text(encoding="utf-8"), path)
    return validate_wiki_edit_proposal_json(data)


def list_proposals(*, status: WikiEditProposalStatus | None = None) -> list[WikiEditProposalPayload]:
    proposals: list[WikiEditProposalPayload] = []
    for path in sorted(queue_root().glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        proposal = load_proposal_file(path)
        if status is not None and proposal.status is not status:
            continue
        proposals.append(proposal)
    return proposals


def create_proposal(
    *,
    target_ref: str,
    target_path: str,
    title: str,
    summary: str,
    proposed_content: str,
    rationale: str,
    provenance_refs: list[str],
    created_by: str,
    edit_kind: WikiEditKind = WikiEditKind.UPDATE,
    confidence: float = 0.5,
    proposed_patch: str | None = None,
) -> WikiEditProposalPayload:
    now = datetime.now(UTC)
    payload = WikiEditProposalPayload(
        wiki_edit_proposal_id=uuid4(),
        target_ref=target_ref,
        target_path=target_path,
        edit_kind=edit_kind,
        status=WikiEditProposalStatus.PROPOSED,
        title=title,
        summary=summary,
        proposed_content=proposed_content,
        proposed_patch=proposed_patch,
        rationale=rationale,
        provenance_refs=provenance_refs,
        confidence=confidence,
        unapproved_source=True,
        caution=CAUTION_TEXT,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    write_proposal_file(payload)
    return payload


def update_proposal_status(
    *,
    proposal_id: str,
    status: WikiEditProposalStatus,
    approver: str | None = None,
    approval_notes: str | None = None,
    promotion_ref: str | None = None,
) -> WikiEditProposalPayload:
    path = proposal_path(proposal_id)
    proposal = load_proposal_file(path)
    now = datetime.now(UTC)
    updated = proposal.model_copy(
        update={
            "status": status,
            "approved_by": approver or proposal.approved_by,
            "approval_notes": approval_notes if approval_notes is not None else proposal.approval_notes,
            "approved_at": now if status in {WikiEditProposalStatus.APPROVED, WikiEditProposalStatus.PROMOTED} else proposal.approved_at,
            "promoted_at": now if status is WikiEditProposalStatus.PROMOTED else proposal.promoted_at,
            "promotion_ref": promotion_ref if promotion_ref is not None else proposal.promotion_ref,
            "updated_at": now,
        }
    )
    write_proposal_file(updated)
    return updated


def _load_orchestration_cards() -> list[tuple[str, dict[str, Any], str]]:
    repo = _repo_root()
    cards: list[tuple[str, dict[str, Any], str]] = []
    for shard, id_field in WIKI_SHARDS.items():
        for path in sorted((repo / "knowledge" / "wiki" / "orchestration" / shard).glob("*.md")):
            front, body = _split_front_matter(path.read_text(encoding="utf-8"), path)
            if id_field not in front:
                continue
            cards.append((str(path), front, body.strip()))
    return cards


def _ref_for_card(front: dict[str, Any]) -> str | None:
    if "response_mode_id" in front:
        return f"artifact://response-mode/{front['response_mode_id']}"
    if "knowledge_pool_id" in front:
        return f"artifact://knowledge-pool/{front['knowledge_pool_id']}"
    if "module_card_id" in front:
        return f"artifact://module-card/{front['module_card_id']}"
    if "technique_card_id" in front:
        return f"artifact://technique-card/{front['technique_card_id']}"
    if "theory_card_id" in front:
        return f"artifact://theory-card/{front['theory_card_id']}"
    return None


def resolve_wiki_overlay_context(selected_refs: list[str]) -> str:
    refs = {str(ref).strip() for ref in selected_refs if str(ref).strip()}
    if not refs:
        return ""
    approved_chunks: list[str] = []
    for _path, front, body in _load_orchestration_cards():
        ref = _ref_for_card(front)
        if not ref or ref not in refs:
            continue
        title = str(front.get("label") or front.get("title") or ref)
        snippet = body or str(front.get("summary") or "")
        approved_chunks.append(f"- {title} ({ref})\n  {snippet}")

    proposal_chunks: list[str] = []
    for proposal in list_proposals(status=WikiEditProposalStatus.PROPOSED):
        if proposal.target_ref not in refs:
            continue
        proposal_chunks.append(

                f"- {proposal.title} ({proposal.target_ref})\n"
                f"  {CAUTION_TEXT.upper()}\n"
                f"  Summary: {proposal.summary}\n"
                f"  Proposed content: {proposal.proposed_content}"

        )

    if not approved_chunks and not proposal_chunks:
        return ""
    sections: list[str] = []
    if approved_chunks:
        sections.append("Approved wiki context:\n" + "\n".join(approved_chunks))
    if proposal_chunks:
        sections.append("Unapproved wiki overlays (proceed with caution):\n" + "\n".join(proposal_chunks))
    return "\n\n".join(sections)

