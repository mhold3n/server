#!/usr/bin/env python3
"""
Extended advanced-transforms coverage tests.
Covers all transformer classes and their methods.
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

from prompt_middleware.transformations.advanced_transforms import (
    HyperbolicTransformer,
    QuantumInspiredTransformer,
    FractalTransformer,
    ManifoldTransformer,
    TemporalTransformer,
    AdvancedPromptTransformer,
    TransformationConfig,
)

# ── HyperbolicTransformer ──────────────────────────────────────────


class TestHyperbolicTransformer:
    def setup_method(self):
        self.ht = HyperbolicTransformer(curvature=-1.0)

    def test_poincare_large_norm(self):
        emb = np.random.randn(384) * 10  # norm >> 1
        result = self.ht.poincare_ball_projection(emb)
        assert result.shape == emb.shape

    def test_poincare_small_norm(self):
        emb = np.random.randn(384) * 0.01
        result = self.ht.poincare_ball_projection(emb)
        assert result.shape == emb.shape

    def test_mobius_even_dim(self):
        emb = np.random.randn(384)
        result = self.ht.mobius_transformation(emb)
        assert result.shape == emb.shape

    def test_mobius_odd_dim(self):
        emb = np.random.randn(385)
        result = self.ht.mobius_transformation(emb)
        assert result.shape == emb.shape

    def test_mobius_custom_params(self):
        emb = np.random.randn(384)
        result = self.ht.mobius_transformation(
            emb, a=2 + 0j, b=1 + 1j, c=0 + 0j, d=1 + 0j
        )
        assert result.shape == emb.shape


# ── QuantumInspiredTransformer ──────────────────────────────────


class TestQuantumInspired:
    def setup_method(self):
        self.qt = QuantumInspiredTransformer()

    def test_superposition(self):
        emb = np.random.randn(384)
        result = self.qt.quantum_superposition(emb, num_states=5)
        assert result.shape == emb.shape

    def test_entanglement(self):
        e1 = np.random.randn(384)
        e2 = np.random.randn(384)
        r1, r2 = self.qt.quantum_entanglement(e1, e2)
        assert r1.shape == (384,)
        assert r2.shape == (384,)

    def test_entanglement_diff_dims(self):
        e1 = np.random.randn(384)
        e2 = np.random.randn(200)
        r1, r2 = self.qt.quantum_entanglement(e1, e2)
        assert r1.shape == r2.shape == (200,)

    def test_superposition_tiny(self):
        emb = np.random.randn(1)
        result = self.qt.quantum_superposition(emb, num_states=2)
        assert result.shape == (1,)


# ── FractalTransformer ──────────────────────────────────────────


class TestFractalTransformer:
    def test_mandelbrot_even(self):
        ft = FractalTransformer(fractal_type="mandelbrot")
        emb = np.random.randn(384) * 0.1
        result = ft.mandelbrot_transform(emb, max_iter=10)
        assert result.shape == emb.shape

    def test_mandelbrot_odd(self):
        ft = FractalTransformer(fractal_type="mandelbrot")
        emb = np.random.randn(385) * 0.1
        result = ft.mandelbrot_transform(emb, max_iter=10)
        assert result.shape == (385,)

    def test_julia_even(self):
        ft = FractalTransformer(fractal_type="julia")
        emb = np.random.randn(384) * 0.1
        result = ft.julia_transform(emb, max_iter=10)
        assert result.shape == emb.shape

    def test_julia_odd(self):
        ft = FractalTransformer(fractal_type="julia")
        emb = np.random.randn(385) * 0.1
        result = ft.julia_transform(emb, max_iter=10)
        assert result.shape == (385,)


# ── ManifoldTransformer ──────────────────────────────────────────


class TestManifoldTransformer:
    def setup_method(self):
        self.mt = ManifoldTransformer()

    def test_projection_single_sample(self):
        emb = np.random.randn(384)
        result = self.mt.manifold_projection(emb, method="tsne")
        assert result.shape[0] == 2  # projected to 2D

    def test_projection_pca(self):
        emb = np.random.randn(10, 384)
        result = self.mt.manifold_projection(emb, method="pca")
        assert len(result) > 0

    def test_projection_ica(self):
        emb = np.random.randn(10, 384)
        result = self.mt.manifold_projection(emb, method="ica")
        assert len(result) > 0

    def test_projection_mds(self):
        emb = np.random.randn(5, 384)
        result = self.mt.manifold_projection(emb, method="mds")
        assert len(result) > 0

    def test_projection_unknown_method(self):
        emb = np.random.randn(5, 384)
        result = self.mt.manifold_projection(emb, method="unknown")
        assert len(result) > 0

    def test_projection_small_dim(self):
        emb = np.random.randn(1)  # 1D input
        result = self.mt.manifold_projection(emb, method="tsne")
        assert result.shape[0] == 2

    def test_geodesic(self):
        emb = np.random.randn(384)
        result = self.mt.geodesic_distance_transform(emb)
        assert result.shape == emb.shape


# ── TemporalTransformer ──────────────────────────────────────────


class TestTemporalTransformer:
    def setup_method(self):
        self.tt = TemporalTransformer(time_steps=10)

    def test_oscillatory(self):
        emb = np.random.randn(384)
        result = self.tt.temporal_evolution(emb, evolution_type="oscillatory")
        assert not np.array_equal(emb, result)

    def test_exponential(self):
        emb = np.random.randn(384)
        result = self.tt.temporal_evolution(emb, evolution_type="exponential")
        assert not np.array_equal(emb, result)

    def test_chaotic(self):
        emb = np.random.randn(384)
        result = self.tt.temporal_evolution(emb, evolution_type="chaotic")
        assert not np.array_equal(emb, result)

    def test_unknown_type(self):
        emb = np.random.randn(384)
        result = self.tt.temporal_evolution(emb, evolution_type="unknown")
        assert np.array_equal(emb, result)

    def test_phase_space_short(self):
        emb = np.random.randn(5)
        result = self.tt.phase_space_reconstruction(emb, delay=2, dimension=3)
        assert len(result) > 0

    def test_phase_space_long(self):
        emb = np.random.randn(384)
        result = self.tt.phase_space_reconstruction(emb, delay=1, dimension=3)
        assert len(result) > 0


# ── AdvancedPromptTransformer ──────────────────────────────────


class TestAdvancedPromptTransformer:
    def setup_method(self):
        self.apt = AdvancedPromptTransformer()
        self.config = TransformationConfig(intensity=1.0, add_noise=False)
        self.config_noisy = TransformationConfig(
            intensity=1.0, add_noise=True, noise_level=0.01
        )

    def test_hyperbolic_noisy(self):
        emb = np.random.randn(384)
        result = self.apt.apply_hyperbolic_transformation(emb, self.config_noisy)
        assert result.shape == emb.shape

    def test_quantum_noisy(self):
        emb = np.random.randn(384)
        result = self.apt.apply_quantum_transformation(emb, self.config_noisy)
        assert result.shape == emb.shape

    def test_fractal_noisy(self):
        emb = np.random.randn(384) * 0.1
        result = self.apt.apply_fractal_transformation(emb, self.config_noisy)
        assert result.shape == emb.shape

    def test_fractal_julia_type(self):
        apt = AdvancedPromptTransformer()
        apt.fractal.fractal_type = "julia"
        emb = np.random.randn(384) * 0.1
        result = apt.apply_fractal_transformation(emb, self.config)
        assert result.shape == emb.shape

    def test_manifold(self):
        emb = np.random.randn(384)
        result = self.apt.apply_manifold_transformation(emb, self.config)
        assert len(result) > 0

    def test_manifold_noisy(self):
        emb = np.random.randn(384)
        result = self.apt.apply_manifold_transformation(emb, self.config_noisy)
        assert len(result) > 0

    def test_temporal_noisy(self):
        emb = np.random.randn(384)
        result = self.apt.apply_temporal_transformation(emb, self.config_noisy)
        assert result.shape == emb.shape

    def test_multi_modal(self):
        emb = np.random.randn(384)
        results = self.apt.apply_multi_modal_transformation(emb, self.config)
        assert "ensemble" in results
        assert "hyperbolic" in results
        assert "quantum" in results
        assert "fractal" in results
        assert "manifold" in results
        assert "temporal" in results


# ── TransformationConfig ──────────────────────────────────────────


class TestTransformationConfig:
    def test_defaults(self):
        c = TransformationConfig()
        assert c.intensity == 1.0
        assert c.preserve_semantics is True
        assert c.add_noise is False
        assert c.noise_level == 0.1

    def test_custom(self):
        c = TransformationConfig(intensity=0.5, add_noise=True, noise_level=0.05)
        assert c.intensity == 0.5
        assert c.add_noise is True
        assert c.noise_level == 0.05
