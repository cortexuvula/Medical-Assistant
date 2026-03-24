"""Tests for per-speaker emotion analysis engine."""
import sys
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ai.emotion_speaker_analyzer import (
    SpeakerEmotionAnalyzer,
    SpeakerRole,
    EmotionDeviation,
    SpeakerProfile,
    EmotionCluster,
    ClinicalFlag,
    EncounterAnalysis,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

V2_TWO_SPEAKER_DATA = {
    "version": 2,
    "segments": [
        {"text": "Hello?", "emotion_label": "calm", "emotion_raw": "Calm",
         "emotions": {"calm": 1.0}, "start_time": 1.0, "end_time": 1.5, "speaker": "speaker_1"},
        {"text": "Hi, it's Dr. Smith. How are you?", "emotion_label": "calm", "emotion_raw": "Calm",
         "emotions": {"calm": 1.0}, "start_time": 2.0, "end_time": 4.0, "speaker": "speaker_2"},
        {"text": "Oh fine, just got him up.", "emotion_label": "calm", "emotion_raw": "Calm",
         "emotions": {"calm": 1.0}, "start_time": 5.0, "end_time": 12.0, "speaker": "speaker_1"},
        {"text": "I got a text from community nurses about a memory test.", "emotion_label": "neutral", "emotion_raw": "Neutral",
         "emotions": {"neutral": 1.0}, "start_time": 12.0, "end_time": 46.0, "speaker": "speaker_2"},
        {"text": "Oh, yeah. Well... I don't know.", "emotion_label": "confusion", "emotion_raw": "Confused",
         "emotions": {"confusion": 1.0}, "start_time": 47.0, "end_time": 49.0, "speaker": "speaker_1"},
        {"text": "Is it difficult to get him into the lab?", "emotion_label": "neutral", "emotion_raw": "Neutral",
         "emotions": {"neutral": 1.0}, "start_time": 51.0, "end_time": 53.0, "speaker": "speaker_2"},
        {"text": "Yes. Yes.", "emotion_label": "calm", "emotion_raw": "Calm",
         "emotions": {"calm": 1.0}, "start_time": 54.0, "end_time": 55.0, "speaker": "speaker_1"},
        {"text": "You said why? Because he can't walk?", "emotion_label": "neutral", "emotion_raw": "Neutral",
         "emotions": {"neutral": 1.0}, "start_time": 57.0, "end_time": 60.0, "speaker": "speaker_2"},
        {"text": "Yeah. He can't walk, getting him in and out of the car.", "emotion_label": "concern", "emotion_raw": "Concerned",
         "emotions": {"concern": 1.0}, "start_time": 61.0, "end_time": 83.0, "speaker": "speaker_1"},
        {"text": "Okay. Well, I'll send the requisition into the lab.", "emotion_label": "neutral", "emotion_raw": "Neutral",
         "emotions": {"neutral": 1.0}, "start_time": 83.0, "end_time": 120.0, "speaker": "speaker_2"},
        {"text": "We have nobody around here to help us.", "emotion_label": "concern", "emotion_raw": "Concerned",
         "emotions": {"concern": 1.0}, "start_time": 121.0, "end_time": 132.0, "speaker": "speaker_1"},
        {"text": "What about senior programs?", "emotion_label": "neutral", "emotion_raw": "Neutral",
         "emotions": {"neutral": 1.0}, "start_time": 137.0, "end_time": 148.0, "speaker": "speaker_2"},
        {"text": "I was thinking of giving them a call.", "emotion_label": "concern", "emotion_raw": "Concerned",
         "emotions": {"concern": 1.0}, "start_time": 150.0, "end_time": 169.0, "speaker": "speaker_1"},
        {"text": "Okay, we'll try to get that done then.", "emotion_label": "calm", "emotion_raw": "Calm",
         "emotions": {"calm": 1.0}, "start_time": 244.0, "end_time": 246.0, "speaker": "speaker_1"},
        {"text": "Okay. All right, I'll place the order now.", "emotion_label": "calm", "emotion_raw": "Calm",
         "emotions": {"calm": 1.0}, "start_time": 247.0, "end_time": 250.0, "speaker": "speaker_2"},
    ],
    "overall": {
        "dominant_emotion": "calm",
        "emotion_distribution": {"calm": 6, "neutral": 5, "concern": 3, "confusion": 1},
        "total_segments": 15,
    },
}


def _default_modulate_settings():
    """Return default modulate settings dict for mocking."""
    return {
        "emotion_cluster_window_seconds": 120,
        "speaker_role_overrides": {},
        "emotion_disclaimer": "Test disclaimer.",
    }


def _mock_settings_get(key, default=None):
    """Mock for settings_manager.get that returns modulate settings."""
    if key == "modulate":
        return _default_modulate_settings()
    return default


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyzeBasic:
    """Basic analyze() return-type and structure tests."""

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_analyze_returns_encounter_analysis(self, mock_sm):
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)
        assert isinstance(result, EncounterAnalysis)
        assert len(result.speakers) == 2
        assert result.total_segments == 15

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_empty_data(self, mock_sm):
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze({})
        assert isinstance(result, EncounterAnalysis)
        assert len(result.speakers) == 0
        assert result.total_segments == 0
        assert result.disclaimer == "Test disclaimer."

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_none_data(self, mock_sm):
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(None)
        assert isinstance(result, EncounterAnalysis)
        assert len(result.speakers) == 0

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_disclaimer_present(self, mock_sm):
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)
        assert result.disclaimer
        assert len(result.disclaimer) > 0


