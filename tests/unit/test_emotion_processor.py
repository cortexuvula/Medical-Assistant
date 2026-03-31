"""
Tests for src/ai/emotion_processor.py — pure module-level functions only.
V2 paths that import settings_manager or SpeakerEmotionAnalyzer are excluded.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from ai.emotion_processor import (
    _format_timestamp,
    _is_v2,
    _validate_emotion_data,
    _get_top_emotions,
    _format_soap_v1,
    _format_panel_v1,
    _generate_clinical_notes,
    get_dominant_emotions,
    format_emotion_for_soap,
    format_emotion_for_panel,
    CLINICAL_EMOTIONS,
    CLINICAL_DESCRIPTORS,
)


# ---------------------------------------------------------------------------
# TestFormatTimestamp
# ---------------------------------------------------------------------------

class TestFormatTimestamp:
    def test_zero(self):
        assert _format_timestamp(0.0) == "00:00"

    def test_exactly_one_minute(self):
        assert _format_timestamp(60.0) == "01:00"

    def test_one_minute_thirty_seconds(self):
        assert _format_timestamp(90.0) == "01:30"

    def test_sixty_minutes(self):
        # 3600 seconds = 60 minutes, 0 seconds
        assert _format_timestamp(3600.0) == "60:00"

    def test_five_seconds(self):
        assert _format_timestamp(5.0) == "00:05"

    def test_truncates_fractional_seconds(self):
        # 65.5 => 1 min 5.5 sec => truncated to 1 min 5 sec
        assert _format_timestamp(65.5) == "01:05"

    def test_truncates_at_boundary(self):
        # 125.9 => 2 min 5.9 sec => truncated to 2 min 5 sec
        assert _format_timestamp(125.9) == "02:05"

    def test_single_digit_seconds(self):
        assert _format_timestamp(9.0) == "00:09"

    def test_ten_minutes(self):
        assert _format_timestamp(600.0) == "10:00"

    def test_one_minute_one_second(self):
        assert _format_timestamp(61.0) == "01:01"


# ---------------------------------------------------------------------------
# TestIsV2
# ---------------------------------------------------------------------------

class TestIsV2:
    def test_version_2_int(self):
        assert _is_v2({"version": 2}) is True

    def test_version_1(self):
        assert _is_v2({"version": 1}) is False

    def test_empty_dict(self):
        assert _is_v2({}) is False

    def test_none(self):
        assert _is_v2(None) is False

    def test_version_2_with_extra_keys(self):
        assert _is_v2({"version": 2, "other": "data"}) is True

    def test_version_string_two(self):
        # String "2" is not equal to int 2
        assert _is_v2({"version": "2"}) is False

    def test_list(self):
        assert _is_v2([]) is False

    def test_plain_string(self):
        assert _is_v2("string") is False


# ---------------------------------------------------------------------------
# TestValidateEmotionData
# ---------------------------------------------------------------------------

class TestValidateEmotionData:
    def test_none(self):
        assert _validate_emotion_data(None) is False

    def test_empty_dict(self):
        assert _validate_emotion_data({}) is False

    def test_empty_segments_list(self):
        assert _validate_emotion_data({"segments": []}) is False

    def test_segments_none(self):
        assert _validate_emotion_data({"segments": None}) is False

    def test_segments_not_a_list(self):
        assert _validate_emotion_data({"segments": "not a list"}) is False

    def test_valid_single_segment(self):
        assert _validate_emotion_data({"segments": [{"emotions": {}}]}) is True

    def test_list_instead_of_dict(self):
        assert _validate_emotion_data([]) is False

    def test_plain_string(self):
        assert _validate_emotion_data("string") is False

    def test_no_segments_key(self):
        assert _validate_emotion_data({"other": "key"}) is False

    def test_segments_list_with_items(self):
        assert _validate_emotion_data({"segments": [1, 2, 3]}) is True


# ---------------------------------------------------------------------------
# TestGetTopEmotions
# ---------------------------------------------------------------------------

class TestGetTopEmotions:
    def test_empty_dict(self):
        assert _get_top_emotions({}) == []

    def test_none(self):
        assert _get_top_emotions(None) == []

    def test_two_emotions_returned_in_order(self):
        result = _get_top_emotions({"anxiety": 0.8, "calm": 0.5})
        assert result == [("anxiety", 0.8), ("calm", 0.5)]

    def test_neutral_excluded(self):
        result = _get_top_emotions({"neutral": 0.9, "anxiety": 0.8})
        assert result == [("anxiety", 0.8)]

    def test_below_default_threshold_excluded(self):
        result = _get_top_emotions({"anxiety": 0.05})
        assert result == []

    def test_exactly_at_threshold(self):
        result = _get_top_emotions({"anxiety": 0.1})
        assert result == [("anxiety", 0.1)]

    def test_top_n_limit(self):
        result = _get_top_emotions({"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.6}, n=2)
        assert result == [("a", 0.9), ("b", 0.8)]

    def test_sorted_descending(self):
        result = _get_top_emotions({"anxiety": 0.5, "calm": 0.8})
        assert result == [("calm", 0.8), ("anxiety", 0.5)]

    def test_custom_threshold_excludes(self):
        result = _get_top_emotions({"anxiety": 0.29}, threshold=0.3)
        assert result == []

    def test_non_numeric_score_excluded(self):
        result = _get_top_emotions({"anxiety": "high"})
        assert result == []

    def test_non_dict_input(self):
        assert _get_top_emotions(["anxiety", "calm"]) == []


# ---------------------------------------------------------------------------
# TestGenerateClinicalNotes
# ---------------------------------------------------------------------------

class TestGenerateClinicalNotes:
    def test_empty_segments(self):
        assert _generate_clinical_notes([], {}) == []

    def test_non_dict_segments_ignored(self):
        # All non-dict => total_segments=0, no notes generated
        result = _generate_clinical_notes(["not a dict", 42], {})
        assert result == []

    def test_anxiety_100_percent_triggers_note(self):
        segments = [{"emotions": {"anxiety": 0.4}}]
        notes = _generate_clinical_notes(segments, {})
        assert any("anxiety" in n.lower() for n in notes)

    def test_anxiety_below_threshold_no_note(self):
        segments = [{"emotions": {"anxiety": 0.39}}]
        notes = _generate_clinical_notes(segments, {})
        assert not any("anxiety" in n.lower() for n in notes)

    def test_anxiety_exactly_50_percent_triggers_note(self):
        # 1 of 2 segments = 50% >= 0.5
        segments = [
            {"emotions": {"anxiety": 0.4}},
            {"emotions": {"calm": 0.9}},
        ]
        notes = _generate_clinical_notes(segments, {})
        assert any("anxiety" in n.lower() for n in notes)

    def test_fear_30_percent_triggers_note(self):
        # 1 of 1 segment = 100% >= 0.3
        segments = [{"emotions": {"fear": 0.4}}]
        notes = _generate_clinical_notes(segments, {})
        assert any("fear" in n.lower() for n in notes)

    def test_sadness_50_percent_triggers_depression_note(self):
        segments = [{"emotions": {"sadness": 0.4}}]
        notes = _generate_clinical_notes(segments, {})
        assert any("depression" in n.lower() or "phq" in n.lower() for n in notes)

    def test_high_variability_triggers_note(self):
        segments = [{"emotions": {"anxiety": 0.2}}]
        overall = {"emotion_variability": 0.7}
        notes = _generate_clinical_notes(segments, overall)
        assert any("variability" in n.lower() for n in notes)

    def test_variability_exactly_0_6_no_note(self):
        # 0.6 is NOT > 0.6, so no variability note
        segments = [{"emotions": {"anxiety": 0.2}}]
        overall = {"emotion_variability": 0.6}
        notes = _generate_clinical_notes(segments, overall)
        assert not any("variability" in n.lower() for n in notes)

    def test_empty_overall_no_variability_note(self):
        segments = [{"emotions": {"anxiety": 0.2}}]
        notes = _generate_clinical_notes(segments, {})
        assert not any("variability" in n.lower() for n in notes)

    def test_multiple_conditions_produce_multiple_notes(self):
        segments = [
            {"emotions": {"anxiety": 0.5, "sadness": 0.5, "fear": 0.5}},
        ]
        overall = {"emotion_variability": 0.9}
        notes = _generate_clinical_notes(segments, overall)
        assert len(notes) >= 3


# ---------------------------------------------------------------------------
# TestGetDominantEmotions
# ---------------------------------------------------------------------------

class TestGetDominantEmotions:
    # --- Invalid / edge inputs ---

    def test_none_input(self):
        assert get_dominant_emotions(None) == []

    def test_invalid_structure(self):
        assert get_dominant_emotions({}) == []

    # --- V1 cases ---

    def test_v1_single_segment_returns_entry(self):
        data = {"segments": [{"emotions": {"anxiety": 0.8}, "start_time": 0.0}]}
        result = get_dominant_emotions(data)
        assert len(result) == 1
        assert result[0]["emotion"] == "anxiety"
        assert result[0]["confidence"] == 0.8
        assert result[0]["segment_index"] == 0
        assert result[0]["timestamp"] == 0.0

    def test_v1_below_threshold_excluded(self):
        data = {"segments": [{"emotions": {"anxiety": 0.29}, "start_time": 0.0}]}
        result = get_dominant_emotions(data, threshold=0.3)
        assert result == []

    def test_v1_neutral_excluded(self):
        data = {"segments": [{"emotions": {"neutral": 0.9}, "start_time": 0.0}]}
        result = get_dominant_emotions(data)
        assert result == []

    def test_v1_sorted_by_confidence_descending(self):
        data = {
            "segments": [
                {"emotions": {"calm": 0.5, "anxiety": 0.9}, "start_time": 0.0}
            ]
        }
        result = get_dominant_emotions(data)
        confidences = [r["confidence"] for r in result]
        assert confidences == sorted(confidences, reverse=True)

    # --- V2 cases ---

    def test_v2_emotion_label_included(self):
        data = {
            "version": 2,
            "segments": [{"emotion_label": "anxiety", "start_time": 5.0}],
        }
        result = get_dominant_emotions(data)
        assert len(result) == 1
        assert result[0]["emotion"] == "anxiety"
        assert result[0]["confidence"] == 1.0

    def test_v2_empty_label_excluded(self):
        data = {
            "version": 2,
            "segments": [{"emotion_label": "", "start_time": 0.0}],
        }
        result = get_dominant_emotions(data)
        assert result == []

    def test_v2_neutral_excluded(self):
        data = {
            "version": 2,
            "segments": [{"emotion_label": "neutral", "start_time": 0.0}],
        }
        result = get_dominant_emotions(data)
        assert result == []

    def test_v2_timestamp_from_start_time(self):
        data = {
            "version": 2,
            "segments": [{"emotion_label": "fear", "start_time": 120.5}],
        }
        result = get_dominant_emotions(data)
        assert result[0]["timestamp"] == 120.5

    # --- Threshold validation ---

    def test_invalid_threshold_above_1_uses_default(self):
        # Invalid threshold 2.0 => falls back to default 0.3; 0.35 >= 0.3 so included
        data = {"segments": [{"emotions": {"anxiety": 0.35}, "start_time": 0.0}]}
        result = get_dominant_emotions(data, threshold=2.0)
        assert len(result) == 1

    def test_invalid_threshold_below_0_uses_default(self):
        data = {"segments": [{"emotions": {"anxiety": 0.35}, "start_time": 0.0}]}
        result = get_dominant_emotions(data, threshold=-0.1)
        assert len(result) == 1

    def test_custom_threshold_0_5_excludes_below(self):
        data = {"segments": [{"emotions": {"anxiety": 0.4}, "start_time": 0.0}]}
        result = get_dominant_emotions(data, threshold=0.5)
        assert result == []

    # --- Robustness ---

    def test_v1_non_dict_segment_skipped(self):
        data = {
            "segments": [
                "not a dict",
                {"emotions": {"anxiety": 0.8}, "start_time": 0.0},
            ]
        }
        result = get_dominant_emotions(data)
        assert len(result) == 1
        assert result[0]["segment_index"] == 1

    def test_v1_non_numeric_start_time_defaults_to_zero(self):
        data = {"segments": [{"emotions": {"anxiety": 0.8}, "start_time": "bad"}]}
        result = get_dominant_emotions(data)
        assert result[0]["timestamp"] == 0.0


# ---------------------------------------------------------------------------
# TestFormatEmotionForSoap
# ---------------------------------------------------------------------------

class TestFormatEmotionForSoap:
    def test_none_returns_empty(self):
        assert format_emotion_for_soap(None) == ""

    def test_empty_dict_returns_empty(self):
        assert format_emotion_for_soap({}) == ""

    def test_empty_segments_returns_empty(self):
        assert format_emotion_for_soap({"segments": []}) == ""

    def test_v1_no_clinical_emotions_above_threshold_returns_empty(self):
        # Confidence 0.2 is below the SOAP threshold of 0.3
        data = {"segments": [{"emotions": {"anxiety": 0.2}, "start_time": 0.0}]}
        assert format_emotion_for_soap(data) == ""

    def test_v1_anxiety_above_threshold_returns_header(self):
        data = {
            "segments": [
                {"emotions": {"anxiety": 0.8}, "start_time": 0.0, "text": "I feel worried"}
            ]
        }
        result = format_emotion_for_soap(data)
        assert "Voice Emotion Analysis:" in result

    def test_v1_anxiety_result_contains_elevated_anxiety(self):
        data = {
            "segments": [
                {"emotions": {"anxiety": 0.8}, "start_time": 0.0, "text": "I feel worried"}
            ]
        }
        result = format_emotion_for_soap(data)
        assert "Patient exhibited elevated anxiety" in result


# ---------------------------------------------------------------------------
# TestFormatEmotionForPanel
# ---------------------------------------------------------------------------

class TestFormatEmotionForPanel:
    def test_none_returns_no_data_message(self):
        assert format_emotion_for_panel(None) == "No emotion analysis data available."

    def test_empty_dict_returns_no_data_message(self):
        assert format_emotion_for_panel({}) == "No emotion analysis data available."

    def test_v1_data_with_segments_returns_header(self):
        data = {
            "segments": [
                {
                    "emotions": {"anxiety": 0.8},
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "text": "Test text",
                    "speaker": "patient",
                }
            ]
        }
        result = format_emotion_for_panel(data)
        assert "VOICE EMOTION ANALYSIS" in result

    def test_v1_empty_segment_content_still_returns_header(self):
        # Segment passes validation but has no usable emotion/text data
        data = {
            "segments": [{"emotions": {}, "start_time": 0.0, "end_time": 0.0, "text": ""}]
        }
        result = format_emotion_for_panel(data)
        assert "VOICE EMOTION ANALYSIS" in result


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_clinical_emotions_is_set(self):
        assert isinstance(CLINICAL_EMOTIONS, set)

    def test_anxiety_in_clinical_emotions(self):
        assert "anxiety" in CLINICAL_EMOTIONS

    def test_neutral_not_in_clinical_emotions(self):
        assert "neutral" not in CLINICAL_EMOTIONS

    def test_clinical_descriptors_is_dict(self):
        assert isinstance(CLINICAL_DESCRIPTORS, dict)

    def test_anxiety_descriptor(self):
        assert CLINICAL_DESCRIPTORS["anxiety"] == "anxious"

    def test_calm_descriptor(self):
        assert CLINICAL_DESCRIPTORS["calm"] == "calm"

    def test_neutral_in_clinical_descriptors(self):
        assert "neutral" in CLINICAL_DESCRIPTORS
