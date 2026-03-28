"""Tests for utils.differential_tracker — DifferentialTracker, Differential, DifferentialEvolution."""

import pytest
from utils.differential_tracker import (
    Differential,
    DifferentialEvolution,
    DifferentialStatus,
    DifferentialTracker,
)


# ── Differential ──────────────────────────────────────────────────────────────

class TestDifferential:
    def test_normalized_name_lowercases(self):
        d = Differential(rank=1, diagnosis="Pneumonia", confidence=80)
        assert d.normalized_name() == "pneumonia"

    def test_normalized_name_strips_whitespace(self):
        d = Differential(rank=1, diagnosis="  MI  ", confidence=70)
        assert d.normalized_name() == "mi"

    def test_normalized_name_collapses_spaces(self):
        d = Differential(rank=1, diagnosis="Acute  MI", confidence=70)
        assert d.normalized_name() == "acute mi"

    def test_confidence_level_high(self):
        d = Differential(rank=1, diagnosis="X", confidence=70)
        assert d.confidence_level == "HIGH"

    def test_confidence_level_medium(self):
        d = Differential(rank=1, diagnosis="X", confidence=55)
        assert d.confidence_level == "MEDIUM"

    def test_confidence_level_low(self):
        d = Differential(rank=1, diagnosis="X", confidence=39)
        assert d.confidence_level == "LOW"

    def test_confidence_display_format(self):
        d = Differential(rank=1, diagnosis="X", confidence=78)
        assert d.confidence_display == "78% (HIGH)"

    def test_icd_code_defaults_none(self):
        d = Differential(rank=1, diagnosis="X", confidence=50)
        assert d.icd_code is None

    def test_supporting_defaults_empty(self):
        d = Differential(rank=1, diagnosis="X", confidence=50)
        assert d.supporting == ""

    def test_against_defaults_empty(self):
        d = Differential(rank=1, diagnosis="X", confidence=50)
        assert d.against == ""


# ── DifferentialEvolution ─────────────────────────────────────────────────────

class TestDifferentialEvolution:
    def _make(self, status, prev_rank=None, prev_conf=None, confidence=50):
        diff = Differential(rank=2, diagnosis="Test Dx", confidence=confidence)
        return DifferentialEvolution(
            differential=diff,
            status=status,
            previous_rank=prev_rank,
            previous_confidence=prev_conf,
        )

    def test_indicator_new(self):
        evo = self._make(DifferentialStatus.NEW)
        assert "🆕" in evo.get_indicator()

    def test_indicator_unchanged(self):
        evo = self._make(DifferentialStatus.UNCHANGED)
        assert "➡️" in evo.get_indicator()

    def test_indicator_moved_up(self):
        evo = self._make(DifferentialStatus.MOVED_UP)
        assert "⬆️" in evo.get_indicator()

    def test_indicator_moved_down(self):
        evo = self._make(DifferentialStatus.MOVED_DOWN)
        assert "⬇️" in evo.get_indicator()

    def test_indicator_confidence_up(self):
        evo = self._make(DifferentialStatus.CONFIDENCE_UP)
        assert "📈" in evo.get_indicator()

    def test_indicator_confidence_down(self):
        evo = self._make(DifferentialStatus.CONFIDENCE_DOWN)
        assert "📉" in evo.get_indicator()

    def test_description_new(self):
        evo = self._make(DifferentialStatus.NEW)
        assert evo.get_change_description() == "NEW"

    def test_description_unchanged_empty(self):
        evo = self._make(DifferentialStatus.UNCHANGED)
        assert evo.get_change_description() == ""

    def test_description_moved_up_shows_prev_rank(self):
        evo = self._make(DifferentialStatus.MOVED_UP, prev_rank=3)
        assert "#3" in evo.get_change_description()

    def test_description_moved_down_shows_prev_rank(self):
        evo = self._make(DifferentialStatus.MOVED_DOWN, prev_rank=1)
        assert "#1" in evo.get_change_description()

    def test_description_confidence_up_shows_prev_conf(self):
        evo = self._make(DifferentialStatus.CONFIDENCE_UP, prev_conf=60)
        assert "60%" in evo.get_change_description()

    def test_description_confidence_down_shows_prev_conf(self):
        evo = self._make(DifferentialStatus.CONFIDENCE_DOWN, prev_conf=80)
        assert "80%" in evo.get_change_description()

    def test_confidence_delta_calculated(self):
        evo = self._make(DifferentialStatus.CONFIDENCE_UP, prev_conf=60, confidence=75)
        assert evo.get_confidence_delta() == 15

    def test_confidence_delta_none_when_no_previous(self):
        evo = self._make(DifferentialStatus.NEW)
        assert evo.get_confidence_delta() is None