class TestBaselineDetection:
    """Test baseline emotion computation."""

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_baseline_detection(self, mock_sm):
        """speaker_1 has 4 calm segments out of 8 total -> baseline is 'calm'."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        # Find speaker_1 profile
        sp1 = next(s for s in result.speakers if s.speaker_id == "speaker_1")
        assert sp1.baseline_emotion == "calm"
        # 4 calm out of 8 segments (calm at t=1, t=5, t=54, t=244)
        assert sp1.utterance_count == 8
        assert abs(sp1.baseline_ratio - 4 / 8) < 0.01


class TestDeviationFinding:
    """Test deviation detection from baseline."""

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_deviation_finding(self, mock_sm):
        """speaker_1 has 4 deviations: 1 confusion + 3 concern."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        sp1 = next(s for s in result.speakers if s.speaker_id == "speaker_1")
        assert len(sp1.deviations) == 4

        deviation_labels = [d.emotion_label for d in sp1.deviations]
        assert deviation_labels.count("confusion") == 1
        assert deviation_labels.count("concern") == 3


class TestClusterDetection:
    """Test temporal emotion clustering."""

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_cluster_detection_concern(self, mock_sm):
        """3 concern segments within 120s window should form 1 cluster."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        concern_clusters = [
            c for c in result.clusters if c.emotion_label == "concern"
        ]
        assert len(concern_clusters) == 1
        cluster = concern_clusters[0]
        assert cluster.segment_count == 3
        assert cluster.start_time == 61.0
        assert cluster.end_time == 169.0

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_cluster_detection_no_cluster_for_single(self, mock_sm):
        """confusion has only 1 segment, so no cluster should form."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        confusion_clusters = [
            c for c in result.clusters if c.emotion_label == "confusion"
        ]
        assert len(confusion_clusters) == 0


