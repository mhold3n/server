#!/usr/bin/env python3
"""
Extended Prompt Middleware Tests — covers VoiceAnalyzer, SemanticReprocessor,
PromptMiddleware._apply_transformation for each branch, FastAPI endpoints, etc.
"""

import os
import sys
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

# Patch HF model load so GeometricTransformer can be instantiated
_emb = np.random.default_rng(99).standard_normal((1, 384))
_cpu = MagicMock()
_cpu.numpy.return_value = _emb
_mean = MagicMock()
_mean.cpu.return_value = _cpu
_lh = MagicMock()
_lh.mean.return_value = _mean
_out = MagicMock()
_out.last_hidden_state = _lh
_model = MagicMock()
_model.return_value = _out
_model.to.return_value = _model
_tok = MagicMock()
_tok_t = MagicMock()
_tok_t.to.return_value = _tok_t
_tok.return_value = {"input_ids": _tok_t, "attention_mask": _tok_t}

patch("prompt_middleware.app.AutoTokenizer.from_pretrained", return_value=_tok).start()
patch("prompt_middleware.app.AutoModel.from_pretrained", return_value=_model).start()
patch("prompt_middleware.app.torch.cuda.is_available", return_value=False).start()
patch(
    "prompt_middleware.app.torch.no_grad",
    return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()),
).start()

from prompt_middleware.app import (  # noqa: E402
    VoiceAnalyzer,
    GeometricTransformer,
    SemanticReprocessor,
    PromptMiddleware,
    PromptContext,
    TransformationType,
    app as pm_app,
)

# ── VoiceAnalyzer ──────────────────────────────────────────────────


class TestVoiceAnalyzer:
    def setup_method(self):
        self.va = VoiceAnalyzer()

    def test_infer_emotional_high_pitch_energy(self):
        features = {"pitch_mean": 250, "energy_mean": 0.15, "tempo": 60}
        scores = self.va.infer_emotional_context(features)
        assert scores["anger"] > 0
        assert scores["joy"] > 0
        total = sum(scores.values())
        assert abs(total - 1.0) < 0.01

    def test_infer_emotional_low_pitch_energy(self):
        features = {"pitch_mean": 100, "energy_mean": 0.02, "tempo": 60}
        scores = self.va.infer_emotional_context(features)
        assert scores["sadness"] > 0

    def test_infer_emotional_high_tempo(self):
        features = {"pitch_mean": 0, "energy_mean": 0.0, "tempo": 150}
        scores = self.va.infer_emotional_context(features)
        assert scores["joy"] > 0

    def test_infer_emotional_neutral(self):
        features = {}
        scores = self.va.infer_emotional_context(features)
        assert scores["neutral"] == 1.0

    def test_detect_ambiguity_high(self):
        features = {"pitch_std": 110, "energy_mean": 0.07}
        assert self.va.detect_intentional_ambiguity(features) == 0.9

    def test_detect_ambiguity_moderate(self):
        features = {"pitch_std": 75, "energy_mean": 0.07}
        assert self.va.detect_intentional_ambiguity(features) == 0.7

    def test_detect_ambiguity_low(self):
        features = {"pitch_std": 10, "energy_mean": 0.01}
        assert self.va.detect_intentional_ambiguity(features) == 0.3


# ── GeometricTransformer ──────────────────────────────────────────


class TestGeometricTransformerExtended:
    def setup_method(self):
        self.gt = GeometricTransformer()

    def test_topological_deformation_nonzero(self):
        emb = np.random.randn(384)
        result = self.gt.topological_deformation(emb, curvature=0.5)
        assert not np.array_equal(emb, result)

    def test_topological_deformation_zero_norm(self):
        emb = np.zeros(384)
        result = self.gt.topological_deformation(emb, curvature=0.5)
        assert np.array_equal(emb, result)

    def test_dimensional_4d_different_times(self):
        emb = np.random.randn(384)
        r1 = self.gt.dimensional_4d_projection(emb, time_dimension=0.1)
        r2 = self.gt.dimensional_4d_projection(emb, time_dimension=0.9)
        assert not np.array_equal(r1, r2)


# ── SemanticReprocessor ──────────────────────────────────────────


class TestSemanticReprocessor:
    def setup_method(self):
        self.sr = SemanticReprocessor()

    def test_entropy_enhancement(self):
        emb = np.random.randn(384) + 1  # ensure positive values possible
        result = self.sr.entropy_enhancement("test text", emb)
        assert result is not None
        assert result.shape == emb.shape

    def test_build_semantic_graph(self):
        text = "hello world foo bar"
        # Use embeddings with length >= num words
        emb = np.random.randn(10)
        graph = self.sr.build_semantic_graph(text, emb)
        assert "hello" in graph.nodes

    def test_mutual_information_analysis(self):
        emb1 = np.random.randn(384)
        emb2 = np.random.randn(384)
        mi = self.sr.mutual_information_analysis("text1", "text2", emb1, emb2)
        assert isinstance(mi, float)


# ── PromptMiddleware async methods ────────────────────────────────


