import asyncio
import hashlib
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

api = FastAPI(
    title="AI Stack Surrogate API",
    description="Deterministic, profile-driven API surrogates for offline mobile validation.",
    version="1.0.0",
)


ROLE = os.getenv("SURROGATE_ROLE", "orchestrator")
DEFAULT_PROFILE = os.getenv("SURROGATE_PROFILE", "nominal").lower()
SEED = os.getenv("SURROGATE_SEED", "mobile-offline-seed")
BASE_LATENCY_MS = int(os.getenv("SURROGATE_BASE_LATENCY_MS", "40"))
LATENCY_JITTER_MS = int(os.getenv("SURROGATE_LATENCY_JITTER_MS", "30"))

SUPPORTED_ROLES = {
    "orchestrator",
    "rag",
    "asr",
    "mcp",
    "tool-registry",
    "gateway",
}
SUPPORTED_PROFILES = {
    "nominal",
    "degraded",
    "flaky",
    "rate-limited",
    "auth-error",
    "outage",
}

if ROLE not in SUPPORTED_ROLES:
    raise RuntimeError(
        f"Unsupported SURROGATE_ROLE='{ROLE}'. Expected one of {sorted(SUPPORTED_ROLES)}."
    )
if DEFAULT_PROFILE not in SUPPORTED_PROFILES:
    raise RuntimeError(
        f"Unsupported SURROGATE_PROFILE='{DEFAULT_PROFILE}'. Expected one of {sorted(SUPPORTED_PROFILES)}."
    )


REQUEST_COUNTS: Dict[str, int] = defaultdict(int)
CHAT_TURNS: Dict[str, int] = defaultdict(int)


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = "default"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000


class SearchRequest(BaseModel):
    query: str
    domain_weights: Dict[str, float] = {}
    k: int = 5
    threshold: float = 0.7
    use_bm25_reranking: bool = True
    bm25_weight: float = 0.3
    embedding_weight: float = 0.7


class DomainQuery(BaseModel):
    query: str
    context: Dict[str, Any] = {}
    limit: int = 10


class TranscriptionRequest(BaseModel):
    audio_url: Optional[str] = None
    audio_data: Optional[str] = None
    language: Optional[str] = "en"
    extract_technical: bool = True


class MolecularWeightRequest(BaseModel):
    formula: str


class PHCalculationRequest(BaseModel):
    calculation_type: str
    value: float
    ion_type: str = "H+"


class BeamCalculationRequest(BaseModel):
    beam_type: str
    length: float
    load: float
    load_type: str = "point_center"
    moment_of_inertia: float = 8.33e-6
    elastic_modulus: float = 200e9
    material_yield_strength: Optional[float] = None


class MaterialPropertyRequest(BaseModel):
    material: str
    properties: List[str] = ["density", "elastic_modulus", "yield_strength"]
    temperature: float = 293.15


class MolecularPropertyRequest(BaseModel):
    smiles: Optional[str] = None
    name: Optional[str] = None
    formula: Optional[str] = None


class ToolExecutionRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}


RAG_CORPUS = [
    {
        "id": "doc-chem-001",
        "domain": "chemistry",
        "source": "chemistry_handbook_v2.pdf",
        "content": "Hydrochloric acid at 0.1M has pH approximately 1.0 and is a strong acid.",
    },
    {
        "id": "doc-mech-001",
        "domain": "mechanical",
        "source": "mechanical_design_guide.md",
        "content": "Stress is calculated as sigma = force / area, with SI unit pascal (Pa).",
    },
    {
        "id": "doc-mat-001",
        "domain": "materials",
        "source": "materials_reference.csv",
        "content": "Typical structural steel yield strength is around 250 MPa.",
    },
    {
        "id": "doc-mech-002",
        "domain": "mechanical",
        "source": "beam_theory_notes.txt",
        "content": "For simply supported beam with center load, max deflection is PL^3/(48EI).",
    },
    {
        "id": "doc-chem-002",
        "domain": "chemistry",
        "source": "reaction_safety.md",
        "content": "Always assess corrosive and exothermic risks when handling concentrated acids.",
    },
    {
        "id": "doc-mat-002",
        "domain": "materials",
        "source": "alloy_selector.md",
        "content": "Aluminum 6061 has lower density than steel but lower tensile strength.",
    },
]

