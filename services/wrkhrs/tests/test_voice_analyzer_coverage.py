#!/usr/bin/env python3
"""
Extended Voice Analyzer coverage tests.
Covers AdvancedVoiceAnalyzer subtext inference methods with various feature combinations.
"""

import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

from prompt_middleware.voice.voice_analyzer import (
    AdvancedVoiceAnalyzer,
    VoiceFeatures,
    SubtextInference,
)


def _make_features(**overrides) -> VoiceFeatures:
    """Helper to build VoiceFeatures with sensible defaults + overrides."""
    defaults = dict(
        pitch_mean=180.0,
        pitch_std=30.0,
        pitch_range=60.0,
        pitch_skew=0.0,
        pitch_kurtosis=0.0,
        tempo=120.0,
        rhythm_regularity=0.6,
        pause_frequency=1.0,
        pause_duration_mean=0.5,
        energy_mean=0.08,
        energy_std=0.02,
        energy_skew=0.0,
        energy_kurtosis=0.0,
        spectral_centroid_mean=2000.0,
        spectral_centroid_std=200.0,
        spectral_rolloff_mean=4000.0,
        spectral_rolloff_std=500.0,
        spectral_bandwidth_mean=1000.0,
        spectral_bandwidth_std=100.0,
        zero_crossing_rate_mean=0.1,
        zero_crossing_rate_std=0.02,
        mfcc_mean=np.zeros(13),
        mfcc_std=np.zeros(13),
        f1_mean=800.0,
        f2_mean=1200.0,
        f3_mean=2500.0,
        f1_std=50.0,
        f2_std=100.0,
        f3_std=200.0,
        jitter=0.04,
        shimmer=0.09,
        hnr=15.0,
        valence=0.0,
        arousal=0.5,
        dominance=0.5,
    )
    defaults.update(overrides)
    return VoiceFeatures(**defaults)


class TestEmotionalStateInference:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_anger_detected(self):
        f = _make_features(pitch_mean=220, energy_mean=0.15, arousal=0.8, valence=-0.4)
        state = self.a._infer_emotional_state(f)
        assert state["anger"] > 0

    def test_joy_detected(self):
        f = _make_features(pitch_mean=200, energy_mean=0.1, valence=0.5, arousal=0.3)
        state = self.a._infer_emotional_state(f)
        assert state["joy"] > 0

    def test_sadness_detected(self):
        f = _make_features(pitch_mean=120, energy_mean=0.03, valence=-0.5, arousal=0.1)
        state = self.a._infer_emotional_state(f)
        assert state["sadness"] > 0

    def test_fear_detected(self):
        f = _make_features(pitch_std=70, arousal=0.6, valence=-0.3)
        state = self.a._infer_emotional_state(f)
        assert state["fear"] > 0

    def test_surprise_detected(self):
        f = _make_features(pitch_mean=220, arousal=0.8, valence=0.0)
        state = self.a._infer_emotional_state(f)
        assert state["surprise"] > 0

    def test_disgust_detected(self):
        f = _make_features(pitch_mean=130, valence=-0.6, arousal=0.1, energy_mean=0.03)
        state = self.a._infer_emotional_state(f)
        assert state["disgust"] > 0

    def test_neutral_when_nothing_triggers(self):
        f = _make_features(
            pitch_mean=170, energy_mean=0.06, valence=0.0, arousal=0.2, pitch_std=20
        )
        state = self.a._infer_emotional_state(f)
        assert state["neutral"] == 1.0


class TestConfidence:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_high_confidence(self):
        f = _make_features(
            pitch_std=10, rhythm_regularity=0.9, jitter=0.02, shimmer=0.05
        )
        c = self.a._calculate_confidence(f)
        assert c >= 0.9

    def test_low_confidence(self):
        f = _make_features(pitch_std=80, rhythm_regularity=0.1, jitter=0.2, shimmer=0.3)
        c = self.a._calculate_confidence(f)
        assert c <= 0.6


class TestIntentionalAmbiguity:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_high_ambiguity(self):
        f = _make_features(
            pitch_std=80,
            rhythm_regularity=0.3,
            pause_frequency=3.0,
            jitter=0.15,
            shimmer=0.2,
        )
        score = self.a._detect_intentional_ambiguity(f)
        assert score >= 0.7

    def test_low_ambiguity(self):
        f = _make_features(
            pitch_std=10,
            rhythm_regularity=0.9,
            pause_frequency=0.5,
            jitter=0.02,
            shimmer=0.05,
        )
        score = self.a._detect_intentional_ambiguity(f)
        assert score == 0.0


class TestUrgency:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_high_urgency(self):
        f = _make_features(
            tempo=140,
            energy_mean=0.15,
            arousal=0.8,
            pitch_mean=220,
            pause_frequency=0.5,
        )
        u = self.a._assess_urgency(f)
        assert u >= 0.8

    def test_low_urgency(self):
        f = _make_features(
            tempo=80, energy_mean=0.04, arousal=0.2, pitch_mean=150, pause_frequency=3.0
        )
        u = self.a._assess_urgency(f)
        assert u <= 0.3


