"""
Cross-encoder reranker service.

Accepts a query + candidate documents and returns them reranked by relevance
using a cross-encoder model (e.g. ms-marco-MiniLM-L-6-v2).

Runs on GPU 1 (RTX 2080) alongside the embedding lane.
"""

import os
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

api = FastAPI(
    title="Reranker API",
    description="Cross-encoder reranker for RAG retrieval pipelines",
    version="1.0.0",
)


# ── Models ────────────────────────────────────────────────────────

class RerankRequest(BaseModel):
    query: str = Field(..., description="The search query")
    documents: List[str] = Field(..., description="Candidate document texts")
    top_k: Optional[int] = Field(default=None, description="Max results to return (default: all)")


class RerankResult(BaseModel):
    index: int
    document: str
    score: float


class RerankResponse(BaseModel):
    query: str
    results: List[RerankResult]


# ── Service ───────────────────────────────────────────────────────

_model: Optional[CrossEncoder] = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        model_name = os.getenv(
            "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        logger.info(f"Loading cross-encoder model: {model_name}")
        _model = CrossEncoder(model_name)
        logger.info("Cross-encoder model loaded")
    return _model


@api.on_event("startup")
async def startup():
    _get_model()


@api.get("/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": _model is not None,
        "model_name": os.getenv(
            "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ),
    }


@api.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    """Rerank documents by cross-encoder relevance to the query."""
    if not request.documents:
        raise HTTPException(status_code=400, detail="documents list must not be empty")

    model = _get_model()
    pairs = [[request.query, doc] for doc in request.documents]

    try:
        scores = model.predict(pairs).tolist()
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reranking failed: {e}")

    # Build results sorted by score descending
    indexed = [
        RerankResult(index=i, document=doc, score=score)
        for i, (doc, score) in enumerate(zip(request.documents, scores))
    ]
    indexed.sort(key=lambda r: r.score, reverse=True)

    if request.top_k is not None:
        indexed = indexed[: request.top_k]

    return RerankResponse(query=request.query, results=indexed)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(api, host="0.0.0.0", port=8000)