# ── DifferentialTracker._parse_confidence ────────────────────────────────────

class TestParseConfidence:
    @pytest.fixture
    def tracker(self):
        return DifferentialTracker()

    def test_numeric_with_percent(self, tracker):
        assert tracker._parse_confidence("78%") == 78

    def test_numeric_without_percent(self, tracker):
        assert tracker._parse_confidence("65") == 65

    def test_numeric_with_text(self, tracker):
        assert tracker._parse_confidence("78% confidence") == 78

    def test_numeric_combined_format(self, tracker):
        assert tracker._parse_confidence("78% (HIGH)") == 78

    def test_text_high(self, tracker):
        assert tracker._parse_confidence("HIGH") == 80

    def test_text_medium(self, tracker):
        assert tracker._parse_confidence("MEDIUM") == 55

    def test_text_low(self, tracker):
        assert tracker._parse_confidence("LOW") == 25

    def test_text_case_insensitive(self, tracker):
        assert tracker._parse_confidence("high") == 80

    def test_unknown_defaults_to_50(self, tracker):
        assert tracker._parse_confidence("something_weird") == 50

    def test_clamps_above_100(self, tracker):
        assert tracker._parse_confidence("150%") == 100

    def test_clamps_below_0(self, tracker):
        # "0" is a valid numeric, but negative values don't appear in format
        assert tracker._parse_confidence("0%") == 0


# ── DifferentialTracker.parse_differentials ───────────────────────────────────

SAMPLE_ANALYSIS_NEW = """
DIFFERENTIAL DIAGNOSES

1. Bacterial pneumonia - 85% (HIGH) (ICD-10: J18.9)
   Supporting: fever, cough, infiltrate
   Against: vaccinated

2. Pulmonary embolism - 60% (MEDIUM) (ICD-10: I26.9)
   Supporting: tachycardia

3. Viral URI - 25% (LOW)

RECOMMENDED NEXT STEPS
Order chest CT
"""

SAMPLE_ANALYSIS_OLD = """
DIFFERENTIAL DIAGNOSES

1. Bacterial pneumonia - HIGH confidence
2. Pulmonary embolism - MEDIUM confidence

RECOMMENDED NEXT STEPS
"""


class TestParseDifferentials:
    @pytest.fixture
    def tracker(self):
        return DifferentialTracker()

    def test_parses_count_new_format(self, tracker):
        result = tracker.parse_differentials(SAMPLE_ANALYSIS_NEW)
        assert len(result) == 3

    def test_parses_rank_new_format(self, tracker):
        result = tracker.parse_differentials(SAMPLE_ANALYSIS_NEW)
        assert result[0].rank == 1
        assert result[1].rank == 2

    def test_parses_diagnosis_name(self, tracker):
        result = tracker.parse_differentials(SAMPLE_ANALYSIS_NEW)
        assert "pneumonia" in result[0].diagnosis.lower()

    def test_parses_numeric_confidence(self, tracker):
        result = tracker.parse_differentials(SAMPLE_ANALYSIS_NEW)
        assert result[0].confidence == 85

    def test_parses_icd_code(self, tracker):
        result = tracker.parse_differentials(SAMPLE_ANALYSIS_NEW)
        assert result[0].icd_code == "J18.9"

    def test_parses_old_format_high(self, tracker):
        result = tracker.parse_differentials(SAMPLE_ANALYSIS_OLD)
        assert len(result) >= 1
        assert result[0].confidence == 80  # HIGH → 80

    def test_parses_old_format_medium(self, tracker):
        result = tracker.parse_differentials(SAMPLE_ANALYSIS_OLD)
        assert result[1].confidence == 55  # MEDIUM → 55

    def test_no_section_returns_empty(self, tracker):
        result = tracker.parse_differentials("Patient has fever and cough.")
        assert result == []

    def test_empty_text_returns_empty(self, tracker):
        result = tracker.parse_differentials("")
        assert result == []