TOOLS = [
    {
        "name": "calculator",
        "description": "Evaluate engineering expressions.",
        "type": "python",
        "category": "general",
    },
    {
        "name": "unit_converter",
        "description": "Convert SI and engineering units.",
        "type": "yaml",
        "category": "engineering",
    },
    {
        "name": "material_lookup",
        "description": "Lookup material properties.",
        "type": "python",
        "category": "materials",
    },
    {
        "name": "beam_solver",
        "description": "Beam stress and deflection helper.",
        "type": "python",
        "category": "mechanical",
    },
]

TECHNICAL_KEYWORDS = {
    "mechanical": ["stress", "strain", "beam", "deflection", "torque", "yield"],
    "chemistry": ["molar", "pH", "reaction", "acid", "base", "concentration"],
    "materials": ["alloy", "hardness", "ductility", "elastic", "tensile", "grain"],
}

ATOMIC_WEIGHTS = {
    "H": 1.008,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "Na": 22.99,
    "Cl": 35.45,
    "S": 32.06,
    "P": 30.974,
    "K": 39.098,
    "Ca": 40.078,
    "Fe": 55.845,
    "Al": 26.982,
    "Si": 28.085,
    "Mg": 24.305,
}

MATERIAL_DB = {
    "steel": {
        "density": 7850,
        "elastic_modulus": 200e9,
        "yield_strength": 250e6,
        "ultimate_strength": 460e6,
    },
    "aluminum": {
        "density": 2700,
        "elastic_modulus": 69e9,
        "yield_strength": 95e6,
        "ultimate_strength": 310e6,
    },
    "titanium": {
        "density": 4500,
        "elastic_modulus": 116e9,
        "yield_strength": 880e6,
        "ultimate_strength": 950e6,
    },
}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _h(*parts: Any) -> int:
    base = "|".join([SEED] + [str(p) for p in parts])
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _get_profile(header_profile: Optional[str]) -> str:
    profile = (header_profile or DEFAULT_PROFILE).strip().lower()
    if profile not in SUPPORTED_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported surrogate profile '{profile}'. Expected one of {sorted(SUPPORTED_PROFILES)}.",
        )
    return profile


def _domain_weights(text: str) -> Dict[str, float]:
    text_lower = text.lower()
    result = {"chemistry": 0.0, "mechanical": 0.0, "materials": 0.0}
    for domain, keywords in TECHNICAL_KEYWORDS.items():
        matches = sum(1 for k in keywords if k in text_lower)
        result[domain] = min(1.0, matches * 0.25)
    return result