class TestPromptMiddlewareAsync:
    @pytest.mark.asyncio
    async def test_process_prompt_mirror(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="debug this code")
        results = await mw.process_prompt(ctx, [TransformationType.MIRROR])
        assert len(results) == 1
        r = results[0]
        assert r.transformation_type == TransformationType.MIRROR
        assert r.confidence_score > 0

    @pytest.mark.asyncio
    async def test_process_prompt_chiral(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="optimize algorithm")
        results = await mw.process_prompt(ctx, [TransformationType.CHIRAL])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_process_prompt_4d(self):
        mw = PromptMiddleware()
        ctx = PromptContext(
            text="fix this bug",
            temporal_context={"time_factor": 0.8},
        )
        results = await mw.process_prompt(ctx, [TransformationType.DIMENSIONAL_4D])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_process_prompt_4d_no_temporal(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="fix this bug")
        results = await mw.process_prompt(ctx, [TransformationType.DIMENSIONAL_4D])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_process_prompt_topological(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="refactor code", metadata={"curvature": 0.3})
        results = await mw.process_prompt(ctx, [TransformationType.TOPOLOGICAL])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_process_prompt_topological_no_metadata(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="refactor code")
        results = await mw.process_prompt(ctx, [TransformationType.TOPOLOGICAL])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_process_prompt_voice_conditioned_with_features(self):
        mw = PromptMiddleware()
        ctx = PromptContext(
            text="something is wrong",
            voice_features={
                "pitch_mean": 250,
                "energy_mean": 0.15,
                "tempo": 150,
                "pitch_std": 30,
                "valence": -0.5,
                "arousal": 0.9,
            },
        )
        results = await mw.process_prompt(ctx, [TransformationType.VOICE_CONDITIONED])
        assert len(results) == 1
        assert (
            "urgently" in results[0].transformed_prompt
            or len(results[0].transformed_prompt) > 0
        )

    @pytest.mark.asyncio
    async def test_process_prompt_voice_conditioned_no_features(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="something is wrong")
        results = await mw.process_prompt(ctx, [TransformationType.VOICE_CONDITIONED])
        assert len(results) == 1
        assert results[0].transformed_prompt == "something is wrong"

    @pytest.mark.asyncio
    async def test_process_prompt_semantic_rotation(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="improve this")
        results = await mw.process_prompt(ctx, [TransformationType.SEMANTIC_ROTATION])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_process_prompt_entropy_enhancement(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="enhance this prompt")
        results = await mw.process_prompt(ctx, [TransformationType.ENTROPY_ENHANCEMENT])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_process_prompt_all_transformations(self):
        mw = PromptMiddleware()
        ctx = PromptContext(
            text="help me with code",
            voice_features={
                "pitch_mean": 200,
                "energy_mean": 0.1,
                "tempo": 100,
                "pitch_std": 20,
            },
            temporal_context={"time_factor": 0.5},
            social_context={"formality": 0.5},
            domain_context={"domain": "coding", "keywords": ["help", "fix"]},
        )
        all_types = list(TransformationType)
        results = await mw.process_prompt(ctx, all_types)
        assert len(results) == len(all_types)

    @pytest.mark.asyncio
    async def test_embeddings_to_text_empty(self):
        mw = PromptMiddleware()
        result = await mw._embeddings_to_text(np.zeros(384), "")
        assert result == ""

    @pytest.mark.asyncio
    async def test_analyze_subtext_with_social(self):
        mw = PromptMiddleware()
        ctx = PromptContext(
            text="check this",
            voice_features={
                "pitch_mean": 200,
                "energy_mean": 0.1,
                "tempo": 100,
                "pitch_std": 20,
            },
            social_context={"relationship": "peer"},
            domain_context={"domain": "coding", "keywords": ["a", "b", "c", "d", "e"]},
        )
        subtext = await mw._analyze_subtext(ctx, "check this")
        assert subtext["social_dynamics"] == {"relationship": "peer"}
        assert subtext["domain_specificity"] == 0.5

    def test_calculate_confidence_full_context(self):
        mw = PromptMiddleware()
        ctx = PromptContext(
            text="test",
            voice_features={"pitch_mean": 200},
            temporal_context={"t": 1},
            spatial_context={"s": 1},
            social_context={"so": 1},
        )
        c = mw._calculate_confidence(ctx, "test")
        assert c == 1.0

    def test_calculate_confidence_minimal(self):
        mw = PromptMiddleware()
        ctx = PromptContext(text="test")
        c = mw._calculate_confidence(ctx, "test")
        assert c == 0.5


# ── FastAPI endpoints ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pm_health_endpoint():
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=pm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_pm_transform_endpoint():
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=pm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/transform",
            json={
                "text": "debug my code",
                "transformations": ["mirror", "chiral"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert len(body["results"]) == 2


@pytest.mark.asyncio
async def test_pm_transform_invalid_type():
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=pm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/transform",
            json={
                "text": "test",
                "transformations": ["nonexistent_type"],
            },
        )
        assert resp.status_code == 500  # ValueError from invalid enum