class TestSocialDominance:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_high_dominance(self):
        f = _make_features(
            pitch_mean=200,
            energy_mean=0.12,
            jitter=0.02,
            rhythm_regularity=0.8,
            dominance=0.6,
        )
        d = self.a._assess_social_dominance(f)
        assert d >= 0.8

    def test_low_dominance(self):
        f = _make_features(
            pitch_mean=130,
            energy_mean=0.04,
            jitter=0.1,
            rhythm_regularity=0.3,
            dominance=0.0,
        )
        d = self.a._assess_social_dominance(f)
        assert d <= 0.2


class TestDeception:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_deception_indicators_high(self):
        f = _make_features(
            jitter=0.12,
            shimmer=0.2,
            rhythm_regularity=0.2,
            pause_frequency=4.0,
            hnr=5.0,
        )
        d = self.a._detect_deception_indicators(f)
        assert d >= 0.8

    def test_deception_indicators_low(self):
        f = _make_features(
            jitter=0.02,
            shimmer=0.05,
            rhythm_regularity=0.9,
            pause_frequency=0.5,
            hnr=30.0,
        )
        d = self.a._detect_deception_indicators(f)
        assert d == 0.0


class TestCognitiveLoad:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_high_load(self):
        f = _make_features(
            pause_frequency=3.0,
            rhythm_regularity=0.3,
            jitter=0.1,
            energy_mean=0.04,
            pitch_std=60,
        )
        cl = self.a._assess_cognitive_load(f)
        assert cl >= 0.8

    def test_low_load(self):
        f = _make_features(
            pause_frequency=0.5,
            rhythm_regularity=0.9,
            jitter=0.02,
            energy_mean=0.1,
            pitch_std=15,
        )
        cl = self.a._assess_cognitive_load(f)
        assert cl == 0.0


class TestCulturalMarkers:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_american(self):
        f = _make_features(pitch_mean=175, rhythm_regularity=0.8)
        m = self.a._identify_cultural_markers(f)
        assert m["american"] > 0

    def test_british(self):
        f = _make_features(pitch_mean=210, pitch_std=30, rhythm_regularity=0.3)
        m = self.a._identify_cultural_markers(f)
        assert m["british"] > 0

    def test_australian(self):
        f = _make_features(
            pitch_mean=130, energy_mean=0.12, rhythm_regularity=0.3, pitch_std=50
        )
        m = self.a._identify_cultural_markers(f)
        assert m["australian"] > 0

    def test_other(self):
        f = _make_features(
            pitch_mean=155, energy_mean=0.04, rhythm_regularity=0.4, pitch_std=50
        )
        m = self.a._identify_cultural_markers(f)
        assert m["other"] > 0


class TestPersonality:
    def setup_method(self):
        self.a = AdvancedVoiceAnalyzer()

    def test_extraversion(self):
        f = _make_features(energy_mean=0.12, pitch_mean=200, rhythm_regularity=0.8)
        p = self.a._infer_personality_traits(f)
        assert p["extraversion"] > 0

    def test_agreeableness(self):
        f = _make_features(pitch_mean=180, rhythm_regularity=0.7, jitter=0.03)
        p = self.a._infer_personality_traits(f)
        assert p["agreeableness"] > 0

    def test_conscientiousness(self):
        f = _make_features(rhythm_regularity=0.8, jitter=0.03, energy_mean=0.07)
        p = self.a._infer_personality_traits(f)
        assert p["conscientiousness"] > 0

    def test_neuroticism(self):
        f = _make_features(jitter=0.1, rhythm_regularity=0.3, pitch_std=70)
        p = self.a._infer_personality_traits(f)
        assert p["neuroticism"] > 0

    def test_openness(self):
        f = _make_features(pitch_std=60, energy_mean=0.08)
        p = self.a._infer_personality_traits(f)
        assert p["openness"] > 0


class TestInferSubtextIntegration:
    """End-to-end infer_subtext call."""

    def test_full_subtext_inference(self):
        a = AdvancedVoiceAnalyzer()
        f = _make_features(
            pitch_mean=220,
            pitch_std=65,
            energy_mean=0.12,
            arousal=0.8,
            valence=-0.4,
            jitter=0.09,
            shimmer=0.16,
            hnr=8.0,
            rhythm_regularity=0.3,
            pause_frequency=3.5,
            tempo=140,
            dominance=0.6,
        )
        st = a.infer_subtext(f)
        assert isinstance(st, SubtextInference)
        assert st.urgency_level > 0.5
        assert st.cognitive_load > 0
        assert sum(st.emotional_state.values()) == pytest.approx(1.0, abs=0.01)


class TestDefaultFeatures:
    def test_default_features(self):
        a = AdvancedVoiceAnalyzer()
        f = a._get_default_features()
        assert f.pitch_mean == 0.0
        assert f.valence == 0.0
        assert len(f.mfcc_mean) == 13
