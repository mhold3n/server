#!/usr/bin/env python3
"""
Additional feature-extraction coverage for the advanced voice analyzer.
"""

import os
import sys
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

from prompt_middleware.voice.voice_analyzer import AdvancedVoiceAnalyzer, VoiceFeatures


def _prosodic_features():
    return {
        "pitch_mean": 110.0,
        "pitch_std": 12.0,
        "pitch_range": 32.0,
        "pitch_skew": 0.1,
        "pitch_kurtosis": 0.2,
    }


def _rhythm_features():
    return {
        "tempo": 90.0,
        "rhythm_regularity": 0.75,
        "pause_frequency": 1.2,
        "pause_duration_mean": 0.15,
    }


def _energy_features():
    return {
        "energy_mean": 0.08,
        "energy_std": 0.02,
        "energy_skew": 0.3,
        "energy_kurtosis": 0.4,
    }


def _spectral_features():
    return {
        "spectral_centroid_mean": 2200.0,
        "spectral_centroid_std": 120.0,
        "spectral_rolloff_mean": 4400.0,
        "spectral_rolloff_std": 210.0,
        "spectral_bandwidth_mean": 980.0,
        "spectral_bandwidth_std": 75.0,
        "zero_crossing_rate_mean": 0.12,
        "zero_crossing_rate_std": 0.03,
    }


def _mfcc_features():
    return {
        "mfcc_mean": np.arange(13, dtype=float),
        "mfcc_std": np.ones(13, dtype=float),
    }


def _formant_features():
    return {
        "f1_mean": 500.0,
        "f2_mean": 1500.0,
        "f3_mean": 2500.0,
        "f1_std": 5.0,
        "f2_std": 10.0,
        "f3_std": 15.0,
    }


def _voice_quality_features():
    return {"jitter": 0.03, "shimmer": 0.04, "hnr": 12.0}


def _emotional_features():
    return {"valence": 0.2, "arousal": 0.3, "dominance": 0.4}