class TestSpeakerRoleInference:
    """Test automatic speaker role assignment."""

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_speaker_role_inference_two_speakers(self, mock_sm):
        """speaker_2 (mostly neutral, longer text) should be CLINICIAN,
        speaker_1 should be PATIENT."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        sp1 = next(s for s in result.speakers if s.speaker_id == "speaker_1")
        sp2 = next(s for s in result.speakers if s.speaker_id == "speaker_2")
        assert sp2.role == SpeakerRole.CLINICIAN
        assert sp1.role == SpeakerRole.PATIENT

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_speaker_role_inference_single_speaker(self, mock_sm):
        """Single speaker defaults to PATIENT."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        single_speaker_data = {
            "segments": [
                {"text": "Hello", "emotion_label": "calm",
                 "start_time": 0, "end_time": 1, "speaker": "speaker_1"},
            ]
        }
        result = analyzer.analyze(single_speaker_data)
        assert len(result.speakers) == 1
        assert result.speakers[0].role == SpeakerRole.PATIENT

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_speaker_role_inference_identical_baseline(self, mock_sm):
        """Two speakers with identical calm baselines and similar text -> both UNKNOWN."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        identical_data = {
            "segments": [
                {"text": "Hello there", "emotion_label": "calm",
                 "start_time": 0, "end_time": 1, "speaker": "speaker_1"},
                {"text": "Hello back", "emotion_label": "calm",
                 "start_time": 1, "end_time": 2, "speaker": "speaker_2"},
                {"text": "How are you", "emotion_label": "calm",
                 "start_time": 2, "end_time": 3, "speaker": "speaker_1"},
                {"text": "I am fine", "emotion_label": "calm",
                 "start_time": 3, "end_time": 4, "speaker": "speaker_2"},
            ]
        }
        result = analyzer.analyze(identical_data)
        for sp in result.speakers:
            assert sp.role == SpeakerRole.UNKNOWN

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_speaker_role_override(self, mock_sm):
        """Manual role override from settings should be applied."""
        def override_settings_get(key, default=None):
            if key == "modulate":
                return {
                    "emotion_cluster_window_seconds": 120,
                    "speaker_role_overrides": {
                        "speaker_1": "clinician",
                        "speaker_2": "caregiver",
                    },
                    "emotion_disclaimer": "Test disclaimer.",
                }
            return default

        mock_sm.get.side_effect = override_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        sp1 = next(s for s in result.speakers if s.speaker_id == "speaker_1")
        sp2 = next(s for s in result.speakers if s.speaker_id == "speaker_2")
        assert sp1.role == SpeakerRole.CLINICIAN
        assert sp2.role == SpeakerRole.CAREGIVER


class TestClinicalFlags:
    """Test clinical flag generation."""

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_clinical_flags_concern_cluster(self, mock_sm):
        """Concern cluster should generate 'Sustained concern' flag."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        concern_flags = [f for f in result.flags if f.emotion == "concern"]
        assert len(concern_flags) >= 1
        assert any("Sustained concern" in f.message for f in concern_flags)

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_clinical_flags_no_diagnostic_language(self, mock_sm):
        """No flag message should contain diagnostic terms."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        FORBIDDEN_TERMS = [
            "screening", "disorder", "PHQ", "GAD", "diagnosis",
            "diagnose", "diagnostic",
        ]
        for flag in result.flags:
            msg_lower = flag.message.lower()
            for term in FORBIDDEN_TERMS:
                assert term.lower() not in msg_lower, (
                    f"Flag message contains forbidden diagnostic term '{term}': "
                    f"{flag.message}"
                )

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_flags_no_negative_findings(self, mock_sm):
        """No flag should contain 'no significant', 'no clinically', 'patient was fine'."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        result = analyzer.analyze(V2_TWO_SPEAKER_DATA)

        FORBIDDEN_PHRASES = [
            "no significant", "no clinically", "patient was fine",
        ]
        for flag in result.flags:
            msg_lower = flag.message.lower()
            for phrase in FORBIDDEN_PHRASES:
                assert phrase not in msg_lower, (
                    f"Flag message contains forbidden phrase '{phrase}': "
                    f"{flag.message}"
                )

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_fear_flag_generation(self, mock_sm):
        """Fear in any segment should generate a flag."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        fear_data = {
            "segments": [
                {"text": "I'm really scared about the results", "emotion_label": "fear",
                 "start_time": 10.0, "end_time": 15.0, "speaker": "speaker_1"},
                {"text": "Everything else is fine", "emotion_label": "calm",
                 "start_time": 16.0, "end_time": 20.0, "speaker": "speaker_1"},
                {"text": "Let me check", "emotion_label": "calm",
                 "start_time": 21.0, "end_time": 25.0, "speaker": "speaker_1"},
            ]
        }
        result = analyzer.analyze(fear_data)
        fear_flags = [f for f in result.flags if f.emotion == "fear"]
        assert len(fear_flags) >= 1
        assert any("Fear detected" in f.message for f in fear_flags)

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_sadness_threshold_flag(self, mock_sm):
        """Sadness in >=30% of utterances should generate a flag."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        sadness_data = {
            "segments": [
                {"text": "I feel so down", "emotion_label": "sadness",
                 "start_time": 0, "end_time": 5, "speaker": "speaker_1"},
                {"text": "Nothing helps", "emotion_label": "sadness",
                 "start_time": 5, "end_time": 10, "speaker": "speaker_1"},
                {"text": "Okay", "emotion_label": "calm",
                 "start_time": 10, "end_time": 15, "speaker": "speaker_1"},
            ]
        }
        result = analyzer.analyze(sadness_data)
        sadness_flags = [f for f in result.flags if f.emotion == "sadness"]
        assert len(sadness_flags) >= 1
        assert any("Sadness noted" in f.message for f in sadness_flags)

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_varied_emotion_flag(self, mock_sm):
        """>=4 distinct non-baseline emotions should generate a 'Varied' flag."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        varied_data = {
            "segments": [
                {"text": "a", "emotion_label": "calm", "start_time": 0, "end_time": 1, "speaker": "s1"},
                {"text": "b", "emotion_label": "calm", "start_time": 1, "end_time": 2, "speaker": "s1"},
                {"text": "c", "emotion_label": "calm", "start_time": 2, "end_time": 3, "speaker": "s1"},
                {"text": "d", "emotion_label": "concern", "start_time": 3, "end_time": 4, "speaker": "s1"},
                {"text": "e", "emotion_label": "fear", "start_time": 4, "end_time": 5, "speaker": "s1"},
                {"text": "f", "emotion_label": "sadness", "start_time": 5, "end_time": 6, "speaker": "s1"},
                {"text": "g", "emotion_label": "confusion", "start_time": 6, "end_time": 7, "speaker": "s1"},
                {"text": "h", "emotion_label": "anger", "start_time": 7, "end_time": 8, "speaker": "s1"},
            ]
        }
        result = analyzer.analyze(varied_data)
        varied_flags = [f for f in result.flags if f.emotion == "varied"]
        assert len(varied_flags) >= 1
        assert any("Varied emotional presentation" in f.message for f in varied_flags)


class TestV1Compatibility:
    """Test backward compatibility with v1 emotion data format."""

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_v1_compatibility(self, mock_sm):
        """v1 data (no emotion_label, has emotions dict) still analyzes correctly."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        v1_data = {
            "segments": [
                {"text": "Hello", "emotions": {"calm": 0.9, "neutral": 0.1},
                 "start_time": 0, "end_time": 1, "speaker": "speaker_1"},
                {"text": "I'm worried", "emotions": {"anxiety": 0.8, "neutral": 0.2},
                 "start_time": 2, "end_time": 3, "speaker": "speaker_1"},
                {"text": "Okay", "emotions": {"calm": 0.95, "neutral": 0.05},
                 "start_time": 4, "end_time": 5, "speaker": "speaker_1"},
            ]
        }
        result = analyzer.analyze(v1_data)
        assert isinstance(result, EncounterAnalysis)
        assert len(result.speakers) == 1
        sp = result.speakers[0]
        assert sp.baseline_emotion == "calm"
        # anxiety segment should be a deviation
        assert any(d.emotion_label == "anxiety" for d in sp.deviations)

    @patch("ai.emotion_speaker_analyzer.settings_manager")
    def test_v1_capitalized_label_mapped(self, mock_sm):
        """v1 data with capitalized emotion_label should map to clinical name."""
        mock_sm.get.side_effect = _mock_settings_get
        analyzer = SpeakerEmotionAnalyzer()
        # Segment with a capitalized v1-style label
        v1_segment = {
            "text": "I feel anxious",
            "emotion_label": "Anxious",
            "emotions": {"anxiety": 0.9},
            "start_time": 0,
            "end_time": 1,
            "speaker": "speaker_1",
        }
        label = analyzer._extract_emotion_label(v1_segment)
        assert label == "anxiety"


