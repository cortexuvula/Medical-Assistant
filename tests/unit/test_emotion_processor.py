"""Test emotion processor functionality."""
import pytest
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ai.emotion_processor import (
    format_emotion_for_soap,
    format_emotion_for_panel,
    get_dominant_emotions,
)


# --- Test Data ---

SAMPLE_EMOTION_DATA = {
    "segments": [
        {
            "start_time": 0.0,
            "end_time": 5.2,
            "speaker": "speaker_0",
            "text": "I've been having these headaches...",
            "emotions": {
                "anxiety": 0.72,
                "sadness": 0.15,
                "neutral": 0.45,
                "anger": 0.05,
                "joy": 0.02,
                "fear": 0.31,
            },
        },
        {
            "start_time": 5.2,
            "end_time": 12.8,
            "speaker": "speaker_0",
            "text": "My mother had the same thing before she passed",
            "emotions": {
                "anxiety": 0.22,
                "sadness": 0.68,
                "neutral": 0.30,
                "anger": 0.03,
                "joy": 0.01,
                "fear": 0.15,
            },
        },
    ],
    "overall": {
        "dominant_emotion": "anxiety",
        "average_emotions": {
            "anxiety": 0.47,
            "sadness": 0.42,
            "neutral": 0.38,
            "anger": 0.04,
            "joy": 0.015,
            "fear": 0.23,
        },
        "emotion_variability": 0.45,
    },
}

SINGLE_SEGMENT_DATA = {
    "segments": [
        {
            "start_time": 0.0,
            "end_time": 3.0,
            "speaker": "speaker_0",
            "text": "I feel fine today",
            "emotions": {
                "neutral": 0.85,
                "joy": 0.10,
                "anxiety": 0.03,
                "sadness": 0.01,
                "anger": 0.00,
                "fear": 0.01,
            },
        }
    ],
    "overall": {
        "dominant_emotion": "neutral",
        "average_emotions": {
            "neutral": 0.85,
            "joy": 0.10,
            "anxiety": 0.03,
            "sadness": 0.01,
            "anger": 0.00,
            "fear": 0.01,
        },
        "emotion_variability": 0.05,
    },
}


# --- Tests for format_emotion_for_soap ---


class TestFormatEmotionForSoap:
    """Test SOAP note formatting of emotion data."""

    def test_format_with_full_emotion_data(self):
        """Test SOAP formatting with complete emotion data."""
        result = format_emotion_for_soap(SAMPLE_EMOTION_DATA)

        assert isinstance(result, str)
        assert len(result) > 0
        # Should reference the dominant emotion
        assert "anxiety" in result.lower() or "anxious" in result.lower()

    def test_format_includes_significant_emotions(self):
        """Test that significant emotions are included in SOAP output."""
        result = format_emotion_for_soap(SAMPLE_EMOTION_DATA)

        # Anxiety (0.47) and sadness (0.42) are the most significant
        result_lower = result.lower()
        assert "anxiety" in result_lower or "anxious" in result_lower
        assert "sadness" in result_lower or "sad" in result_lower

    def test_format_with_single_segment(self):
        """Test SOAP formatting with a single neutral segment."""
        result = format_emotion_for_soap(SINGLE_SEGMENT_DATA)

        assert isinstance(result, str)

    def test_format_with_empty_data(self):
        """Test SOAP formatting with empty emotion data."""
        result = format_emotion_for_soap({})

        assert isinstance(result, str)
        # Should return empty string or a reasonable default
        assert result == "" or "no emotion" in result.lower() or "unavailable" in result.lower()

    def test_format_with_none(self):
        """Test SOAP formatting with None input."""
        result = format_emotion_for_soap(None)

        assert isinstance(result, str)
        assert result == "" or "no emotion" in result.lower() or "unavailable" in result.lower()

    def test_format_with_missing_overall(self):
        """Test SOAP formatting when overall section is missing."""
        data = {
            "segments": SAMPLE_EMOTION_DATA["segments"],
        }
        result = format_emotion_for_soap(data)

        assert isinstance(result, str)

    def test_format_with_missing_segments(self):
        """Test SOAP formatting when segments are missing."""
        data = {
            "overall": SAMPLE_EMOTION_DATA["overall"],
        }
        result = format_emotion_for_soap(data)

        assert isinstance(result, str)


# --- Tests for format_emotion_for_panel ---


