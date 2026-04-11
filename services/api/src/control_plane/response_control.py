"""Three-choice / five-layer response-control evaluation.

The control plane owns the independent choices:
mode (x), knowledge pool (y), and module (z). Technique (z1) is derived from
selected modules, and theory (y1) is derived from selected pools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .contracts import (
    KnowledgePoolPayload,
    ModeDissonance,
    ModeSelection,
    ModuleCardPayload,
    ModuleKind,
    ModuleSelection,
    ResponseControlAssessment,
    ResponseModeKey,
    ResponseModePayload,
    TechniqueCardPayload,
    TechniqueSelection,
    TheoryCardPayload,
    KnowledgePoolSelection,
)

ASSEMBLY_ORDER = ["mode", "knowledge_pool", "module", "technique", "theory"]

_MODE_ALIASES = {
    "strict": ResponseModeKey.ENGINEERING,
    "strict_engineering": ResponseModeKey.ENGINEERING,
    "engineering_task": ResponseModeKey.ENGINEERING,
    "definition": ResponseModeKey.DICTIONARY_DEFINITION,
    "dictionary": ResponseModeKey.DICTIONARY_DEFINITION,
    "dictionary/definition": ResponseModeKey.DICTIONARY_DEFINITION,
    "direct_query": ResponseModeKey.QUERY,
    "qa": ResponseModeKey.QUERY,
}

_ENGINEERING_POOL_KEYS = {
    "mechanical_engineering",
    "manufacturing",
    "computational_engineering",
    "chemistry_chemical_modeling",
    "standards_data",
}


@dataclass(frozen=True)
class ResponseControlCatalog:
    modes: dict[str, ResponseModePayload]
    pools: dict[str, KnowledgePoolPayload]
    modules: dict[str, ModuleCardPayload]
    techniques: dict[str, TechniqueCardPayload]
    theory: dict[str, TheoryCardPayload]

    @classmethod
    def load(cls, root: Path | None = None) -> ResponseControlCatalog:
        base = root or _catalog_root()
        return cls(
            modes={
                item.response_mode_id: item
                for item in _load_cards(base / "modes.json", ResponseModePayload)
            },
            pools={
                item.knowledge_pool_id: item
                for item in _load_cards(base / "knowledge-pools.json", KnowledgePoolPayload)
            },
            modules={
                item.module_card_id: item
                for item in _load_cards(base / "modules.json", ModuleCardPayload)
            },
            techniques={
                item.technique_card_id: item
                for item in _load_cards(base / "techniques.json", TechniqueCardPayload)
            },
            theory={
                item.theory_card_id: item
                for item in _load_cards(base / "theory.json", TheoryCardPayload)
            },
        )


_CATALOG_CACHE: tuple[str, ResponseControlCatalog] | None = None


def reset_response_control_catalog_cache_for_tests() -> None:
    global _CATALOG_CACHE  # noqa: PLW0603 - intentional process-local cache
    _CATALOG_CACHE = None


def response_control_artifact_ref(assessment: ResponseControlAssessment | dict[str, Any]) -> str:
    identifier = (
        assessment.response_control_assessment_id
        if isinstance(assessment, ResponseControlAssessment)
        else assessment["response_control_assessment_id"]
    )
    return f"artifact://response-control-assessment/{identifier}"


def selected_response_control_refs(
    assessment: ResponseControlAssessment | dict[str, Any],
) -> dict[str, Any]:
    payload = (
        assessment.model_dump(mode="json")
        if isinstance(assessment, ResponseControlAssessment)
        else assessment
    )
    pool_selection = payload.get("knowledge_pool_selection") or {}
    module_selection = payload.get("module_selection") or {}
    technique_selection = payload.get("technique_selection") or {}
    return {
        "response_control_ref": response_control_artifact_ref(payload),
        "selected_knowledge_pool_refs": list(pool_selection.get("selected_pool_refs") or []),
        "selected_module_refs": list(module_selection.get("selected_module_refs") or []),
        "selected_technique_refs": list(technique_selection.get("selected_technique_refs") or []),
        "selected_theory_refs": list(pool_selection.get("selected_theory_refs") or []),
    }


def evaluate_response_control(
    *,
    prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    requested_mode: str | None = None,
    active_mode: str | None = None,
    minimum_mode: str | None = None,
    catalog: ResponseControlCatalog | None = None,
) -> ResponseControlAssessment:
    """Evaluate the independent response-control choices for the current prompt."""

    ctx = context or {}
    text = (prompt or _latest_user_content(messages)).strip()
    lower = text.lower()
    loaded = catalog or load_response_control_catalog()
    selected_mode, mode_confidence, mode_reason = _infer_mode(lower)
    explicit_mode = _normalize_response_mode(
        requested_mode
        or ctx.get("response_mode")
        or ctx.get("engagement_mode")
        or ("engineering" if ctx.get("strict_engineering") is True else None)
    )
    session_mode = _normalize_response_mode(
        active_mode
        or ctx.get("active_response_mode")
        or ctx.get("active_engagement_mode")
        or ctx.get("session_engagement_mode")
    )
    minimum = _normalize_response_mode(minimum_mode or ctx.get("minimum_response_mode"))
    mode_reasons = [mode_reason]
    user_override = explicit_mode is not None
    if explicit_mode is not None:
        if explicit_mode != selected_mode:
            mode_dissonance = ModeDissonance(
                inferred_mode=selected_mode,
                suggested_mode=selected_mode,
                reason=(
                    f"Prompt evidence suggests {selected_mode.value}, but explicit "
                    f"mode {explicit_mode.value} remains authoritative."
                ),
            )
        else:
            mode_dissonance = None
        selected_mode = explicit_mode
        mode_confidence = 1.0
        mode_reasons.append(f"explicit_response_mode:{selected_mode.value}")
    else:
        mode_dissonance = None
        selected_mode = session_mode or minimum or selected_mode
        if session_mode is not None:
            mode_reasons.append(f"session_response_mode:{session_mode.value}")
        if minimum is not None:
            mode_reasons.append(f"minimum_response_mode:{minimum.value}")

    selected_pools, pool_reasons = _select_pools(
        lower=lower,
        selected_mode=selected_mode,
        catalog=loaded,
        context=ctx,
    )
    selected_theory_refs = _theory_refs_for_pools(selected_pools)
    selected_modules, module_reasons = _select_modules(
        lower=lower,
        selected_pools=selected_pools,
        catalog=loaded,
        context=ctx,
    )
    selected_technique_refs = _technique_refs_for_modules(selected_modules)
    selected_pool_refs = [_pool_ref(pool.knowledge_pool_id) for pool in selected_pools]
    selected_module_refs = [_module_ref(module.module_card_id) for module in selected_modules]
    selected_module_refs_by_kind = {
        ModuleKind.TOOL: [
            _module_ref(module.module_card_id)
            for module in selected_modules
            if module.module_kind is ModuleKind.TOOL
        ],
        ModuleKind.PACKAGE: [
            _module_ref(module.module_card_id)
            for module in selected_modules
            if module.module_kind is ModuleKind.PACKAGE
        ],
        ModuleKind.KNOWLEDGE_BANK: [
            _module_ref(module.module_card_id)
            for module in selected_modules
            if module.module_kind is ModuleKind.KNOWLEDGE_BANK
        ],
    }
    assessment_id = uuid5(
        NAMESPACE_URL,
        "response-control-assessment:"
        + json.dumps(
            {
                "text": text,
                "mode": selected_mode.value,
                "pools": selected_pool_refs,
                "modules": selected_module_refs,
                "techniques": selected_technique_refs,
                "theory": selected_theory_refs,
            },
            sort_keys=True,
        ),
    )
    return ResponseControlAssessment(
        response_control_assessment_id=assessment_id,
        schema_version="1.0.0",
        mode_selection=ModeSelection(
            selected_mode=selected_mode,
            user_override=user_override,
            confidence=round(min(mode_confidence, 1.0), 3),
            reasons=list(dict.fromkeys(mode_reasons)),
            mode_dissonance=mode_dissonance,
        ),
        knowledge_pool_selection=KnowledgePoolSelection(
            selected_pool_refs=selected_pool_refs,
            selected_theory_refs=selected_theory_refs,
            reasons=pool_reasons,
        ),
        module_selection=ModuleSelection(
            selected_module_refs_by_kind=selected_module_refs_by_kind,
            selected_module_refs=selected_module_refs,
            reasons=module_reasons,
        ),
        technique_selection=TechniqueSelection(
            selected_technique_refs=selected_technique_refs,
            derived_from_module_refs=selected_module_refs,
        ),
        assembly_order=list(ASSEMBLY_ORDER),
        created_at=datetime.now(UTC),
    )


def load_response_control_catalog(root: Path | None = None) -> ResponseControlCatalog:
    global _CATALOG_CACHE  # noqa: PLW0603 - intentional process-local cache
    base = root or _catalog_root()
    fingerprint = _catalog_fingerprint(base)
    if _CATALOG_CACHE and _CATALOG_CACHE[0] == fingerprint:
        return _CATALOG_CACHE[1]
    catalog = ResponseControlCatalog.load(base)
    _CATALOG_CACHE = (fingerprint, catalog)
    return catalog


def _catalog_root() -> Path:
    here = Path(__file__).resolve()
    for path in [here, *here.parents]:
        candidate = path / "knowledge" / "response-control"
        if candidate.exists():
            return candidate
    raise RuntimeError("Could not locate knowledge/response-control")


def _catalog_fingerprint(root: Path) -> str:
    parts: list[str] = []
    for path in sorted(root.glob("*.json")):
        stat = path.stat()
        parts.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)


def _load_cards(path: Path, model: type[Any]) -> list[Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [model.model_validate(item) for item in payload]


def _latest_user_content(messages: list[dict[str, Any]] | None) -> str:
    if not messages:
        return ""
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return str(messages[-1].get("content") or "")


def _normalize_response_mode(value: Any) -> ResponseModeKey | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace("/", "_")
    if normalized in _MODE_ALIASES:
        return _MODE_ALIASES[normalized]
    try:
        return ResponseModeKey(normalized)
    except ValueError:
        return None


def _infer_mode(lower: str) -> tuple[ResponseModeKey, float, str]:
    keyword_groups: list[tuple[ResponseModeKey, float, tuple[str, ...], str]] = [
        (
            ResponseModeKey.ENGINEERING,
            0.86,
            (
                "implement",
                "refactor",
                "codebase",
                "repo",
                "engineering",
                "simulation",
                "solver",
                "verification",
                "manufacturing",
                "mechanical",
            ),
            "mode_keyword:engineering",
        ),
        (
            ResponseModeKey.RESEARCH,
            0.82,
            ("research", "literature", "source", "citation", "paper", "evidence"),
            "mode_keyword:research",
        ),
        (
            ResponseModeKey.CONTENT,
            0.78,
            ("video", "script", "podcast", "caption", "social post", "content"),
            "mode_keyword:content",
        ),
        (
            ResponseModeKey.MARKETING,
            0.78,
            ("marketing", "campaign", "brand", "copy", "advertis", "positioning"),
            "mode_keyword:marketing",
        ),
        (
            ResponseModeKey.BUSINESS,
            0.76,
            ("business", "market", "pricing", "revenue", "operations", "strategy"),
            "mode_keyword:business",
        ),
        (
            ResponseModeKey.DICTIONARY_DEFINITION,
            0.74,
            ("define", "definition", "meaning of", "what does", "what is"),
            "mode_keyword:dictionary_definition",
        ),
        (
            ResponseModeKey.NAPKIN_MATH,
            0.72,
            ("estimate", "calculate", "rough", "equation", "back of envelope"),
            "mode_keyword:napkin_math",
        ),
        (
            ResponseModeKey.IDEATION,
            0.68,
            ("brainstorm", "ideas", "concept", "explore", "what if"),
            "mode_keyword:ideation",
        ),
    ]
    for mode, confidence, keywords, reason in keyword_groups:
        if any(keyword in lower for keyword in keywords):
            return mode, confidence, reason
    return ResponseModeKey.QUERY, 0.45, "default:query"


def _select_pools(
    *,
    lower: str,
    selected_mode: ResponseModeKey,
    catalog: ResponseControlCatalog,
    context: dict[str, Any],
) -> tuple[list[KnowledgePoolPayload], list[str]]:
    explicit_pool_refs = context.get("selected_knowledge_pool_refs")
    if isinstance(explicit_pool_refs, list) and explicit_pool_refs:
        selected = [
            pool
            for pool in catalog.pools.values()
            if _pool_ref(pool.knowledge_pool_id) in explicit_pool_refs
            or pool.knowledge_pool_id in explicit_pool_refs
        ]
        if selected:
            return selected, ["explicit:selected_knowledge_pool_refs"]

    scored: list[tuple[int, KnowledgePoolPayload, list[str]]] = []
    for pool in catalog.pools.values():
        matched = [keyword for keyword in pool.keywords if keyword.lower() in lower]
        pool_reasons = [f"pool_keyword:{pool.pool_key}:{keyword}" for keyword in matched]
        score = len(matched)
        if selected_mode is ResponseModeKey.ENGINEERING and pool.pool_key in _ENGINEERING_POOL_KEYS:
            score += 1
            pool_reasons.append(f"mode_default:engineering:{pool.pool_key}")
        if score > 0:
            scored.append((score, pool, pool_reasons))
    scored.sort(key=lambda item: (-item[0], item[1].pool_key))
    selected = [pool for _score, pool, _reasons in scored[:4]]
    reasons = [reason for _score, _pool, pool_reasons in scored[:4] for reason in pool_reasons]
    if selected_mode is ResponseModeKey.ENGINEERING and not selected:
        selected = [
            catalog.pools[key]
            for key in ("computational_engineering", "standards_data")
            if key in catalog.pools
        ]
        reasons = ["mode_default:engineering_core_pools"]
    return selected, reasons or ["pool_selection:no_pool_required"]


def _select_modules(
    *,
    lower: str,
    selected_pools: list[KnowledgePoolPayload],
    catalog: ResponseControlCatalog,
    context: dict[str, Any],
) -> tuple[list[ModuleCardPayload], list[str]]:
    explicit_module_refs = context.get("selected_module_refs")
    if isinstance(explicit_module_refs, list) and explicit_module_refs:
        selected = [
            module
            for module in catalog.modules.values()
            if _module_ref(module.module_card_id) in explicit_module_refs
            or module.module_card_id in explicit_module_refs
        ]
        if selected:
            return selected, ["explicit:selected_module_refs"]

    selected_pool_refs = {_pool_ref(pool.knowledge_pool_id) for pool in selected_pools}
    scored: list[tuple[int, ModuleCardPayload, list[str]]] = []
    for module in catalog.modules.values():
        matched = [keyword for keyword in module.keywords if keyword.lower() in lower]
        pool_fit = bool(selected_pool_refs.intersection(module.pool_refs))
        score = len(matched) * 2 + (1 if pool_fit else 0)
        if module.module_card_id == "engineering_orchestration_stack" and (
            "orchestrat" in lower or "devplane" in lower or "claw" in lower
        ):
            score += 4
        if score > 0:
            reasons = [f"module_keyword:{module.module_key}:{keyword}" for keyword in matched]
            if pool_fit:
                reasons.append(f"module_pool_fit:{module.module_key}")
            scored.append((score, module, reasons))
    scored.sort(key=lambda item: (-item[0], item[1].module_key))
    selected = [module for _score, module, _reasons in scored[:6]]
    reasons = [reason for _score, _module, module_reasons in scored[:6] for reason in module_reasons]
    if selected_pools and not selected:
        selected_ref_set = {
            ref
            for pool in selected_pools
            for ref in pool.module_refs[:2]
        }
        selected = [
            module
            for module in catalog.modules.values()
            if _module_ref(module.module_card_id) in selected_ref_set
        ]
        reasons = ["pool_default:first_ranked_pool_modules"]
    return selected, reasons or ["module_selection:no_module_required"]


def _theory_refs_for_pools(pools: list[KnowledgePoolPayload]) -> list[str]:
    return list(dict.fromkeys(ref for pool in pools for ref in pool.theory_refs))


def _technique_refs_for_modules(modules: list[ModuleCardPayload]) -> list[str]:
    return list(dict.fromkeys(ref for module in modules for ref in module.technique_refs))


def _pool_ref(pool_id: str) -> str:
    return f"artifact://knowledge-pool/{pool_id}"


def _module_ref(module_id: str) -> str:
    return f"artifact://module-card/{module_id}"