def _extract_user_message(messages: List[Dict[str, str]]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user":
            return item.get("content", "")
    return ""


def _approx_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _score_doc(
    query: str, doc: Dict[str, str], domain_weights: Dict[str, float]
) -> float:
    query_tokens = set(re.findall(r"[a-z0-9_]+", query.lower()))
    doc_tokens = set(re.findall(r"[a-z0-9_]+", doc["content"].lower()))
    overlap = len(query_tokens.intersection(doc_tokens))
    domain_boost = domain_weights.get(doc["domain"], 0.0) * 0.3
    return 0.15 + (overlap * 0.09) + domain_boost


async def _apply_profile(
    endpoint_key: str,
    profile: str,
    payload_key: str,
    forced_fault: Optional[str],
    forced_latency_ms: Optional[int],
) -> Dict[str, Any]:
    REQUEST_COUNTS[endpoint_key] += 1
    request_no = REQUEST_COUNTS[endpoint_key]

    jitter = _h(endpoint_key, payload_key, request_no) % (LATENCY_JITTER_MS + 1)
    profile_multiplier = {
        "nominal": 1.0,
        "degraded": 2.5,
        "flaky": 1.7,
        "rate-limited": 1.0,
        "auth-error": 1.0,
        "outage": 1.0,
    }[profile]
    latency_ms = int((BASE_LATENCY_MS + jitter) * profile_multiplier)
    if forced_latency_ms is not None:
        latency_ms = max(0, forced_latency_ms)

    if latency_ms > 0:
        await asyncio.sleep(latency_ms / 1000.0)

    if forced_fault:
        normalized = forced_fault.strip().lower()
        if normalized in {"429", "rate_limit", "rate-limited"}:
            raise HTTPException(status_code=429, detail="Surrogate forced rate limit")
        if normalized in {"401", "auth"}:
            raise HTTPException(status_code=401, detail="Surrogate forced auth failure")
        if normalized in {"500", "internal"}:
            raise HTTPException(
                status_code=500, detail="Surrogate forced internal failure"
            )
        if normalized in {"503", "outage"}:
            raise HTTPException(status_code=503, detail="Surrogate forced outage")
        if normalized in {"timeout", "504"}:
            raise HTTPException(status_code=504, detail="Surrogate forced timeout")

    if profile == "outage":
        raise HTTPException(status_code=503, detail="Surrogate profile outage")
    if profile == "auth-error" and endpoint_key in {
        "orchestrator.chat",
        "gateway.chat_completions",
    }:
        raise HTTPException(status_code=401, detail="Surrogate profile auth-error")
    if profile == "rate-limited" and request_no % 4 == 0:
        raise HTTPException(status_code=429, detail="Surrogate profile rate-limited")
    if profile == "flaky" and (_h(endpoint_key, payload_key, request_no) % 6 == 0):
        raise HTTPException(status_code=503, detail="Surrogate profile flaky failure")

    return {
        "profile": profile,
        "request_no": request_no,
        "latency_ms": latency_ms,
    }


@api.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": _now(),
        "role": ROLE,
        "default_profile": DEFAULT_PROFILE,
        "supported_profiles": sorted(SUPPORTED_PROFILES),
        "request_counts": dict(REQUEST_COUNTS),
        "workflow_ready": ROLE == "orchestrator",
        "tools_loaded": len(TOOLS),
        "model_loaded": True,
    }


@api.post("/v1/chat/completions")
async def gateway_chat_completions(
    request: ChatRequest,
    x_surrogate_profile: Optional[str] = Header(default=None),
    x_surrogate_fault: Optional[str] = Header(default=None),
    x_surrogate_latency_ms: Optional[int] = Header(default=None),
):
    profile = _get_profile(x_surrogate_profile)
    user_message = _extract_user_message(request.messages)
    profile_meta = await _apply_profile(
        endpoint_key="gateway.chat_completions",
        profile=profile,
        payload_key=user_message,
        forced_fault=x_surrogate_fault,
        forced_latency_ms=x_surrogate_latency_ms,
    )
    weights = _domain_weights(user_message)
    response_content = (
        "Gateway surrogate response.\n"
        f"Detected domains: chemistry={weights['chemistry']:.2f}, "
        f"mechanical={weights['mechanical']:.2f}, materials={weights['materials']:.2f}.\n"
        "This payload is deterministic and profile-aware."
    )
    prompt_tokens = _approx_token_count(user_message)
    completion_tokens = _approx_token_count(response_content)
    return {
        "id": f"chatcmpl-{_h(user_message, request.model) % 10**10}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model or "surrogate-gateway",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "surrogate": profile_meta,
    }


@api.post("/chat")
async def orchestrator_chat(
    request: ChatRequest,
    x_surrogate_profile: Optional[str] = Header(default=None),
    x_surrogate_fault: Optional[str] = Header(default=None),
    x_surrogate_latency_ms: Optional[int] = Header(default=None),
):
    profile = _get_profile(x_surrogate_profile)
    user_message = _extract_user_message(request.messages)
    session_key = str(_h(request.model or "default", user_message) % 10000)
    CHAT_TURNS[session_key] += 1
    profile_meta = await _apply_profile(
        endpoint_key="orchestrator.chat",
        profile=profile,
        payload_key=user_message,
        forced_fault=x_surrogate_fault,
        forced_latency_ms=x_surrogate_latency_ms,
    )
    weights = _domain_weights(user_message)
    selected_docs = sorted(
        RAG_CORPUS,
        key=lambda d: _score_doc(user_message, d, weights),
        reverse=True,
    )[:2]
    evidence = " | ".join([f"{d['id']}:{d['source']}" for d in selected_docs])
    response_content = (
        "Surrogate orchestration completed.\n"
        f"Turn={CHAT_TURNS[session_key]}; profile={profile}.\n"
        f"Evidence={evidence}.\n"
        "Result quality gate: pass; relevance gate: pass; structure gate: pass."
    )
    prompt_tokens = _approx_token_count(user_message)
    completion_tokens = _approx_token_count(response_content)
    return {
        "id": f"chatcmpl-{_h('orchestrator', user_message) % 10**10}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model or "surrogate-orchestrator",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "surrogate": {**profile_meta, "tools_used": ["rag_search", "mcp_lookup"]},
    }


