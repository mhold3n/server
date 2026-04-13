#!/usr/bin/env python3
"""
Extended RAG Service coverage tests.
Covers RAGService helper methods, domain scoring,
chunking, citation generation, and preprocessing.
"""

import os
import re
import sys
import numpy as np
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

# Patch qdrant and nltk so import doesn't fail
with patch.dict(os.environ, {"USE_MOCK_MODELS": "true"}):
    from rag.app import RAGService, RemoteEmbeddingClient  # noqa: E402


# ── RAGService helper methods ─────────────────────────────────


class TestChunkText:
    def setup_method(self):
        self.svc = RAGService()

    def test_short_text_single_chunk(self):
        chunks = self.svc.chunk_text("Hello world", chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_long_text_multiple_chunks(self):
        text = "word " * 200  # ~1000 chars
        chunks = self.svc.chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) > 1
        for ch in chunks:
            assert len(ch) > 0

    def test_word_boundary_break(self):
        text = "abcde " * 100  # 600 chars, spaces every 6 chars
        chunks = self.svc.chunk_text(text, chunk_size=50, overlap=10)
        assert len(chunks) > 1

    def test_exact_chunk_size(self):
        text = "a" * 500
        chunks = self.svc.chunk_text(text, chunk_size=500)
        assert len(chunks) == 1


class TestDomainScore:
    def setup_method(self):
        self.svc = RAGService()

    def test_no_weights(self):
        score = self.svc.calculate_domain_score("Some text about steel", {})
        assert score == 1.0

    def test_chemistry_match(self):
        score = self.svc.calculate_domain_score(
            "The molecule undergoes a reaction with the compound",
            {"chemistry": 1.0},
        )
        assert score > 0

    def test_mechanical_match(self):
        score = self.svc.calculate_domain_score(
            "The force and stress on the material exceed limits",
            {"mechanical": 1.0},
        )
        assert score > 0

    def test_materials_match(self):
        score = self.svc.calculate_domain_score(
            "The steel alloy has good properties",
            {"materials": 1.0},
        )
        assert score > 0

    def test_no_match(self):
        score = self.svc.calculate_domain_score(
            "Hello this is a generic sentence",
            {"chemistry": 1.0},
        )
        assert score == 0.0

    def test_zero_weight_domain(self):
        score = self.svc.calculate_domain_score(
            "Steel alloy with reaction compound",
            {"chemistry": 0.0, "materials": 0.0},
        )
        assert score == 0.0

    def test_multi_domain(self):
        score = self.svc.calculate_domain_score(
            "The steel alloy undergoes a chemical reaction with force",
            {"chemistry": 0.5, "mechanical": 0.3, "materials": 0.2},
        )
        assert score > 0


class TestPreprocessText:
    def setup_method(self):
        self.svc = RAGService()

    def test_basic_preprocessing(self):
        tokens = self.svc.preprocess_text("The quick brown fox jumps over the lazy dog")
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        # should be lowercase
        for t in tokens:
            assert t == t.lower()

    def test_special_chars_removed(self):
        tokens = self.svc.preprocess_text("Hello! @world #test $special")
        for t in tokens:
            assert re.match(r"^[a-z0-9]+$", t) is not None or len(t) <= 2

    def test_empty_string(self):
        tokens = self.svc.preprocess_text("")
        assert isinstance(tokens, list)


class TestGenerateCitations:
    def setup_method(self):
        self.svc = RAGService()

    def test_with_preexisting_citations(self):
        existing = [{"source": "test.pdf", "page": 5}]
        result = self.svc.generate_citations("content", "source", citations=existing)
        assert result == existing

    def test_asr_with_timestamps(self):
        timestamps = [
            {"start": 0.0, "end": 2.5, "text": "hello", "confidence": 0.9},
            {"start": 2.5, "end": 5.0, "text": "world", "confidence": 0.8},
        ]
        result = self.svc.generate_citations(
            "hello world", "audio.mp3", source_type="asr", timestamps=timestamps
        )
        assert len(result) == 2
        assert result[0]["source_type"] == "asr"
        assert result[0]["timestamp_start"] == 0.0

    def test_text_source(self):
        result = self.svc.generate_citations(
            "Some text content", "doc.txt", source_type="text"
        )
        assert len(result) == 1
        assert result[0]["source_type"] == "text"

    def test_unknown_source(self):
        result = self.svc.generate_citations("content", None, source_type="text")
        assert result[0]["source"] == "unknown"


class TestMapChunkToCitation:
    def setup_method(self):
        self.svc = RAGService()

    def test_empty_citations(self):
        result = self.svc.map_chunk_to_citation("chunk", 0, [], 0, 100)
        assert result is None

    def test_asr_citation(self):
        citations = [{"source_type": "asr", "timestamp_start": 0, "timestamp_end": 5}]
        result = self.svc.map_chunk_to_citation("chunk", 0, citations, 0, 100)
        assert result is not None
        assert result["source_type"] == "asr"

    def test_text_citation(self):
        citations = [{"source_type": "text", "source": "doc.txt"}]
        result = self.svc.map_chunk_to_citation("chunk", 0, citations, 0, 100)
        assert result is not None
        assert result["source_type"] == "text"


class TestEmbedMock:
    @pytest.mark.asyncio
    async def test_mock_embed_single(self):
        svc = RAGService()
        svc.use_mock = True
        svc.embedding_dimension = 384
        result = await svc.embed("Hello world")
        assert result.shape == (1, 384)
        norm = np.linalg.norm(result[0])
        assert abs(norm - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_mock_embed_batch(self):
        svc = RAGService()
        svc.use_mock = True
        svc.embedding_dimension = 384
        result = await svc.embed(["Hello", "World"])
        assert result.shape == (2, 384)

    @pytest.mark.asyncio
    async def test_no_backend_raises(self):
        svc = RAGService()
        svc.use_mock = False
        svc._remote_embedder = None
        svc.embedding_model = None
        with pytest.raises(RuntimeError, match="No embedding backend"):
            await svc.embed("test")


class TestRemoteEmbeddingClient:
    def test_default_dimension(self):
        client = RemoteEmbeddingClient("http://localhost:8000/v1/embeddings")
        assert client.get_sentence_embedding_dimension() == 384

    def test_dimension_after_set(self):
        client = RemoteEmbeddingClient("http://localhost:8000/v1/embeddings")
        client._dimension = 768
        assert client.get_sentence_embedding_dimension() == 768