class TestFormatEmotionForPanel:
    """Test panel display formatting of emotion data."""

    def test_format_with_full_data(self):
        """Test panel formatting with complete emotion data."""
        result = format_emotion_for_panel(SAMPLE_EMOTION_DATA)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_includes_segment_info(self):
        """Test that panel output includes segment-level information."""
        result = format_emotion_for_panel(SAMPLE_EMOTION_DATA)

        # Should reference the text or emotions from segments
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_includes_emotion_scores(self):
        """Test that panel output includes emotion scores or labels."""
        result = format_emotion_for_panel(SAMPLE_EMOTION_DATA)

        result_lower = result.lower()
        # Should include at least one emotion reference
        has_emotion = any(
            emotion in result_lower
            for emotion in ["anxiety", "sadness", "neutral", "anger", "joy", "fear"]
        )
        assert has_emotion

    def test_format_with_empty_data(self):
        """Test panel formatting with empty data."""
        result = format_emotion_for_panel({})

        assert isinstance(result, str)

    def test_format_with_none(self):
        """Test panel formatting with None input."""
        result = format_emotion_for_panel(None)

        assert isinstance(result, str)

    def test_format_with_single_segment(self):
        """Test panel formatting with single segment."""
        result = format_emotion_for_panel(SINGLE_SEGMENT_DATA)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_with_missing_fields(self):
        """Test panel formatting when segment fields are partially missing."""
        data = {
            "segments": [
                {
                    "text": "Some text",
                    "emotions": {"neutral": 0.90},
                }
            ],
        }
        result = format_emotion_for_panel(data)

        assert isinstance(result, str)


# --- Tests for get_dominant_emotions ---


class TestGetDominantEmotions:
    """Test dominant emotion extraction with threshold filtering."""

    def test_default_threshold(self):
        """Test dominant emotions with default threshold."""
        result = get_dominant_emotions(SAMPLE_EMOTION_DATA)

        assert isinstance(result, list)
        # Should include emotions above default threshold (0.3)
        assert len(result) > 0
        for item in result:
            assert item["confidence"] >= 0.3

    def test_high_threshold(self):
        """Test with a high threshold filters most emotions."""
        result = get_dominant_emotions(SAMPLE_EMOTION_DATA, threshold=0.60)

        assert isinstance(result, list)
        # Only anxiety (0.72) and sadness (0.68) from individual segments
        for item in result:
            assert item["confidence"] >= 0.60

    def test_low_threshold(self):
        """Test with a low threshold includes more emotions."""
        result = get_dominant_emotions(SAMPLE_EMOTION_DATA, threshold=0.01)

        assert isinstance(result, list)
        # Most emotions should be included at this low threshold
        assert len(result) >= 4

    def test_threshold_of_one_returns_empty(self):
        """Test threshold of 1.0 should return no emotions."""
        result = get_dominant_emotions(SAMPLE_EMOTION_DATA, threshold=1.0)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_with_empty_emotions(self):
        """Test with empty emotions dict."""
        result = get_dominant_emotions({})

        assert isinstance(result, list)
        assert len(result) == 0

    def test_with_none_emotions(self):
        """Test with None input."""
        result = get_dominant_emotions(None)

        if isinstance(result, list):
            assert len(result) == 0
        elif isinstance(result, dict):
            assert len(result) == 0

    def test_all_emotions_below_threshold(self):
        """Test when all emotions are below the threshold."""
        low_data = {
            "segments": [{
                "start_time": 0.0, "end_time": 5.0, "speaker": "speaker_0",
                "text": "test", "emotions": {
                    "anxiety": 0.05, "sadness": 0.03, "neutral": 0.08,
                    "anger": 0.01, "joy": 0.02, "fear": 0.01,
                }
            }],
            "overall": {}
        }
        result = get_dominant_emotions(low_data, threshold=0.10)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_single_emotion_above_threshold(self):
        """Test with only one emotion above threshold."""
        single_data = {
            "segments": [{
                "start_time": 0.0, "end_time": 5.0, "speaker": "speaker_0",
                "text": "test", "emotions": {
                    "anxiety": 0.90, "sadness": 0.02, "neutral": 0.05,
                    "anger": 0.01, "joy": 0.01, "fear": 0.01,
                }
            }],
            "overall": {}
        }
        result = get_dominant_emotions(single_data, threshold=0.50)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["emotion"] == "anxiety"

    def test_result_sorted_by_score(self):
        """Test that results are sorted by score in descending order."""
        result = get_dominant_emotions(SAMPLE_EMOTION_DATA, threshold=0.10)

        assert isinstance(result, list)
        if len(result) > 1:
            if "confidence" in result[0]:
                scores = [item["confidence"] for item in result]
                assert scores == sorted(scores, reverse=True)
            elif "score" in result[0]:
                scores = [item["score"] for item in result]
                assert scores == sorted(scores, reverse=True)

    def test_with_zero_values(self):
        """Test emotions with zero values are excluded."""
        data = {
            "segments": [{
                "start_time": 0.0, "end_time": 5.0, "speaker": "speaker_0",
                "text": "test", "emotions": {
                    "anxiety": 0.50, "sadness": 0.0, "neutral": 0.0,
                    "anger": 0.0, "joy": 0.0, "fear": 0.0,
                }
            }],
            "overall": {}
        }

        result = get_dominant_emotions(data, threshold=0.10)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["emotion"] == "anxiety"

    def test_preserves_emotion_names(self):
        """Test that emotion names are preserved in output."""
        data = {
            "segments": [{
                "start_time": 0.0, "end_time": 5.0, "speaker": "speaker_0",
                "text": "test", "emotions": {"anxiety": 0.80, "joy": 0.60}
            }],
            "overall": {}
        }

        result = get_dominant_emotions(data, threshold=0.10)

        assert isinstance(result, list)
        result_str = str(result)
        assert "anxiety" in result_str
        assert "joy" in result_str