@api.get("/workflow/status")
async def workflow_status():
    return {
        "status": "active",
        "available_tools": len(TOOLS),
        "workflow_nodes": ["analyze", "gather_context", "generate_response"],
    }


@api.get("/llm/info")
async def llm_info():
    return {
        "backend_info": {
            "type": "mock",
            "base_url": "surrogate://llm",
            "timeout": 1,
            "name": "SurrogateLLM",
        },
        "health": {"backend": "mock", "healthy": True, "response_time": 0.001},
        "available_models": ["surrogate-llm-v1"],
    }


@api.post("/llm/test")
async def llm_test():
    return {
        "success": True,
        "backend": "mock",
        "test_response": "LLM test successful (surrogate).",
    }


@api.post("/search")
async def rag_search(
    request: SearchRequest,
    x_surrogate_profile: Optional[str] = Header(default=None),
    x_surrogate_fault: Optional[str] = Header(default=None),
    x_surrogate_latency_ms: Optional[int] = Header(default=None),
):
    profile = _get_profile(x_surrogate_profile)
    profile_meta = await _apply_profile(
        endpoint_key="rag.search",
        profile=profile,
        payload_key=request.query,
        forced_fault=x_surrogate_fault,
        forced_latency_ms=x_surrogate_latency_ms,
    )
    weights = request.domain_weights or _domain_weights(request.query)
    scored = []
    for doc in RAG_CORPUS:
        score = _score_doc(request.query, doc, weights)
        if profile == "degraded":
            score *= 0.9
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_k = max(1, min(request.k, 10))
    selected = scored[:top_k]
    results = []
    for score, doc in selected:
        results.append(
            {
                "id": doc["id"],
                "content": doc["content"],
                "domain": doc["domain"],
                "source": doc["source"],
                "score": round(score, 4),
                "citation": {
                    "source": doc["source"],
                    "document_id": doc["id"],
                    "retrieved_at": _now(),
                },
            }
        )
    evidence = " ".join([r["content"] for r in results[: min(3, len(results))]])
    return {
        "query": request.query,
        "results": results,
        "evidence": evidence,
        "search_time": round(profile_meta["latency_ms"] / 1000.0, 4),
        "reranking_method": (
            "hybrid_bm25_embedding" if request.use_bm25_reranking else "embedding_only"
        ),
        "surrogate": profile_meta,
    }


@api.post("/documents")
async def rag_documents():
    return {
        "document_id": f"doc-{_h('documents') % 100000}",
        "chunks_created": 3,
        "embedding_dimension": 384,
    }


@api.post("/documents/upload")
async def rag_documents_upload(file: UploadFile = File(...)):
    return {
        "document_id": f"doc-{_h(file.filename, 'upload') % 100000}",
        "chunks_created": 2,
        "embedding_dimension": 384,
        "filename": file.filename,
    }