# ── DifferentialTracker.compare_differentials ─────────────────────────────────

class TestCompareDifferentials:
    @pytest.fixture
    def tracker(self):
        return DifferentialTracker()

    def _make(self, rank, name, confidence):
        return Differential(rank=rank, diagnosis=name, confidence=confidence)

    def test_all_new_when_no_previous(self, tracker):
        current = [self._make(1, "Pneumonia", 80)]
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].status == DifferentialStatus.NEW

    def test_unchanged_when_same_rank_and_confidence(self, tracker):
        prev = [self._make(1, "Pneumonia", 80)]
        tracker.update(prev)
        current = [self._make(1, "Pneumonia", 80)]
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].status == DifferentialStatus.UNCHANGED

    def test_moved_up_when_rank_decreased(self, tracker):
        prev = [self._make(2, "Pneumonia", 80)]
        tracker.update(prev)
        current = [self._make(1, "Pneumonia", 80)]
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].status == DifferentialStatus.MOVED_UP

    def test_moved_down_when_rank_increased(self, tracker):
        prev = [self._make(1, "Pneumonia", 80)]
        tracker.update(prev)
        current = [self._make(2, "Pneumonia", 80)]
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].status == DifferentialStatus.MOVED_DOWN

    def test_confidence_up_above_threshold(self, tracker):
        prev = [self._make(1, "Pneumonia", 60)]
        tracker.update(prev)
        current = [self._make(1, "Pneumonia", 70)]  # +10 ≥ 5 threshold
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].status == DifferentialStatus.CONFIDENCE_UP

    def test_confidence_down_above_threshold(self, tracker):
        prev = [self._make(1, "Pneumonia", 70)]
        tracker.update(prev)
        current = [self._make(1, "Pneumonia", 60)]  # -10 ≤ -5 threshold
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].status == DifferentialStatus.CONFIDENCE_DOWN

    def test_unchanged_when_confidence_within_threshold(self, tracker):
        prev = [self._make(1, "Pneumonia", 60)]
        tracker.update(prev)
        current = [self._make(1, "Pneumonia", 63)]  # +3 < 5 threshold
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].status == DifferentialStatus.UNCHANGED

    def test_removed_diagnosis_detected(self, tracker):
        prev = [self._make(1, "Pneumonia", 80), self._make(2, "PE", 60)]
        tracker.update(prev)
        current = [self._make(1, "Pneumonia", 80)]
        evols, removed = tracker.compare_differentials(current)
        assert len(removed) == 1
        assert "PE" in removed[0].diagnosis or "pe" in removed[0].normalized_name()

    def test_previous_rank_recorded(self, tracker):
        prev = [self._make(2, "Pneumonia", 80)]
        tracker.update(prev)
        current = [self._make(1, "Pneumonia", 80)]
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].previous_rank == 2

    def test_previous_confidence_recorded(self, tracker):
        prev = [self._make(1, "Pneumonia", 60)]
        tracker.update(prev)
        current = [self._make(1, "Pneumonia", 75)]
        evols, removed = tracker.compare_differentials(current)
        assert evols[0].previous_confidence == 60


