#!/usr/bin/env python3
"""
Additional RAG endpoint and citation coverage tests.
"""

import io
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

import rag.app as rag


@pytest.fixture
def client():
    return TestClient(rag.api)


@pytest.fixture(autouse=True)
def setup_rag_state():
    rag.rag_service.qdrant_client = Mock()
    rag.rag_service.embedding_model = Mock()
    rag.rag_service._remote_embedder = None
    rag.rag_service.use_mock = True
    rag.rag_service.bm25_index = None
    rag.rag_service.bm25_corpus = []
    rag.rag_service.bm25_documents = []
    yield
    rag.rag_service.qdrant_client = None
    rag.rag_service.embedding_model = None
    rag.rag_service._remote_embedder = None


@pytest.mark.asyncio
async def test_remote_embedding_client_encode_sets_dimension():
    client = rag.RemoteEmbeddingClient("http://localhost:8000/v1/embeddings")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": [{"embedding": [1.0, 2.0, 3.0]}]}
    async_client = AsyncMock()
    async_client.post.return_value = response
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=async_client)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch("rag.app.httpx.AsyncClient", return_value=context_manager):
        embeddings = await client.encode("hello world")

    assert embeddings.shape == (1, 3)
    assert client.get_sentence_embedding_dimension() == 3
    assert np.allclose(embeddings[0], [1.0, 2.0, 3.0])


@pytest.mark.asyncio
async def test_remote_embedding_client_ollama_embed_shape_and_endpoint():
    client = rag.RemoteEmbeddingClient(
        "http://localhost:11434",
        model="nomic-embed-text",
        backend="ollama",
    )
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
    async_client = AsyncMock()
    async_client.post.return_value = response
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=async_client)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch("rag.app.httpx.AsyncClient", return_value=context_manager):
        embeddings = await client.encode("hello world")

    async_client.post.assert_awaited_once()
    url = async_client.post.await_args.args[0]
    payload = async_client.post.await_args.kwargs["json"]
    assert url == "http://localhost:11434/api/embed"
    assert payload == {"model": "nomic-embed-text", "input": ["hello world"]}
    assert embeddings.shape == (1, 3)
    assert client.get_sentence_embedding_dimension() == 3


@pytest.mark.asyncio
async def test_rerank_candidates_merges_cross_encoder_scores():
    svc = rag.RAGService()
    svc.reranker_url = "http://reranker:8080"
    candidates = [
        {"content": "low", "combined_score": 0.9},
        {"content": "high", "combined_score": 0.1},
    ]
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "results": [
            {"index": 0, "score": 0.1},
            {"index": 1, "score": 0.9},
        ]
    }
    async_client = AsyncMock()
    async_client.post.return_value = response
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=async_client)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch("rag.app.httpx.AsyncClient", return_value=context_manager):
        applied = await svc.rerank_candidates("query", candidates, k=2)

    assert applied is True
    async_client.post.assert_awaited_once()
    url = async_client.post.await_args.args[0]
    payload = async_client.post.await_args.kwargs["json"]
    assert url == "http://reranker:8080/rerank"
    assert payload["query"] == "query"
    assert payload["documents"] == ["low", "high"]
    assert candidates[0]["content"] == "high"
    assert candidates[0]["reranker_score"] == 0.9


@pytest.mark.asyncio
async def test_rerank_candidates_failure_preserves_fallback_scores():
    svc = rag.RAGService()
    svc.reranker_url = "http://reranker:8080/rerank"
    candidates = [
        {"content": "first", "combined_score": 0.6},
        {"content": "second", "combined_score": 0.5},
    ]
    async_client = AsyncMock()
    async_client.post.side_effect = httpx.ConnectError("down")
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=async_client)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch("rag.app.httpx.AsyncClient", return_value=context_manager):
        applied = await svc.rerank_candidates("query", candidates, k=2)

    assert applied is False
    assert [c["content"] for c in candidates] == ["first", "second"]
    assert "reranker_score" not in candidates[0]


@patch("rag.app.RAGService.add_document", new_callable=AsyncMock)
def test_upload_document_invalid_metadata_uses_empty_dict(mock_add_document, client):
    mock_add_document.return_value = {
        "document_id": "doc-upload",
        "chunks_created": 1,
        "embedding_dimension": 384,
    }

    response = client.post(
        "/documents/upload",
        files={"file": ("upload.txt", io.BytesIO(b"hello"), "text/plain")},
        data={"domain": "general", "metadata": "{not-json"},
    )

    assert response.status_code == 200
    metadata = mock_add_document.await_args.kwargs["metadata"]
    assert metadata["filename"] == "upload.txt"
    assert metadata["content_type"] == "text/plain"