def _make_transcription(
    seed_text: str, language: str, extract_technical: bool
) -> Dict[str, Any]:
    words = re.findall(r"[A-Za-z0-9_]+", seed_text) or [
        "sample",
        "technical",
        "audio",
        "segment",
    ]
    tokens = words[:12]
    transcript = " ".join(tokens) + "."
    segments = []
    for i, token in enumerate(tokens):
        segments.append(
            {
                "id": i,
                "start": round(i * 0.9, 2),
                "end": round((i + 1) * 0.9, 2),
                "text": token,
                "confidence": round(0.8 + ((_h(token, i) % 20) / 100), 2),
            }
        )
    technical_segments = []
    if extract_technical:
        keyword_set = {k for values in TECHNICAL_KEYWORDS.values() for k in values}
        for segment in segments:
            if segment["text"].lower() in keyword_set:
                technical_segments.append(segment)
    return {
        "transcript": transcript,
        "segments": segments,
        "technical_segments": technical_segments,
        "processing_time": round(len(tokens) * 0.03, 4),
        "language": language or "en",
        "audio_duration": round(len(tokens) * 0.9, 2),
    }


@api.post("/transcribe")
async def asr_transcribe(
    request: TranscriptionRequest,
    x_surrogate_profile: Optional[str] = Header(default=None),
    x_surrogate_fault: Optional[str] = Header(default=None),
    x_surrogate_latency_ms: Optional[int] = Header(default=None),
):
    profile = _get_profile(x_surrogate_profile)
    payload_seed = request.audio_url or request.audio_data or "no-audio"
    profile_meta = await _apply_profile(
        endpoint_key="asr.transcribe",
        profile=profile,
        payload_key=payload_seed,
        forced_fault=x_surrogate_fault,
        forced_latency_ms=x_surrogate_latency_ms,
    )
    result = _make_transcription(
        seed_text=payload_seed,
        language=request.language or "en",
        extract_technical=request.extract_technical,
    )
    result["surrogate"] = profile_meta
    return result


@api.post("/transcribe/file")
async def asr_transcribe_file(
    file: UploadFile = File(...),
    language: Optional[str] = Form(default="en"),
    extract_technical: bool = Form(default=True),
):
    content = await file.read()
    seed_text = f"{file.filename}-{len(content)}"
    return _make_transcription(
        seed_text=seed_text,
        language=language or "en",
        extract_technical=extract_technical,
    )


@api.get("/technical/keywords")
async def asr_keywords():
    all_keywords = sorted({k for values in TECHNICAL_KEYWORDS.values() for k in values})
    return {
        "categories": TECHNICAL_KEYWORDS,
        "total_keywords": len(all_keywords),
    }


@api.post("/technical/analyze")
async def asr_analyze(text: str):
    text_lower = text.lower()
    matches = [
        k for values in TECHNICAL_KEYWORDS.values() for k in values if k in text_lower
    ]
    score = min(1.0, len(matches) * 0.15)
    return {
        "text": text,
        "technical_score": round(score, 3),
        "is_technical": score >= 0.15,
        "matching_keywords": sorted(set(matches)),
        "word_count": len(text.split()),
    }


@api.get("/models/info")
async def asr_models_info():
    return {
        "model_size": "tiny",
        "device": "cpu",
        "model_loaded": True,
        "supported_languages": ["en", "es", "fr", "de"],
        "supported_formats": ["wav", "mp3", "m4a", "mp4", "webm"],
    }


def _domain_result(domain: str, query: str, limit: int) -> Dict[str, Any]:
    templates = {
        "chemistry": [
            (
                "Acid-base control",
                "Maintain pH setpoint and confirm concentration units.",
            ),
            ("Reaction safety", "Verify corrosive handling and containment controls."),
        ],
        "mechanical": [
            ("Stress check", "Use sigma = F/A with SI units and safety factor."),
            ("Beam response", "Evaluate deflection with boundary-specific equations."),
        ],
        "materials": [
            (
                "Material selection",
                "Compare strength-to-weight trade-offs by load case.",
            ),
            (
                "Property validation",
                "Confirm yield strength and modulus from source table.",
            ),
        ],
    }
    rows = templates[domain][: max(1, min(limit, len(templates[domain])))]
    results = []
    for idx, (title, content) in enumerate(rows):
        score = 0.62 + ((_h(domain, query, idx) % 30) / 100)
        results.append(
            {
                "id": f"{domain}-{idx+1}",
                "title": title,
                "content": f"{content} Query context: {query[:120]}",
                "tags": [domain, "surrogate"],
                "source": f"{domain}_kb_surrogate",
                "score": round(min(score, 0.99), 3),
            }
        )
    return {
        "domain": domain,
        "results": results,
        "metadata": {
            "total_items": len(results),
            "keywords_matched": sum(
                1 for k in TECHNICAL_KEYWORDS[domain] if k in query.lower()
            ),
        },
        "query_time": 0.01,
    }