# ── DifferentialTracker.update and clear ─────────────────────────────────────

class TestUpdateAndClear:
    def test_update_stores_differentials(self):
        tracker = DifferentialTracker()
        diffs = [Differential(rank=1, diagnosis="X", confidence=70)]
        tracker.update(diffs)
        assert len(tracker.previous_differentials) == 1

    def test_clear_empties_previous(self):
        tracker = DifferentialTracker()
        diffs = [Differential(rank=1, diagnosis="X", confidence=70)]
        tracker.update(diffs)
        tracker.clear()
        assert len(tracker.previous_differentials) == 0

    def test_clear_empties_removed(self):
        tracker = DifferentialTracker()
        tracker.removed_differentials = [Differential(rank=1, diagnosis="X", confidence=50)]
        tracker.clear()
        assert len(tracker.removed_differentials) == 0


# ── DifferentialTracker.format_evolution_text ─────────────────────────────────

class TestFormatEvolutionText:
    @pytest.fixture
    def tracker(self):
        return DifferentialTracker()

    def _make(self, rank, name, confidence):
        return Differential(rank=rank, diagnosis=name, confidence=confidence)

    def _make_evo(self, status, rank, name, confidence, prev_rank=None, prev_conf=None):
        diff = self._make(rank, name, confidence)
        return DifferentialEvolution(
            differential=diff,
            status=status,
            previous_rank=prev_rank,
            previous_confidence=prev_conf,
        )

    def test_first_analysis_returns_empty(self, tracker):
        evols = [self._make_evo(DifferentialStatus.NEW, 1, "Pneumonia", 80)]
        result = tracker.format_evolution_text(evols, [], analysis_count=1)
        assert result == ""

    def test_second_analysis_returns_header(self, tracker):
        evols = [self._make_evo(DifferentialStatus.UNCHANGED, 1, "Pneumonia", 80, 1, 80)]
        result = tracker.format_evolution_text(evols, [], analysis_count=2)
        assert "DIFFERENTIAL EVOLUTION" in result

    def test_new_differential_in_output(self, tracker):
        evols = [self._make_evo(DifferentialStatus.NEW, 1, "Pneumonia", 80)]
        result = tracker.format_evolution_text(evols, [], analysis_count=2)
        assert "NEW" in result
        assert "Pneumonia" in result

    def test_moved_up_in_output(self, tracker):
        evols = [self._make_evo(DifferentialStatus.MOVED_UP, 1, "Pneumonia", 80, prev_rank=2, prev_conf=75)]
        result = tracker.format_evolution_text(evols, [], analysis_count=2)
        assert "MOVED UP" in result

    def test_moved_down_in_output(self, tracker):
        evols = [self._make_evo(DifferentialStatus.MOVED_DOWN, 3, "PE", 50, prev_rank=1, prev_conf=70)]
        result = tracker.format_evolution_text(evols, [], analysis_count=2)
        assert "MOVED DOWN" in result

    def test_removed_in_output(self, tracker):
        removed = [self._make(1, "PE", 70)]
        evols = [self._make_evo(DifferentialStatus.UNCHANGED, 1, "Pneumonia", 80, 1, 80)]
        result = tracker.format_evolution_text(evols, removed, analysis_count=2)
        assert "REMOVED" in result
        assert "PE" in result

    def test_summary_line_present(self, tracker):
        evols = [self._make_evo(DifferentialStatus.NEW, 1, "Pneumonia", 80)]
        result = tracker.format_evolution_text(evols, [], analysis_count=2)
        assert "Summary:" in result

    def test_unchanged_count_in_output(self, tracker):
        evols = [self._make_evo(DifferentialStatus.UNCHANGED, 1, "Pneumonia", 80, 1, 80)]
        result = tracker.format_evolution_text(evols, [], analysis_count=2)
        assert "UNCHANGED" in result