@pytest.mark.asyncio
async def test_add_asr_document_success_uses_technical_segments():
    rag.rag_service.add_document = AsyncMock(
        return_value={
            "document_id": "asr-doc",
            "chunks_created": 2,
            "embedding_dimension": 384,
        }
    )
    technical_segments = [
        {"text": "technical alpha", "start": 0.0, "end": 1.0, "is_technical": True},
        {"text": "technical beta", "start": 1.0, "end": 2.0, "is_technical": True},
    ]
    segments = technical_segments + [
        {"text": "general gamma", "start": 2.0, "end": 3.0, "is_technical": False}
    ]

    response = await rag.add_asr_document(
        transcript="technical alpha technical beta general gamma",
        segments=segments,
        technical_segments=technical_segments,
        domain="mechanical",
        source="call-123",
        use_technical_only=True,
    )

    assert response.document_id == "asr-doc"
    add_kwargs = rag.rag_service.add_document.await_args.kwargs
    assert add_kwargs["content"] == "technical alpha technical beta"
    assert add_kwargs["source_type"] == "asr"
    assert add_kwargs["timestamps"] == technical_segments


@pytest.mark.asyncio
async def test_add_asr_document_error_is_wrapped():
    rag.rag_service.add_document = AsyncMock(side_effect=RuntimeError("asr failure"))

    with pytest.raises(rag.HTTPException) as exc_info:
        await rag.add_asr_document(
            transcript="hello",
            segments=[{"text": "hello", "start": 0.0, "end": 1.0}],
            technical_segments=[],
        )

    assert exc_info.value.status_code == 500
    assert "Failed to add ASR document" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_collection_info_uninitialized_client():
    rag.rag_service.qdrant_client = None

    with pytest.raises(rag.HTTPException) as exc_info:
        await rag.get_collection_info()

    assert exc_info.value.status_code == 500
    assert "Failed to get collection info" in exc_info.value.detail


@pytest.mark.asyncio
async def test_clear_collection_uninitialized_client():
    rag.rag_service.qdrant_client = None

    with pytest.raises(rag.HTTPException) as exc_info:
        await rag.clear_collection()

    assert exc_info.value.status_code == 500
    assert "Failed to clear collection" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_document_citations_success():
    rag.rag_service.qdrant_client.scroll.return_value = (
        [
            SimpleNamespace(
                id="chunk-1",
                payload={
                    "chunk_index": 0,
                    "content": "chunk content",
                    "citation": {"source": "doc.txt", "source_type": "text"},
                },
            )
        ],
        None,
    )

    result = await rag.get_document_citations("doc-123")

    assert result["document_id"] == "doc-123"
    assert result["total_chunks"] == 1
    assert result["citations"][0]["chunk_id"] == "chunk-1"


@pytest.mark.asyncio
async def test_get_document_citations_error_is_wrapped():
    rag.rag_service.qdrant_client = None

    with pytest.raises(rag.HTTPException) as exc_info:
        await rag.get_document_citations("doc-123")

    assert exc_info.value.status_code == 500
    assert "Failed to get citations" in exc_info.value.detail


@pytest.mark.asyncio
async def test_search_by_citation_success_with_filters():
    rag.rag_service.qdrant_client.scroll.return_value = (
        [
            SimpleNamespace(
                id="chunk-2",
                payload={
                    "content": "technical result",
                    "source": "call.wav",
                    "source_type": "asr",
                    "citation": {"is_technical": True},
                    "domain": "materials",
                    "timestamp": "2024-01-01T00:00:00",
                },
            )
        ],
        None,
    )

    result = await rag.search_by_citation(
        source="call.wav",
        source_type="asr",
        technical_only=True,
        limit=25,
    )

    assert result["total_found"] == 1
    assert result["results"][0]["chunk_id"] == "chunk-2"
    assert result["search_criteria"]["technical_only"] is True


@pytest.mark.asyncio
async def test_search_by_citation_error_is_wrapped():
    rag.rag_service.qdrant_client = None

    with pytest.raises(rag.HTTPException) as exc_info:
        await rag.search_by_citation(source="missing.txt")

    assert exc_info.value.status_code == 500
    assert "Citation search failed" in exc_info.value.detail