@api.get("/domains")
async def mcp_domains():
    return {
        "domains": [
            {"name": "chemistry", "items_count": 2, "metadata": {"surrogate": True}},
            {"name": "mechanical", "items_count": 2, "metadata": {"surrogate": True}},
            {"name": "materials", "items_count": 2, "metadata": {"surrogate": True}},
        ]
    }


@api.post("/chemistry/query")
async def mcp_chemistry_query(request: DomainQuery):
    return _domain_result("chemistry", request.query, request.limit)


@api.post("/mechanical/query")
async def mcp_mechanical_query(request: DomainQuery):
    return _domain_result("mechanical", request.query, request.limit)


@api.post("/materials/query")
async def mcp_materials_query(request: DomainQuery):
    return _domain_result("materials", request.query, request.limit)


@api.post("/domains/reload")
async def mcp_reload():
    return {
        "success": True,
        "message": "Surrogate domains reloaded",
        "domain_stats": {"chemistry": 2, "mechanical": 2, "materials": 2},
    }


@api.get("/domains/{domain_name}/items")
async def mcp_domain_items(domain_name: str, limit: int = 50):
    if domain_name not in {"chemistry", "mechanical", "materials"}:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_name}' not found")
    result = _domain_result(domain_name, "list items", min(limit, 10))
    return {
        "domain": domain_name,
        "items": result["results"],
        "total_items": len(result["results"]),
        "showing": len(result["results"]),
    }


@api.get("/capabilities")
async def mcp_capabilities():
    return {
        "chemistry": {
            "molecular_weight": "Calculate molecular weight from formula",
            "ph_calculation": "Convert concentration and pH",
            "molecular_properties": "Return deterministic surrogate descriptors",
            "libraries_available": False,
        },
        "mechanical": {
            "beam_calculation": "Calculate stress and deflection",
            "supported_beam_types": [
                "simply_supported",
                "cantilever",
                "fixed_both_ends",
            ],
            "supported_load_types": ["point_center", "point_end", "distributed"],
        },
        "materials": {
            "property_lookup": "Lookup material property set",
            "available_properties": sorted(
                {k for material in MATERIAL_DB.values() for k in material.keys()}
            ),
        },
    }


@api.post("/chemistry/molecular_weight")
async def chemistry_molecular_weight(request: MolecularWeightRequest):
    composition: Dict[str, int] = {}
    for symbol, count in re.findall(r"([A-Z][a-z]?)(\d*)", request.formula):
        if symbol not in ATOMIC_WEIGHTS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported element '{symbol}'"
            )
        composition[symbol] = composition.get(symbol, 0) + int(count or "1")
    if not composition:
        raise HTTPException(status_code=400, detail="Invalid chemical formula")
    breakdown = {
        symbol: round(ATOMIC_WEIGHTS[symbol] * count, 6)
        for symbol, count in composition.items()
    }
    molecular_weight = round(sum(breakdown.values()), 6)
    return {
        "formula": request.formula,
        "molecular_weight": molecular_weight,
        "composition": composition,
        "molar_mass_breakdown": breakdown,
    }


@api.post("/chemistry/ph_calculation")
async def chemistry_ph(request: PHCalculationRequest):
    if request.value <= 0:
        raise HTTPException(status_code=400, detail="Value must be > 0")
    calc_type = request.calculation_type.strip().lower()
    ion_type = request.ion_type.strip().upper()
    if calc_type == "concentration_to_ph":
        if ion_type == "H+":
            result = -math.log10(request.value)
            units = "pH"
        elif ion_type == "OH-":
            poh = -math.log10(request.value)
            result = 14 - poh
            units = "pH"
        else:
            raise HTTPException(status_code=400, detail="ion_type must be H+ or OH-")
    elif calc_type == "ph_to_concentration":
        result = 10 ** (-request.value)
        units = "mol/L"
    else:
        raise HTTPException(
            status_code=400,
            detail="calculation_type must be concentration_to_ph or ph_to_concentration",
        )
    return {
        "input_type": calc_type,
        "input_value": request.value,
        "result": round(result, 8),
        "result_units": units,
        "calculation_details": {"ion_type": ion_type},
    }