class TestHelperMethods:
    """Test individual helper methods directly."""

    def test_group_by_speaker(self):
        analyzer = SpeakerEmotionAnalyzer()
        segments = [
            {"text": "a", "speaker": "s1"},
            {"text": "b", "speaker": "s2"},
            {"text": "c", "speaker": "s1"},
        ]
        groups = analyzer._group_by_speaker(segments)
        assert len(groups) == 2
        assert len(groups["s1"]) == 2
        assert len(groups["s2"]) == 1

    def test_group_by_speaker_missing_speaker_field(self):
        analyzer = SpeakerEmotionAnalyzer()
        segments = [
            {"text": "a"},
            {"text": "b", "speaker": "s1"},
        ]
        groups = analyzer._group_by_speaker(segments)
        assert "unknown" in groups
        assert "s1" in groups

    def test_compute_baseline_empty(self):
        analyzer = SpeakerEmotionAnalyzer()
        baseline, ratio = analyzer._compute_baseline([])
        assert baseline == "neutral"
        assert ratio == 1.0

    def test_find_deviations_all_baseline(self):
        analyzer = SpeakerEmotionAnalyzer()
        segments = [
            (0, {"emotion_label": "calm", "text": "a", "start_time": 0, "end_time": 1}),
            (1, {"emotion_label": "calm", "text": "b", "start_time": 1, "end_time": 2}),
        ]
        deviations = analyzer._find_deviations(segments, "calm")
        assert len(deviations) == 0

    def test_detect_clusters_empty(self):
        analyzer = SpeakerEmotionAnalyzer()
        clusters = analyzer._detect_clusters([])
        assert clusters == []

    def test_detect_clusters_outside_window(self):
        """Two deviations far apart should NOT cluster."""
        analyzer = SpeakerEmotionAnalyzer()
        devs = [
            EmotionDeviation("concern", 10.0, 15.0, "text1", 0),
            EmotionDeviation("concern", 500.0, 505.0, "text2", 1),
        ]
        clusters = analyzer._detect_clusters(devs, window_seconds=120.0)
        assert len(clusters) == 0

    def test_detect_clusters_within_window(self):
        """Two deviations within window should cluster."""
        analyzer = SpeakerEmotionAnalyzer()
        devs = [
            EmotionDeviation("concern", 10.0, 15.0, "text1", 0),
            EmotionDeviation("concern", 50.0, 55.0, "text2", 1),
        ]
        clusters = analyzer._detect_clusters(devs, window_seconds=120.0)
        assert len(clusters) == 1
        assert clusters[0].segment_count == 2

    def test_extract_emotion_label_v2_lowercase(self):
        """v2 lowercase label returned as-is."""
        analyzer = SpeakerEmotionAnalyzer()
        seg = {"emotion_label": "concern", "emotions": {"concern": 1.0}}
        assert analyzer._extract_emotion_label(seg) == "concern"

    def test_extract_emotion_label_fallback_neutral(self):
        """No emotion_label and empty emotions dict should return 'neutral'."""
        analyzer = SpeakerEmotionAnalyzer()
        seg = {"text": "hello"}
        assert analyzer._extract_emotion_label(seg) == "neutral"

    def test_extract_emotion_label_v1_emotions_dict(self):
        """v1 format with only emotions dict should pick max non-neutral."""
        analyzer = SpeakerEmotionAnalyzer()
        seg = {"emotions": {"neutral": 0.3, "sadness": 0.7}}
        assert analyzer._extract_emotion_label(seg) == "sadness"

    def test_extract_emotion_label_v1_all_neutral(self):
        """v1 format where only neutral exists should return 'neutral'."""
        analyzer = SpeakerEmotionAnalyzer()
        seg = {"emotions": {"neutral": 1.0}}
        assert analyzer._extract_emotion_label(seg) == "neutral"