class TestAdvancedVoiceFeatureExtraction:
    def setup_method(self):
        self.analyzer = AdvancedVoiceAnalyzer()

    def test_extract_comprehensive_features_success(self):
        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.to_mono",
                return_value=np.ones(8),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.resample",
                return_value=np.ones(16),
            ),
            patch.object(
                self.analyzer,
                "_extract_prosodic_features",
                return_value=_prosodic_features(),
            ),
            patch.object(
                self.analyzer,
                "_extract_rhythm_features",
                return_value=_rhythm_features(),
            ),
            patch.object(
                self.analyzer,
                "_extract_energy_features",
                return_value=_energy_features(),
            ),
            patch.object(
                self.analyzer,
                "_extract_spectral_features",
                return_value=_spectral_features(),
            ),
            patch.object(
                self.analyzer,
                "_extract_mfcc_features",
                return_value=_mfcc_features(),
            ),
            patch.object(
                self.analyzer,
                "_extract_formant_features",
                return_value=_formant_features(),
            ),
            patch.object(
                self.analyzer,
                "_extract_voice_quality_features",
                return_value=_voice_quality_features(),
            ),
            patch.object(
                self.analyzer,
                "_extract_emotional_features",
                return_value=_emotional_features(),
            ),
        ):
            features = self.analyzer.extract_comprehensive_features(np.ones((2, 8)))

        assert isinstance(features, VoiceFeatures)
        assert features.pitch_mean == 110.0
        assert features.tempo == 90.0
        assert features.mfcc_mean.shape == (13,)
        assert features.hnr == 12.0
        assert features.dominance == 0.4

    def test_extract_comprehensive_features_failure_returns_defaults(self):
        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.to_mono",
            side_effect=RuntimeError("boom"),
        ):
            features = self.analyzer.extract_comprehensive_features(np.ones((2, 4)))

        assert isinstance(features, VoiceFeatures)
        assert features.pitch_mean == 0.0
        assert np.array_equal(features.mfcc_mean, np.zeros(13))

    def test_extract_prosodic_features_success(self):
        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.yin",
            return_value=np.array([100.0, 150.0, 200.0, np.nan]),
        ):
            features = self.analyzer._extract_prosodic_features(np.ones(8))

        assert features["pitch_mean"] == 150.0
        assert features["pitch_range"] == 100.0

    def test_extract_prosodic_features_empty_and_error(self):
        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.yin",
            return_value=np.array([np.nan, np.nan]),
        ):
            empty_features = self.analyzer._extract_prosodic_features(np.ones(4))

        assert empty_features["pitch_mean"] == 0.0

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.yin",
            side_effect=RuntimeError("prosody"),
        ):
            error_features = self.analyzer._extract_prosodic_features(np.ones(4))

        assert error_features["pitch_kurtosis"] == 0.0

    def test_extract_rhythm_features_with_pauses(self):
        audio = np.ones(self.analyzer.sample_rate)
        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.beat.beat_track",
                return_value=(120.0, np.array([0, 5, 10])),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.rms",
                return_value=np.array([[1.0, 0.0, 1.0, 0.0]]),
            ),
        ):
            features = self.analyzer._extract_rhythm_features(audio)

        assert features["tempo"] == 120.0
        assert features["rhythm_regularity"] > 0
        assert features["pause_frequency"] > 0

    def test_extract_rhythm_features_without_pauses_and_error(self):
        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.beat.beat_track",
                return_value=(90.0, np.array([0])),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.rms",
                return_value=np.array([[1.0, 1.0, 1.0]]),
            ),
        ):
            features = self.analyzer._extract_rhythm_features(np.ones(32))

        assert features["rhythm_regularity"] == 0.0
        assert features["pause_frequency"] == 0.0

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.beat.beat_track",
            side_effect=RuntimeError("rhythm"),
        ):
            error_features = self.analyzer._extract_rhythm_features(np.ones(4))

        assert error_features["pause_duration_mean"] == 0.0

    def test_extract_energy_features_success_and_error(self):
        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.feature.rms",
            return_value=np.array([[0.5, 1.0, 1.5]]),
        ):
            features = self.analyzer._extract_energy_features(np.ones(8))

        assert features["energy_mean"] == 1.0
        assert features["energy_std"] > 0

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.feature.rms",
            side_effect=RuntimeError("energy"),
        ):
            error_features = self.analyzer._extract_energy_features(np.ones(4))

        assert error_features["energy_kurtosis"] == 0.0

    def test_extract_spectral_features_success_and_error(self):
        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.spectral_centroid",
                return_value=np.array([[1000.0, 2000.0]]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.spectral_rolloff",
                return_value=np.array([[3000.0, 3500.0]]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.spectral_bandwidth",
                return_value=np.array([[500.0, 700.0]]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.zero_crossing_rate",
                return_value=np.array([[0.1, 0.2]]),
            ),
        ):
            features = self.analyzer._extract_spectral_features(np.ones(8))

        assert features["spectral_centroid_mean"] == 1500.0
        assert features["zero_crossing_rate_std"] > 0

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.feature.spectral_centroid",
            side_effect=RuntimeError("spectral"),
        ):
            error_features = self.analyzer._extract_spectral_features(np.ones(4))

        assert error_features["spectral_rolloff_mean"] == 0.0

    def test_extract_mfcc_features_success_and_error(self):
        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.feature.mfcc",
            return_value=np.arange(26, dtype=float).reshape(13, 2),
        ):
            features = self.analyzer._extract_mfcc_features(np.ones(8))

        assert features["mfcc_mean"].shape == (13,)
        assert np.all(features["mfcc_std"] >= 0)

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.feature.mfcc",
            side_effect=RuntimeError("mfcc"),
        ):
            error_features = self.analyzer._extract_mfcc_features(np.ones(4))

        assert np.array_equal(error_features["mfcc_mean"], np.zeros(13))

    def test_extract_formant_features_success_low_peaks_and_error(self):
        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.stft",
                return_value=np.ones((5, 3)),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.fft_frequencies",
                return_value=np.array([100.0, 200.0, 300.0, 400.0, 500.0]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.signal.find_peaks",
                return_value=(np.array([1, 2, 3]), {}),
            ),
        ):
            features = self.analyzer._extract_formant_features(np.ones(8))

        assert features["f1_mean"] == 200.0
        assert features["f3_mean"] == 400.0

        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.stft",
                return_value=np.ones((5, 3)),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.fft_frequencies",
                return_value=np.array([100.0, 200.0, 300.0, 400.0, 500.0]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.signal.find_peaks",
                return_value=(np.array([1]), {}),
            ),
        ):
            low_peak_features = self.analyzer._extract_formant_features(np.ones(8))

        assert low_peak_features["f1_mean"] == 0.0

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.stft",
            side_effect=RuntimeError("formant"),
        ):
            error_features = self.analyzer._extract_formant_features(np.ones(4))

        assert error_features["f2_std"] == 0.0

    def test_extract_voice_quality_features_success_short_pitch_and_error(self):
        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.yin",
                return_value=np.array([100.0, 110.0]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.rms",
                return_value=np.array([[0.5, 1.0, 1.5]]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.spectral_centroid",
                return_value=np.array([[1000.0, 2000.0]]),
            ),
        ):
            features = self.analyzer._extract_voice_quality_features(np.ones(8))

        assert features["jitter"] >= 0
        assert features["shimmer"] > 0
        assert features["hnr"] > 0

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.yin",
            return_value=np.array([100.0, np.nan]),
        ):
            short_features = self.analyzer._extract_voice_quality_features(np.ones(4))

        assert short_features == {"jitter": 0.0, "shimmer": 0.0, "hnr": 0.0}

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.yin",
            side_effect=RuntimeError("voice-quality"),
        ):
            error_features = self.analyzer._extract_voice_quality_features(np.ones(4))

        assert error_features["hnr"] == 0.0

    def test_extract_emotional_features_success_no_pitch_and_error(self):
        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.spectral_centroid",
                return_value=np.array([[2500.0, 2600.0]]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.rms",
                return_value=np.array([[0.2, 0.3]]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.yin",
                return_value=np.array([250.0, 260.0]),
            ),
        ):
            features = self.analyzer._extract_emotional_features(np.ones(8))

        assert features["valence"] > 0
        assert features["arousal"] > 0
        assert features["dominance"] > 0

        with (
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.spectral_centroid",
                return_value=np.array([[2500.0, 2600.0]]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.feature.rms",
                return_value=np.array([[0.2, 0.3]]),
            ),
            patch(
                "prompt_middleware.voice.voice_analyzer.librosa.yin",
                return_value=np.array([np.nan, np.nan]),
            ),
        ):
            no_pitch_features = self.analyzer._extract_emotional_features(np.ones(8))

        assert no_pitch_features["dominance"] == 0.0

        with patch(
            "prompt_middleware.voice.voice_analyzer.librosa.feature.spectral_centroid",
            side_effect=RuntimeError("emotion"),
        ):
            error_features = self.analyzer._extract_emotional_features(np.ones(4))

        assert error_features["arousal"] == 0.0