@api.post("/chemistry/molecular_properties")
async def chemistry_properties(request: MolecularPropertyRequest):
    identity = request.smiles or request.name or request.formula or "unknown"
    h = _h(identity, "molecule")
    return {
        "molecule_info": {"input": identity, "source": "surrogate"},
        "properties": {
            "molecular_weight_estimate": round(50 + (h % 450) / 10, 3),
            "logp_estimate": round(((h % 700) / 100) - 2, 3),
            "hbond_donors_estimate": int(h % 6),
        },
        "descriptors": {
            "fingerprint_family": "surrogate-hashed",
            "confidence": round(0.75 + (h % 20) / 100, 2),
        },
    }


@api.post("/mechanical/beam_calculation")
async def mechanical_beam(request: BeamCalculationRequest):
    if (
        request.length <= 0
        or request.moment_of_inertia <= 0
        or request.elastic_modulus <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail="length, moment_of_inertia, elastic_modulus must be > 0",
        )
    moment = request.load * request.length / 4.0
    max_stress = moment * 0.05 / request.moment_of_inertia
    max_deflection = (request.load * request.length**3) / (
        48 * request.elastic_modulus * request.moment_of_inertia
    )
    safety_factor = None
    if request.material_yield_strength:
        safety_factor = (
            request.material_yield_strength / max_stress if max_stress > 0 else None
        )
    return {
        "input_parameters": request.dict(),
        "max_stress": round(max_stress, 3),
        "max_deflection": round(max_deflection, 8),
        "safety_factor": round(safety_factor, 3) if safety_factor else None,
        "stress_location": "midspan",
        "deflection_location": "midspan",
        "calculations": {
            "bending_moment": round(moment, 6),
            "formula": "delta = PL^3 / (48EI)",
        },
    }


@api.post("/materials/properties")
async def materials_properties(request: MaterialPropertyRequest):
    material_key = request.material.strip().lower()
    if material_key not in MATERIAL_DB:
        raise HTTPException(
            status_code=404, detail=f"Material '{request.material}' not found"
        )
    base = MATERIAL_DB[material_key]
    result_properties = {}
    for key in request.properties:
        if key in base:
            result_properties[key] = base[key]
    return {
        "material": material_key,
        "temperature": request.temperature,
        "properties": result_properties,
        "metadata": {
            "available_properties": sorted(base.keys()),
            "database_name": "surrogate_materials_db",
        },
    }


@api.get("/materials/database")
async def materials_database():
    return {
        "database": {
            "metals": {
                "materials": sorted(MATERIAL_DB.keys()),
                "sample_properties": sorted(next(iter(MATERIAL_DB.values())).keys()),
            }
        },
        "total_categories": 1,
        "total_materials": len(MATERIAL_DB),
    }


@api.get("/tools")
async def tools_list():
    return {"tools": TOOLS, "count": len(TOOLS)}


@api.get("/tools/{tool_name}")
async def tools_get(tool_name: str):
    for tool in TOOLS:
        if tool["name"] == tool_name:
            return tool
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")


@api.post("/tools/{tool_name}/execute")
async def tools_execute(tool_name: str, request: ToolExecutionRequest):
    for tool in TOOLS:
        if tool["name"] == tool_name:
            return {
                "success": True,
                "result": {
                    "tool": tool_name,
                    "parameters": request.parameters,
                    "output": f"Deterministic surrogate output for {tool_name}",
                },
                "error": None,
                "execution_time": 0.004,
            }
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")


@api.post("/plugins/refresh")
async def plugins_refresh():
    return {"success": True, "message": "Surrogate plugin refresh completed"}


@api.get("/plugins/directory")
async def plugins_directory():
    return {"directory": "/plugins", "exists": True, "file_count": 0, "files": []}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(api, host="0.0.0.0", port=8000)
