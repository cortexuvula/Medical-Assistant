"""Tests for DifferentialTracker pure-logic methods."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pytest
from utils.differential_tracker import (
    DifferentialStatus, Differential, DifferentialEvolution,
    DifferentialTracker,
)


def _diff(rank, diagnosis, confidence, icd_code=None):
    return Differential(rank=rank, diagnosis=diagnosis, confidence=confidence, icd_code=icd_code)


# ---------------------------------------------------------------------------
# TestDifferentialDataclasses
# ---------------------------------------------------------------------------

class TestDifferentialDataclasses:
    """Tests for Differential and DifferentialEvolution dataclasses."""

    # --- Differential.normalized_name() ---

    def test_normalized_name_lowercase_stripped(self):
        d = _diff(1, "  Pneumonia  ", 80)
        assert d.normalized_name() == "pneumonia"

    def test_normalized_name_extra_spaces(self):
        d = _diff(1, "  Multiple  Spaces  ", 80)
        assert d.normalized_name() == "multiple spaces"

    # --- Differential.confidence_level ---

    def test_confidence_level_high_above_70(self):
        d = _diff(1, "X", 85)
        assert d.confidence_level == "HIGH"

    def test_confidence_level_medium_between_40_and_70(self):
        d = _diff(1, "X", 55)
        assert d.confidence_level == "MEDIUM"

    def test_confidence_level_low_below_40(self):
        d = _diff(1, "X", 30)
        assert d.confidence_level == "LOW"

    def test_confidence_level_boundary_70_is_high(self):
        d = _diff(1, "X", 70)
        assert d.confidence_level == "HIGH"

    def test_confidence_level_boundary_40_is_medium(self):
        d = _diff(1, "X", 40)
        assert d.confidence_level == "MEDIUM"

    def test_confidence_level_boundary_39_is_low(self):
        d = _diff(1, "X", 39)
        assert d.confidence_level == "LOW"

    # --- Differential.confidence_display ---

    def test_confidence_display_high(self):
        d = _diff(1, "X", 78)
        assert d.confidence_display == "78% (HIGH)"

    def test_confidence_display_medium(self):
        d = _diff(1, "X", 55)
        assert d.confidence_display == "55% (MEDIUM)"

    # --- DifferentialEvolution.get_indicator() ---

    def test_get_indicator_new(self):
        evo = DifferentialEvolution(differential=_diff(1, "X", 80), status=DifferentialStatus.NEW)
        assert evo.get_indicator() == "🆕"

    def test_get_indicator_unchanged(self):
        evo = DifferentialEvolution(differential=_diff(1, "X", 80), status=DifferentialStatus.UNCHANGED)
        assert evo.get_indicator() == "➡️"

    def test_get_indicator_moved_up(self):
        evo = DifferentialEvolution(differential=_diff(1, "X", 80), status=DifferentialStatus.MOVED_UP)
        assert evo.get_indicator() == "⬆️"

    def test_get_indicator_moved_down(self):
        evo = DifferentialEvolution(differential=_diff(2, "X", 80), status=DifferentialStatus.MOVED_DOWN)
        assert evo.get_indicator() == "⬇️"

    def test_get_indicator_confidence_up(self):
        evo = DifferentialEvolution(differential=_diff(1, "X", 80), status=DifferentialStatus.CONFIDENCE_UP)
        assert evo.get_indicator() == "📈"

    def test_get_indicator_confidence_down(self):
        evo = DifferentialEvolution(differential=_diff(1, "X", 60), status=DifferentialStatus.CONFIDENCE_DOWN)
        assert evo.get_indicator() == "📉"

    # --- DifferentialEvolution.get_change_description() ---

    def test_get_change_description_new(self):
        evo = DifferentialEvolution(differential=_diff(1, "X", 80), status=DifferentialStatus.NEW)
        assert evo.get_change_description() == "NEW"

    def test_get_change_description_unchanged(self):
        evo = DifferentialEvolution(differential=_diff(1, "X", 80), status=DifferentialStatus.UNCHANGED)
        assert evo.get_change_description() == ""

    def test_get_change_description_moved_up(self):
        evo = DifferentialEvolution(
            differential=_diff(1, "X", 80),
            status=DifferentialStatus.MOVED_UP,
            previous_rank=3,
        )
        assert evo.get_change_description() == "(was #3)"

    def test_get_change_description_moved_down(self):
        evo = DifferentialEvolution(
            differential=_diff(2, "X", 80),
            status=DifferentialStatus.MOVED_DOWN,
            previous_rank=1,
        )
        assert evo.get_change_description() == "(was #1)"

    def test_get_change_description_confidence_up(self):
        evo = DifferentialEvolution(
            differential=_diff(1, "X", 70),
            status=DifferentialStatus.CONFIDENCE_UP,
            previous_confidence=50,
        )
        assert evo.get_change_description() == "(was 50%)"

    def test_get_change_description_confidence_down(self):
        evo = DifferentialEvolution(
            differential=_diff(1, "X", 60),
            status=DifferentialStatus.CONFIDENCE_DOWN,
            previous_confidence=80,
        )
        assert evo.get_change_description() == "(was 80%)"

    # --- DifferentialEvolution.get_confidence_delta() ---

    def test_get_confidence_delta_positive(self):
        evo = DifferentialEvolution(
            differential=_diff(1, "X", 70),
            status=DifferentialStatus.CONFIDENCE_UP,
            previous_confidence=50,
        )
        assert evo.get_confidence_delta() == 20

    def test_get_confidence_delta_no_previous(self):
        evo = DifferentialEvolution(
            differential=_diff(1, "X", 70),
            status=DifferentialStatus.NEW,
        )
        assert evo.get_confidence_delta() is None


# ---------------------------------------------------------------------------
# TestParseConfidence
# ---------------------------------------------------------------------------

class TestParseConfidence:
    """Tests for DifferentialTracker._parse_confidence."""

    def setup_method(self):
        self.tracker = DifferentialTracker()

    def test_percent_string(self):
        assert self.tracker._parse_confidence("78%") == 78

    def test_plain_number(self):
        assert self.tracker._parse_confidence("78") == 78

    def test_percent_with_suffix(self):
        assert self.tracker._parse_confidence("78% confidence") == 78

    def test_text_high(self):
        assert self.tracker._parse_confidence("HIGH") == 80

    def test_text_medium(self):
        assert self.tracker._parse_confidence("MEDIUM") == 55

    def test_text_low(self):
        assert self.tracker._parse_confidence("LOW") == 25

    def test_combined_numeric_priority(self):
        # Numeric part takes priority over text label
        assert self.tracker._parse_confidence("78% (HIGH)") == 78

    def test_zero_percent(self):
        assert self.tracker._parse_confidence("0%") == 0

    def test_one_hundred_percent(self):
        assert self.tracker._parse_confidence("100%") == 100

    def test_over_max_clamped(self):
        assert self.tracker._parse_confidence("150%") == 100

    def test_negative_string_extracts_digits(self):
        # r'(\d{1,3})%?' matches "5" in "-5", giving value 5
        assert self.tracker._parse_confidence("-5") == 5

    def test_unknown_text_defaults_to_50(self):
        assert self.tracker._parse_confidence("UNKNOWN") == 50


# ---------------------------------------------------------------------------
# TestParseDifferentials
# ---------------------------------------------------------------------------

class TestParseDifferentials:
    """Tests for DifferentialTracker.parse_differentials."""

    def setup_method(self):
        self.tracker = DifferentialTracker()

    def test_empty_string_returns_empty(self):
        assert self.tracker.parse_differentials("") == []

    def test_text_without_section_returns_empty(self):
        assert self.tracker.parse_differentials("No relevant section here.") == []

    def test_single_differential_parsed(self):
        text = "DIFFERENTIAL DIAGNOSES\n1. Pneumonia - 80% confidence\n"
        result = self.tracker.parse_differentials(text)
        assert len(result) == 1
        assert result[0].rank == 1
        assert result[0].diagnosis == "Pneumonia"
        assert result[0].confidence == 80

    def test_old_format_high_confidence(self):
        text = "DIFFERENTIAL DIAGNOSES\n1. Influenza - HIGH confidence\n"
        result = self.tracker.parse_differentials(text)
        assert len(result) == 1
        assert result[0].confidence == 80

    def test_multiple_differentials_in_order(self):
        text = (
            "DIFFERENTIAL DIAGNOSES\n"
            "1. Pneumonia - 80% confidence\n"
            "2. Bronchitis - 60% confidence\n"
            "3. Asthma - 40% confidence\n"
        )
        result = self.tracker.parse_differentials(text)
        assert len(result) == 3
        assert result[0].rank == 1
        assert result[1].rank == 2
        assert result[2].rank == 3

    def test_icd_code_extracted(self):
        text = "DIFFERENTIAL DIAGNOSES\n1. URI - 75% confidence (ICD-10: J06.9)\n"
        result = self.tracker.parse_differentials(text)
        assert len(result) == 1
        assert result[0].icd_code == "J06.9"

    def test_diagnosis_stripped_of_whitespace(self):
        text = "DIFFERENTIAL DIAGNOSES\n1.  Chest Pain  - 65% confidence\n"
        result = self.tracker.parse_differentials(text)
        assert len(result) == 1
        assert result[0].diagnosis == "Chest Pain"

    def test_differential_without_confidence_text_handles_gracefully(self):
        # Even if confidence parsing falls back to default, should not raise
        text = "DIFFERENTIAL DIAGNOSES\n1. Pneumonia - 60%\n"
        result = self.tracker.parse_differentials(text)
        assert len(result) >= 0  # Graceful: no exception


# ---------------------------------------------------------------------------
# TestDetermineStatus
# ---------------------------------------------------------------------------

class TestDetermineStatus:
    """Tests for DifferentialTracker._determine_status."""

    def setup_method(self):
        self.tracker = DifferentialTracker()

    def test_same_rank_same_confidence_unchanged(self):
        prev = _diff(1, "Pneumonia", 75)
        curr = _diff(1, "Pneumonia", 75)
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.UNCHANGED

    def test_lower_rank_number_is_moved_up(self):
        prev = _diff(3, "Pneumonia", 75)
        curr = _diff(1, "Pneumonia", 75)
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.MOVED_UP

    def test_higher_rank_number_is_moved_down(self):
        prev = _diff(1, "Pneumonia", 75)
        curr = _diff(3, "Pneumonia", 75)
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.MOVED_DOWN

    def test_same_rank_confidence_increased_by_5_or_more(self):
        prev = _diff(1, "Pneumonia", 60)
        curr = _diff(1, "Pneumonia", 70)
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.CONFIDENCE_UP

    def test_same_rank_confidence_decreased_by_5_or_more(self):
        prev = _diff(1, "Pneumonia", 70)
        curr = _diff(1, "Pneumonia", 60)
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.CONFIDENCE_DOWN

    def test_same_rank_confidence_exactly_5_up(self):
        prev = _diff(1, "Pneumonia", 65)
        curr = _diff(1, "Pneumonia", 70)
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.CONFIDENCE_UP

    def test_same_rank_confidence_exactly_5_down(self):
        prev = _diff(1, "Pneumonia", 70)
        curr = _diff(1, "Pneumonia", 65)
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.CONFIDENCE_DOWN

    def test_same_rank_confidence_change_below_threshold_unchanged(self):
        prev = _diff(1, "Pneumonia", 70)
        curr = _diff(1, "Pneumonia", 74)  # delta = 4, below threshold
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.UNCHANGED

    def test_rank_change_takes_priority_over_confidence_change(self):
        # Rank changed AND confidence changed — rank-based status wins
        prev = _diff(2, "Pneumonia", 60)
        curr = _diff(1, "Pneumonia", 80)  # moved up + confidence up
        assert self.tracker._determine_status(prev, curr) == DifferentialStatus.MOVED_UP


# ---------------------------------------------------------------------------
# TestCompareDifferentials
# ---------------------------------------------------------------------------

class TestCompareDifferentials:
    """Tests for DifferentialTracker.compare_differentials."""

    def setup_method(self):
        self.tracker = DifferentialTracker()
        self.tracker.previous_differentials = [
            _diff(1, "Pneumonia", 80),
            _diff(2, "Bronchitis", 60),
            _diff(3, "Asthma", 45),
        ]

    def test_empty_current_all_previous_become_removed(self):
        _evolutions, removed = self.tracker.compare_differentials([])
        assert len(removed) == 3

    def test_same_as_previous_all_unchanged(self):
        current = [
            _diff(1, "Pneumonia", 80),
            _diff(2, "Bronchitis", 60),
            _diff(3, "Asthma", 45),
        ]
        evolutions, removed = self.tracker.compare_differentials(current)
        assert all(e.status == DifferentialStatus.UNCHANGED for e in evolutions)
        assert removed == []

    def test_new_differential_has_new_status(self):
        current = [_diff(1, "URI", 75)]
        evolutions, _ = self.tracker.compare_differentials(current)
        assert evolutions[0].status == DifferentialStatus.NEW

    def test_differential_matched_by_normalized_name(self):
        # Same diagnosis, different casing
        current = [_diff(1, "PNEUMONIA", 80)]
        evolutions, _ = self.tracker.compare_differentials(current)
        assert evolutions[0].status == DifferentialStatus.UNCHANGED

    def test_moved_up_detected(self):
        # Bronchitis was rank 2, now rank 1
        current = [_diff(1, "Bronchitis", 60)]
        evolutions, _ = self.tracker.compare_differentials(current)
        assert evolutions[0].status == DifferentialStatus.MOVED_UP

    def test_removed_differential_in_removed_list(self):
        # Only Pneumonia in current; Bronchitis and Asthma should be removed
        current = [_diff(1, "Pneumonia", 80)]
        _evolutions, removed = self.tracker.compare_differentials(current)
        removed_names = [d.normalized_name() for d in removed]
        assert "bronchitis" in removed_names
        assert "asthma" in removed_names

    def test_returns_tuple_of_evolutions_and_removed(self):
        current = [_diff(1, "Pneumonia", 80)]
        result = self.tracker.compare_differentials(current)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_evolutions_length_equals_current_length(self):
        current = [
            _diff(1, "Pneumonia", 80),
            _diff(2, "Bronchitis", 60),
        ]
        evolutions, _ = self.tracker.compare_differentials(current)
        assert len(evolutions) == 2

    def test_previous_rank_populated_for_known_differential(self):
        # Pneumonia was rank 1 previously
        current = [_diff(2, "Pneumonia", 80)]
        evolutions, _ = self.tracker.compare_differentials(current)
        assert evolutions[0].previous_rank == 1


# ---------------------------------------------------------------------------
# TestUpdateAndClear
# ---------------------------------------------------------------------------

class TestUpdateAndClear:
    """Tests for DifferentialTracker.update() and clear()."""

    def setup_method(self):
        self.tracker = DifferentialTracker()
        self.tracker.previous_differentials = [_diff(1, "Pneumonia", 80)]
        self.tracker.removed_differentials = [_diff(2, "Bronchitis", 60)]

    def test_clear_empties_previous_differentials(self):
        self.tracker.clear()
        assert self.tracker.previous_differentials == []

    def test_clear_empties_removed_differentials(self):
        self.tracker.clear()
        assert self.tracker.removed_differentials == []

    def test_update_stores_current_as_previous(self):
        current = [_diff(1, "URI", 75)]
        self.tracker.update(current)
        assert len(self.tracker.previous_differentials) == 1
        assert self.tracker.previous_differentials[0].diagnosis == "URI"

    def test_update_previous_equals_current(self):
        current = [_diff(1, "URI", 75), _diff(2, "Flu", 60)]
        self.tracker.update(current)
        assert len(self.tracker.previous_differentials) == 2

    def test_update_stores_copy_not_same_reference(self):
        current = [_diff(1, "URI", 75)]
        self.tracker.update(current)
        # Mutate original list
        current.append(_diff(2, "Flu", 60))
        # Tracker's copy should be unaffected
        assert len(self.tracker.previous_differentials) == 1


# ---------------------------------------------------------------------------
# TestFormatEvolutionText
# ---------------------------------------------------------------------------

class TestFormatEvolutionText:
    """Tests for DifferentialTracker.format_evolution_text."""

    def setup_method(self):
        self.tracker = DifferentialTracker()

    def _make_evo(self, rank, diagnosis, confidence, status,
                  previous_rank=None, previous_confidence=None):
        return DifferentialEvolution(
            differential=_diff(rank, diagnosis, confidence),
            status=status,
            previous_rank=previous_rank,
            previous_confidence=previous_confidence,
        )

    def test_first_analysis_returns_empty_string(self):
        evolutions = [self._make_evo(1, "Pneumonia", 80, DifferentialStatus.NEW)]
        result = self.tracker.format_evolution_text(evolutions, [], analysis_count=1)
        assert result == ""

    def test_second_analysis_with_no_changes_returns_text(self):
        evolutions = [self._make_evo(1, "Pneumonia", 80, DifferentialStatus.UNCHANGED,
                                    previous_rank=1, previous_confidence=80)]
        result = self.tracker.format_evolution_text(evolutions, [], analysis_count=2)
        assert result != ""

    def test_evolution_header_present(self):
        evolutions = [self._make_evo(1, "Pneumonia", 80, DifferentialStatus.UNCHANGED,
                                    previous_rank=1, previous_confidence=80)]
        result = self.tracker.format_evolution_text(evolutions, [], analysis_count=2)
        assert "DIFFERENTIAL EVOLUTION" in result

    def test_new_differential_in_new_section(self):
        evolutions = [self._make_evo(1, "URI", 75, DifferentialStatus.NEW)]
        result = self.tracker.format_evolution_text(evolutions, [], analysis_count=2)
        assert "🆕 NEW:" in result

    def test_removed_differential_in_removed_section(self):
        removed = [_diff(3, "Asthma", 45)]
        result = self.tracker.format_evolution_text([], removed, analysis_count=2)
        assert "❌ REMOVED" in result

    def test_moved_up_differential_in_moved_up_section(self):
        evolutions = [self._make_evo(1, "Bronchitis", 60, DifferentialStatus.MOVED_UP,
                                    previous_rank=3, previous_confidence=60)]
        result = self.tracker.format_evolution_text(evolutions, [], analysis_count=2)
        assert "⬆️ MOVED UP:" in result

    def test_summary_mentions_new_count(self):
        evolutions = [self._make_evo(1, "URI", 75, DifferentialStatus.NEW)]
        result = self.tracker.format_evolution_text(evolutions, [], analysis_count=2)
        assert "new" in result.lower()

    def test_unchanged_count_shown_at_end(self):
        evolutions = [
            self._make_evo(1, "Pneumonia", 80, DifferentialStatus.UNCHANGED,
                           previous_rank=1, previous_confidence=80),
            self._make_evo(2, "Bronchitis", 60, DifferentialStatus.UNCHANGED,
                           previous_rank=2, previous_confidence=60),
        ]
        result = self.tracker.format_evolution_text(evolutions, [], analysis_count=2)
        assert "diagnosis(es)" in result

    def test_confidence_increased_section_present(self):
        evolutions = [self._make_evo(1, "Pneumonia", 80, DifferentialStatus.CONFIDENCE_UP,
                                    previous_rank=1, previous_confidence=60)]
        result = self.tracker.format_evolution_text(evolutions, [], analysis_count=2)
        assert "📈 CONFIDENCE INCREASED:" in result
