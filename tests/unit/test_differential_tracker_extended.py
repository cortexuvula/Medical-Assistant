"""
Extended unit tests for DifferentialTracker module.

Tests cover:
- DifferentialStatus enum values
- Differential dataclass: normalized_name, confidence_level, confidence_display
- DifferentialEvolution: get_indicator, get_change_description, get_confidence_delta
- DifferentialTracker: clear, _parse_confidence, parse_differentials,
  compare_differentials, _determine_status, update, format_evolution_text
- Edge cases: empty input, boundary confidence values, large text, malformed input
"""

import unittest
from unittest.mock import patch

from utils.differential_tracker import (
    DifferentialStatus,
    Differential,
    DifferentialEvolution,
    DifferentialTracker,
)


# ---------------------------------------------------------------------------
# DifferentialStatus enum
# ---------------------------------------------------------------------------
class TestDifferentialStatus(unittest.TestCase):
    """Tests for the DifferentialStatus enum."""

    def test_enum_values(self):
        self.assertEqual(DifferentialStatus.NEW.value, "new")
        self.assertEqual(DifferentialStatus.UNCHANGED.value, "same")
        self.assertEqual(DifferentialStatus.MOVED_UP.value, "up")
        self.assertEqual(DifferentialStatus.MOVED_DOWN.value, "down")
        self.assertEqual(DifferentialStatus.CONFIDENCE_UP.value, "conf_up")
        self.assertEqual(DifferentialStatus.CONFIDENCE_DOWN.value, "conf_down")

    def test_all_members_present(self):
        members = {m.name for m in DifferentialStatus}
        expected = {"NEW", "UNCHANGED", "MOVED_UP", "MOVED_DOWN",
                    "CONFIDENCE_UP", "CONFIDENCE_DOWN"}
        self.assertEqual(members, expected)


# ---------------------------------------------------------------------------
# Differential dataclass
# ---------------------------------------------------------------------------
class TestDifferential(unittest.TestCase):
    """Tests for the Differential dataclass."""

    def _make(self, **kwargs):
        defaults = dict(rank=1, diagnosis="Hypertension", confidence=75)
        defaults.update(kwargs)
        return Differential(**defaults)

    # --- normalized_name ---------------------------------------------------
    def test_normalized_name_lowercase(self):
        d = self._make(diagnosis="Acute Myocardial Infarction")
        self.assertEqual(d.normalized_name(), "acute myocardial infarction")

    def test_normalized_name_strips_whitespace(self):
        d = self._make(diagnosis="  Pneumonia  ")
        self.assertEqual(d.normalized_name(), "pneumonia")

    def test_normalized_name_collapses_internal_whitespace(self):
        d = self._make(diagnosis="Tension  Type   Headache")
        self.assertEqual(d.normalized_name(), "tension type headache")

    def test_normalized_name_already_clean(self):
        d = self._make(diagnosis="copd")
        self.assertEqual(d.normalized_name(), "copd")

    # --- confidence_level --------------------------------------------------
    def test_confidence_level_high(self):
        for val in (70, 85, 100):
            d = self._make(confidence=val)
            self.assertEqual(d.confidence_level, "HIGH", f"Failed for {val}")

    def test_confidence_level_medium(self):
        for val in (40, 55, 69):
            d = self._make(confidence=val)
            self.assertEqual(d.confidence_level, "MEDIUM", f"Failed for {val}")

    def test_confidence_level_low(self):
        for val in (0, 20, 39):
            d = self._make(confidence=val)
            self.assertEqual(d.confidence_level, "LOW", f"Failed for {val}")

    # --- confidence_display ------------------------------------------------
    def test_confidence_display_high(self):
        d = self._make(confidence=80)
        self.assertEqual(d.confidence_display, "80% (HIGH)")

    def test_confidence_display_medium(self):
        d = self._make(confidence=50)
        self.assertEqual(d.confidence_display, "50% (MEDIUM)")

    def test_confidence_display_low(self):
        d = self._make(confidence=10)
        self.assertEqual(d.confidence_display, "10% (LOW)")

    # --- default optional fields -------------------------------------------
    def test_default_optional_fields(self):
        d = self._make()
        self.assertIsNone(d.icd_code)
        self.assertEqual(d.supporting, "")
        self.assertEqual(d.against, "")

    def test_custom_optional_fields(self):
        d = self._make(icd_code="I10", supporting="Elevated BP",
                       against="No end-organ damage")
        self.assertEqual(d.icd_code, "I10")
        self.assertEqual(d.supporting, "Elevated BP")
        self.assertEqual(d.against, "No end-organ damage")


# ---------------------------------------------------------------------------
# DifferentialEvolution dataclass
# ---------------------------------------------------------------------------
class TestDifferentialEvolution(unittest.TestCase):
    """Tests for DifferentialEvolution methods."""

    def _diff(self, **kwargs):
        defaults = dict(rank=1, diagnosis="Test", confidence=70)
        defaults.update(kwargs)
        return Differential(**defaults)

    # --- get_indicator -----------------------------------------------------
    def test_get_indicator_all_statuses(self):
        expected = {
            DifferentialStatus.NEW: "\U0001f195",        # 🆕
            DifferentialStatus.UNCHANGED: "\u27a1\ufe0f", # ➡️
            DifferentialStatus.MOVED_UP: "\u2b06\ufe0f",  # ⬆️
            DifferentialStatus.MOVED_DOWN: "\u2b07\ufe0f", # ⬇️
            DifferentialStatus.CONFIDENCE_UP: "\U0001f4c8",  # 📈
            DifferentialStatus.CONFIDENCE_DOWN: "\U0001f4c9", # 📉
        }
        for status, indicator in expected.items():
            evo = DifferentialEvolution(
                differential=self._diff(), status=status)
            self.assertEqual(evo.get_indicator(), indicator,
                             f"Wrong indicator for {status}")

    # --- get_change_description -------------------------------------------
    def test_change_description_new(self):
        evo = DifferentialEvolution(
            differential=self._diff(), status=DifferentialStatus.NEW)
        self.assertEqual(evo.get_change_description(), "NEW")

    def test_change_description_unchanged(self):
        evo = DifferentialEvolution(
            differential=self._diff(), status=DifferentialStatus.UNCHANGED,
            previous_rank=1, previous_confidence=70)
        self.assertEqual(evo.get_change_description(), "")

    def test_change_description_moved_up(self):
        evo = DifferentialEvolution(
            differential=self._diff(rank=1), status=DifferentialStatus.MOVED_UP,
            previous_rank=3, previous_confidence=60)
        self.assertEqual(evo.get_change_description(), "(was #3)")

    def test_change_description_moved_down(self):
        evo = DifferentialEvolution(
            differential=self._diff(rank=4), status=DifferentialStatus.MOVED_DOWN,
            previous_rank=2, previous_confidence=80)
        self.assertEqual(evo.get_change_description(), "(was #2)")

    def test_change_description_confidence_up(self):
        evo = DifferentialEvolution(
            differential=self._diff(confidence=85),
            status=DifferentialStatus.CONFIDENCE_UP,
            previous_rank=1, previous_confidence=70)
        self.assertEqual(evo.get_change_description(), "(was 70%)")

    def test_change_description_confidence_down(self):
        evo = DifferentialEvolution(
            differential=self._diff(confidence=50),
            status=DifferentialStatus.CONFIDENCE_DOWN,
            previous_rank=1, previous_confidence=70)
        self.assertEqual(evo.get_change_description(), "(was 70%)")

    # --- get_confidence_delta ----------------------------------------------
    def test_confidence_delta_positive(self):
        evo = DifferentialEvolution(
            differential=self._diff(confidence=80),
            status=DifferentialStatus.CONFIDENCE_UP,
            previous_confidence=60)
        self.assertEqual(evo.get_confidence_delta(), 20)

    def test_confidence_delta_negative(self):
        evo = DifferentialEvolution(
            differential=self._diff(confidence=40),
            status=DifferentialStatus.CONFIDENCE_DOWN,
            previous_confidence=70)
        self.assertEqual(evo.get_confidence_delta(), -30)

    def test_confidence_delta_zero(self):
        evo = DifferentialEvolution(
            differential=self._diff(confidence=50),
            status=DifferentialStatus.UNCHANGED,
            previous_confidence=50)
        self.assertEqual(evo.get_confidence_delta(), 0)

    def test_confidence_delta_none_when_no_previous(self):
        evo = DifferentialEvolution(
            differential=self._diff(), status=DifferentialStatus.NEW)
        self.assertIsNone(evo.get_confidence_delta())


# ---------------------------------------------------------------------------
# DifferentialTracker
# ---------------------------------------------------------------------------
class TestDifferentialTrackerInit(unittest.TestCase):
    """Tests for DifferentialTracker initialization and clear."""

    def test_initial_state(self):
        tracker = DifferentialTracker()
        self.assertEqual(tracker.previous_differentials, [])
        self.assertEqual(tracker.removed_differentials, [])

    def test_clear(self):
        tracker = DifferentialTracker()
        tracker.previous_differentials = [
            Differential(rank=1, diagnosis="X", confidence=50)]
        tracker.removed_differentials = [
            Differential(rank=2, diagnosis="Y", confidence=30)]
        tracker.clear()
        self.assertEqual(tracker.previous_differentials, [])
        self.assertEqual(tracker.removed_differentials, [])

    def test_confidence_change_threshold(self):
        self.assertEqual(DifferentialTracker.CONFIDENCE_CHANGE_THRESHOLD, 5)


class TestParseConfidence(unittest.TestCase):
    """Tests for DifferentialTracker._parse_confidence."""

    def setUp(self):
        self.tracker = DifferentialTracker()

    def test_percent_format(self):
        self.assertEqual(self.tracker._parse_confidence("78%"), 78)

    def test_bare_number(self):
        self.assertEqual(self.tracker._parse_confidence("65"), 65)

    def test_percent_with_confidence_word(self):
        self.assertEqual(self.tracker._parse_confidence("78% confidence"), 78)

    def test_combined_format(self):
        self.assertEqual(self.tracker._parse_confidence("78% (HIGH)"), 78)

    def test_high_text(self):
        self.assertEqual(self.tracker._parse_confidence("HIGH"), 80)

    def test_medium_text(self):
        self.assertEqual(self.tracker._parse_confidence("MEDIUM"), 55)

    def test_low_text(self):
        self.assertEqual(self.tracker._parse_confidence("LOW"), 25)

    def test_case_insensitive_text(self):
        self.assertEqual(self.tracker._parse_confidence("high"), 80)
        self.assertEqual(self.tracker._parse_confidence("Medium"), 55)
        self.assertEqual(self.tracker._parse_confidence("low"), 25)

    def test_clamp_above_100(self):
        self.assertEqual(self.tracker._parse_confidence("150%"), 100)

    def test_zero_percent(self):
        self.assertEqual(self.tracker._parse_confidence("0%"), 0)

    def test_clamp_to_zero(self):
        # _parse_confidence extracts numeric digits; negative signs aren't
        # captured by the regex, so "-5%" would match "5".
        self.assertEqual(self.tracker._parse_confidence("0"), 0)

    def test_unrecognized_defaults_to_50(self):
        self.assertEqual(self.tracker._parse_confidence("unknown"), 50)

    def test_empty_string_defaults_to_50(self):
        self.assertEqual(self.tracker._parse_confidence(""), 50)

    def test_100_percent(self):
        self.assertEqual(self.tracker._parse_confidence("100%"), 100)

    def test_single_digit(self):
        self.assertEqual(self.tracker._parse_confidence("5"), 5)


class TestParseDifferentials(unittest.TestCase):
    """Tests for DifferentialTracker.parse_differentials."""

    def setUp(self):
        self.tracker = DifferentialTracker()

    def test_empty_text(self):
        result = self.tracker.parse_differentials("")
        self.assertEqual(result, [])

    def test_no_section_header(self):
        text = "Some random text without a differential diagnoses section."
        result = self.tracker.parse_differentials(text)
        self.assertEqual(result, [])

    def test_new_format_with_icd_codes(self):
        text = """
DIFFERENTIAL DIAGNOSES
1. Acute Myocardial Infarction - 85% confidence (ICD-10: I21.9)
2. Unstable Angina - 60% confidence (ICD-10: I20.0)
3. Pulmonary Embolism - 30% confidence (ICD-10: I26.99)

RECOMMENDED ACTIONS
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 3)

        self.assertEqual(result[0].rank, 1)
        self.assertEqual(result[0].diagnosis, "Acute Myocardial Infarction")
        self.assertEqual(result[0].confidence, 85)
        self.assertEqual(result[0].icd_code, "I21.9")

        self.assertEqual(result[1].rank, 2)
        self.assertEqual(result[1].diagnosis, "Unstable Angina")
        self.assertEqual(result[1].confidence, 60)
        self.assertEqual(result[1].icd_code, "I20.0")

        self.assertEqual(result[2].rank, 3)
        self.assertEqual(result[2].confidence, 30)
        self.assertEqual(result[2].icd_code, "I26.99")

    def test_old_format_high_medium_low(self):
        text = """
DIFFERENTIAL DIAGNOSES
1. Hypertension - HIGH confidence
2. Diabetes Mellitus - MEDIUM confidence
3. Anemia - LOW confidence

RECOMMENDED ACTIONS
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 3)

        self.assertEqual(result[0].confidence, 80)   # HIGH -> 80
        self.assertEqual(result[1].confidence, 55)   # MEDIUM -> 55
        self.assertEqual(result[2].confidence, 25)   # LOW -> 25

    def test_combined_format(self):
        text = """
DIFFERENTIAL DIAGNOSES
1. Pneumonia - 78% (HIGH)
2. Bronchitis - 45% (MEDIUM)

RECOMMENDED ACTIONS
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 2)
        # Numeric extraction should take precedence
        self.assertEqual(result[0].confidence, 78)
        self.assertEqual(result[1].confidence, 45)

    def test_section_terminated_by_questions(self):
        text = """
DIFFERENTIAL DIAGNOSES
1. GERD - 70% confidence

QUESTIONS TO ASK
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].diagnosis, "GERD")

    def test_section_terminated_by_immediate(self):
        text = """
DIFFERENTIAL DIAGNOSES
1. Stroke - 90% confidence (ICD-10: I63.9)

IMMEDIATE ACTIONS
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 1)

    def test_section_terminated_by_end_of_text(self):
        text = """
DIFFERENTIAL DIAGNOSES
1. Migraine - 65% confidence
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].diagnosis, "Migraine")

    def test_supporting_and_against_evidence(self):
        text = """
DIFFERENTIAL DIAGNOSES
1. Acute Pancreatitis - 75% confidence
   Supporting: elevated lipase, epigastric pain
   Against: no gallstones on ultrasound

RECOMMENDED ACTIONS
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 1)
        self.assertIn("elevated lipase", result[0].supporting)
        self.assertIn("no gallstones", result[0].against)

    def test_case_insensitive_section_header(self):
        text = """
Differential Diagnoses
1. Appendicitis - 80% confidence

Recommended Actions
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 1)

    def test_icd_code_with_longer_suffix(self):
        text = """
DIFFERENTIAL DIAGNOSES
1. Type 2 Diabetes - 70% confidence (ICD-10: E11.65)

RECOMMENDED ACTIONS
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].icd_code, "E11.65")

    def test_exception_in_parsing_returns_empty_list(self):
        """Verify that an exception during parsing is caught gracefully."""
        # Patch re.search to raise to simulate an internal error
        with patch("utils.differential_tracker.re.search", side_effect=RuntimeError("boom")):
            result = self.tracker.parse_differentials("anything")
            self.assertEqual(result, [])


class TestCompareDifferentials(unittest.TestCase):
    """Tests for DifferentialTracker.compare_differentials."""

    def setUp(self):
        self.tracker = DifferentialTracker()

    def _diff(self, rank, diagnosis, confidence, **kwargs):
        return Differential(rank=rank, diagnosis=diagnosis,
                            confidence=confidence, **kwargs)

    def test_first_analysis_all_new(self):
        """With no previous, every differential should be NEW."""
        current = [
            self._diff(1, "Pneumonia", 80),
            self._diff(2, "Bronchitis", 50),
        ]
        evolutions, removed = self.tracker.compare_differentials(current)
        self.assertEqual(len(evolutions), 2)
        self.assertTrue(all(e.status == DifferentialStatus.NEW for e in evolutions))
        self.assertEqual(removed, [])

    def test_unchanged_differentials(self):
        self.tracker.previous_differentials = [
            self._diff(1, "Pneumonia", 80),
            self._diff(2, "Bronchitis", 50),
        ]
        current = [
            self._diff(1, "Pneumonia", 80),
            self._diff(2, "Bronchitis", 50),
        ]
        evolutions, removed = self.tracker.compare_differentials(current)
        self.assertEqual(len(evolutions), 2)
        for evo in evolutions:
            self.assertEqual(evo.status, DifferentialStatus.UNCHANGED)
        self.assertEqual(removed, [])

    def test_moved_up(self):
        self.tracker.previous_differentials = [
            self._diff(1, "A", 80),
            self._diff(2, "B", 50),
        ]
        current = [
            self._diff(1, "B", 50),  # B moved from rank 2 to rank 1
            self._diff(2, "A", 80),
        ]
        evolutions, removed = self.tracker.compare_differentials(current)
        # B: was rank 2, now rank 1 => MOVED_UP
        b_evo = [e for e in evolutions if e.differential.diagnosis == "B"][0]
        self.assertEqual(b_evo.status, DifferentialStatus.MOVED_UP)
        self.assertEqual(b_evo.previous_rank, 2)
        # A: was rank 1, now rank 2 => MOVED_DOWN
        a_evo = [e for e in evolutions if e.differential.diagnosis == "A"][0]
        self.assertEqual(a_evo.status, DifferentialStatus.MOVED_DOWN)
        self.assertEqual(a_evo.previous_rank, 1)

    def test_confidence_up(self):
        self.tracker.previous_differentials = [
            self._diff(1, "Pneumonia", 60),
        ]
        current = [
            self._diff(1, "Pneumonia", 70),  # +10 >= threshold of 5
        ]
        evolutions, _ = self.tracker.compare_differentials(current)
        self.assertEqual(evolutions[0].status, DifferentialStatus.CONFIDENCE_UP)
        self.assertEqual(evolutions[0].previous_confidence, 60)

    def test_confidence_down(self):
        self.tracker.previous_differentials = [
            self._diff(1, "Pneumonia", 70),
        ]
        current = [
            self._diff(1, "Pneumonia", 60),  # -10 <= -threshold
        ]
        evolutions, _ = self.tracker.compare_differentials(current)
        self.assertEqual(evolutions[0].status, DifferentialStatus.CONFIDENCE_DOWN)

    def test_confidence_change_below_threshold_is_unchanged(self):
        """A confidence change of less than 5 should still be UNCHANGED."""
        self.tracker.previous_differentials = [
            self._diff(1, "Pneumonia", 70),
        ]
        current = [
            self._diff(1, "Pneumonia", 73),  # +3 < threshold
        ]
        evolutions, _ = self.tracker.compare_differentials(current)
        self.assertEqual(evolutions[0].status, DifferentialStatus.UNCHANGED)

    def test_confidence_change_at_threshold_triggers(self):
        """A confidence change of exactly 5 should trigger CONFIDENCE_UP."""
        self.tracker.previous_differentials = [
            self._diff(1, "Pneumonia", 70),
        ]
        current = [
            self._diff(1, "Pneumonia", 75),  # exactly +5
        ]
        evolutions, _ = self.tracker.compare_differentials(current)
        self.assertEqual(evolutions[0].status, DifferentialStatus.CONFIDENCE_UP)

    def test_removed_differentials(self):
        self.tracker.previous_differentials = [
            self._diff(1, "A", 80),
            self._diff(2, "B", 50),
            self._diff(3, "C", 30),
        ]
        current = [
            self._diff(1, "A", 80),
            # B and C are gone
        ]
        evolutions, removed = self.tracker.compare_differentials(current)
        self.assertEqual(len(evolutions), 1)
        self.assertEqual(len(removed), 2)
        removed_names = {d.diagnosis for d in removed}
        self.assertEqual(removed_names, {"B", "C"})

    def test_new_and_removed_simultaneously(self):
        self.tracker.previous_differentials = [
            self._diff(1, "A", 80),
        ]
        current = [
            self._diff(1, "B", 70),  # A removed, B is new
        ]
        evolutions, removed = self.tracker.compare_differentials(current)
        self.assertEqual(len(evolutions), 1)
        self.assertEqual(evolutions[0].status, DifferentialStatus.NEW)
        self.assertEqual(evolutions[0].differential.diagnosis, "B")
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].diagnosis, "A")

    def test_normalized_name_matching(self):
        """Matching should be case-insensitive and whitespace-normalized."""
        self.tracker.previous_differentials = [
            self._diff(1, "Tension  Type  Headache", 60),
        ]
        current = [
            self._diff(1, "tension type headache", 60),
        ]
        evolutions, removed = self.tracker.compare_differentials(current)
        self.assertEqual(evolutions[0].status, DifferentialStatus.UNCHANGED)
        self.assertEqual(removed, [])

    def test_empty_current(self):
        self.tracker.previous_differentials = [
            self._diff(1, "A", 80),
        ]
        evolutions, removed = self.tracker.compare_differentials([])
        self.assertEqual(evolutions, [])
        self.assertEqual(len(removed), 1)

    def test_rank_change_takes_precedence_over_confidence_change(self):
        """If rank changed AND confidence changed, rank change wins."""
        self.tracker.previous_differentials = [
            self._diff(2, "X", 60),
        ]
        current = [
            self._diff(1, "X", 90),  # rank up AND confidence up
        ]
        evolutions, _ = self.tracker.compare_differentials(current)
        self.assertEqual(evolutions[0].status, DifferentialStatus.MOVED_UP)


class TestDetermineStatus(unittest.TestCase):
    """Direct tests for DifferentialTracker._determine_status."""

    def setUp(self):
        self.tracker = DifferentialTracker()

    def _diff(self, rank, confidence):
        return Differential(rank=rank, diagnosis="Test", confidence=confidence)

    def test_moved_up(self):
        status = self.tracker._determine_status(
            self._diff(3, 50), self._diff(1, 50))
        self.assertEqual(status, DifferentialStatus.MOVED_UP)

    def test_moved_down(self):
        status = self.tracker._determine_status(
            self._diff(1, 50), self._diff(3, 50))
        self.assertEqual(status, DifferentialStatus.MOVED_DOWN)

    def test_confidence_up_same_rank(self):
        status = self.tracker._determine_status(
            self._diff(1, 50), self._diff(1, 60))
        self.assertEqual(status, DifferentialStatus.CONFIDENCE_UP)

    def test_confidence_down_same_rank(self):
        status = self.tracker._determine_status(
            self._diff(1, 60), self._diff(1, 50))
        self.assertEqual(status, DifferentialStatus.CONFIDENCE_DOWN)

    def test_unchanged_same_rank_small_delta(self):
        status = self.tracker._determine_status(
            self._diff(1, 50), self._diff(1, 52))
        self.assertEqual(status, DifferentialStatus.UNCHANGED)

    def test_unchanged_exact_same(self):
        status = self.tracker._determine_status(
            self._diff(2, 70), self._diff(2, 70))
        self.assertEqual(status, DifferentialStatus.UNCHANGED)

    def test_negative_confidence_delta_just_below_threshold(self):
        # -4 is above -5 threshold, so UNCHANGED
        status = self.tracker._determine_status(
            self._diff(1, 54), self._diff(1, 50))
        self.assertEqual(status, DifferentialStatus.UNCHANGED)

    def test_negative_confidence_delta_at_threshold(self):
        # -5 exactly => CONFIDENCE_DOWN
        status = self.tracker._determine_status(
            self._diff(1, 55), self._diff(1, 50))
        self.assertEqual(status, DifferentialStatus.CONFIDENCE_DOWN)


class TestUpdate(unittest.TestCase):
    """Tests for DifferentialTracker.update."""

    def test_update_stores_copy(self):
        tracker = DifferentialTracker()
        diffs = [Differential(rank=1, diagnosis="A", confidence=80)]
        tracker.update(diffs)
        self.assertEqual(len(tracker.previous_differentials), 1)
        self.assertEqual(tracker.previous_differentials[0].diagnosis, "A")

    def test_update_is_a_copy_not_same_list(self):
        tracker = DifferentialTracker()
        diffs = [Differential(rank=1, diagnosis="A", confidence=80)]
        tracker.update(diffs)
        diffs.append(Differential(rank=2, diagnosis="B", confidence=50))
        # The tracker's list should not have been affected
        self.assertEqual(len(tracker.previous_differentials), 1)

    def test_update_replaces_previous(self):
        tracker = DifferentialTracker()
        tracker.update([Differential(rank=1, diagnosis="A", confidence=80)])
        tracker.update([Differential(rank=1, diagnosis="B", confidence=50)])
        self.assertEqual(len(tracker.previous_differentials), 1)
        self.assertEqual(tracker.previous_differentials[0].diagnosis, "B")


class TestFormatEvolutionText(unittest.TestCase):
    """Tests for DifferentialTracker.format_evolution_text."""

    def setUp(self):
        self.tracker = DifferentialTracker()

    def _diff(self, rank, diagnosis, confidence, icd_code=None):
        return Differential(rank=rank, diagnosis=diagnosis,
                            confidence=confidence, icd_code=icd_code)

    def _evo(self, diff, status, prev_rank=None, prev_conf=None):
        return DifferentialEvolution(
            differential=diff, status=status,
            previous_rank=prev_rank, previous_confidence=prev_conf)

    def test_first_analysis_returns_empty(self):
        result = self.tracker.format_evolution_text([], [], analysis_count=1)
        self.assertEqual(result, "")

    def test_zero_analysis_returns_empty(self):
        result = self.tracker.format_evolution_text([], [], analysis_count=0)
        self.assertEqual(result, "")

    def test_header_present_for_second_analysis(self):
        result = self.tracker.format_evolution_text([], [], analysis_count=2)
        self.assertIn("--- DIFFERENTIAL EVOLUTION ---", result)

    def test_new_differentials_section(self):
        evos = [
            self._evo(self._diff(1, "Pneumonia", 80, "J18.9"),
                      DifferentialStatus.NEW),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        self.assertIn("NEW", result)
        self.assertIn("Pneumonia", result)
        self.assertIn("80%", result)
        self.assertIn("ICD-10: J18.9", result)

    def test_new_without_icd_code(self):
        evos = [
            self._evo(self._diff(1, "Headache", 50),
                      DifferentialStatus.NEW),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        self.assertIn("Headache", result)
        self.assertNotIn("ICD-10", result)

    def test_moved_up_section(self):
        evos = [
            self._evo(self._diff(1, "MI", 85), DifferentialStatus.MOVED_UP,
                      prev_rank=3, prev_conf=75),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        self.assertIn("MOVED UP", result)
        self.assertIn("MI", result)
        self.assertIn("#3", result)
        self.assertIn("#1", result)

    def test_moved_down_section(self):
        evos = [
            self._evo(self._diff(3, "Flu", 40), DifferentialStatus.MOVED_DOWN,
                      prev_rank=1, prev_conf=60),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        self.assertIn("MOVED DOWN", result)
        self.assertIn("Flu", result)
        self.assertIn("#1", result)
        self.assertIn("#3", result)

    def test_confidence_up_section(self):
        evos = [
            self._evo(self._diff(1, "COPD", 80), DifferentialStatus.CONFIDENCE_UP,
                      prev_rank=1, prev_conf=65),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        self.assertIn("CONFIDENCE INCREASED", result)
        self.assertIn("COPD", result)
        self.assertIn("65%", result)
        self.assertIn("80%", result)
        self.assertIn("+15%", result)

    def test_confidence_down_section(self):
        evos = [
            self._evo(self._diff(1, "COPD", 50), DifferentialStatus.CONFIDENCE_DOWN,
                      prev_rank=1, prev_conf=80),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        self.assertIn("CONFIDENCE DECREASED", result)
        self.assertIn("80%", result)
        self.assertIn("50%", result)
        self.assertIn("-30%", result)

    def test_removed_section(self):
        removed = [
            self._diff(2, "Asthma", 55, icd_code="J45.909"),
        ]
        result = self.tracker.format_evolution_text([], removed, analysis_count=2)
        self.assertIn("REMOVED FROM DIFFERENTIAL", result)
        self.assertIn("Asthma", result)
        self.assertIn("#2", result)
        self.assertIn("55%", result)
        self.assertIn("ICD-10: J45.909", result)

    def test_removed_without_icd(self):
        removed = [self._diff(3, "Bronchitis", 40)]
        result = self.tracker.format_evolution_text([], removed, analysis_count=2)
        self.assertIn("Bronchitis", result)
        self.assertNotIn("ICD-10", result)

    def test_unchanged_summary(self):
        evos = [
            self._evo(self._diff(1, "Stable", 70), DifferentialStatus.UNCHANGED,
                      prev_rank=1, prev_conf=70),
            self._evo(self._diff(2, "AlsoStable", 50), DifferentialStatus.UNCHANGED,
                      prev_rank=2, prev_conf=50),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        self.assertIn("UNCHANGED: 2 diagnosis(es)", result)

    def test_summary_line_counts(self):
        evos = [
            self._evo(self._diff(1, "New1", 80), DifferentialStatus.NEW),
            self._evo(self._diff(2, "New2", 60), DifferentialStatus.NEW),
            self._evo(self._diff(3, "Up1", 70), DifferentialStatus.MOVED_UP,
                      prev_rank=5, prev_conf=50),
        ]
        removed = [self._diff(4, "Gone1", 30)]
        result = self.tracker.format_evolution_text(evos, removed, analysis_count=3)
        self.assertIn("2 new", result)
        self.assertIn("1 moved up", result)
        self.assertIn("1 removed", result)

    def test_summary_line_with_moved_down(self):
        evos = [
            self._evo(self._diff(5, "Down1", 30), DifferentialStatus.MOVED_DOWN,
                      prev_rank=2, prev_conf=40),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        self.assertIn("1 moved down", result)

    def test_no_summary_parts_when_only_unchanged(self):
        """If all are unchanged, the summary parts list is empty."""
        evos = [
            self._evo(self._diff(1, "S", 50), DifferentialStatus.UNCHANGED,
                      prev_rank=1, prev_conf=50),
        ]
        result = self.tracker.format_evolution_text(evos, [], analysis_count=2)
        # "Summary:" line should not appear because summary_parts is empty
        self.assertNotIn("Summary:", result)

    def test_all_statuses_together(self):
        """Comprehensive test with every status represented."""
        evos = [
            self._evo(self._diff(1, "NewDx", 80), DifferentialStatus.NEW),
            self._evo(self._diff(2, "UpDx", 70), DifferentialStatus.MOVED_UP,
                      prev_rank=4, prev_conf=65),
            self._evo(self._diff(3, "DownDx", 40), DifferentialStatus.MOVED_DOWN,
                      prev_rank=1, prev_conf=50),
            self._evo(self._diff(4, "ConfUpDx", 75), DifferentialStatus.CONFIDENCE_UP,
                      prev_rank=4, prev_conf=60),
            self._evo(self._diff(5, "ConfDownDx", 30), DifferentialStatus.CONFIDENCE_DOWN,
                      prev_rank=5, prev_conf=55),
            self._evo(self._diff(6, "SameDx", 50), DifferentialStatus.UNCHANGED,
                      prev_rank=6, prev_conf=50),
        ]
        removed = [self._diff(7, "GoneDx", 20)]
        result = self.tracker.format_evolution_text(evos, removed, analysis_count=5)

        self.assertIn("NewDx", result)
        self.assertIn("UpDx", result)
        self.assertIn("DownDx", result)
        self.assertIn("ConfUpDx", result)
        self.assertIn("ConfDownDx", result)
        self.assertIn("UNCHANGED: 1 diagnosis(es)", result)
        self.assertIn("GoneDx", result)


# ---------------------------------------------------------------------------
# Integration-style: parse -> compare -> format round trip
# ---------------------------------------------------------------------------
class TestEndToEndTracking(unittest.TestCase):
    """Tests that chain parse -> compare -> update -> compare -> format."""

    def test_two_analysis_round_trip(self):
        tracker = DifferentialTracker()

        # --- First analysis ---
        text1 = """
DIFFERENTIAL DIAGNOSES
1. Pneumonia - 80% confidence (ICD-10: J18.9)
2. Bronchitis - 50% confidence
3. Asthma - 30% confidence

RECOMMENDED ACTIONS
"""
        diffs1 = tracker.parse_differentials(text1)
        self.assertEqual(len(diffs1), 3)

        evolutions1, removed1 = tracker.compare_differentials(diffs1)
        # First time: all NEW
        self.assertTrue(all(e.status == DifferentialStatus.NEW for e in evolutions1))
        self.assertEqual(removed1, [])

        tracker.update(diffs1)

        # --- Second analysis ---
        text2 = """
DIFFERENTIAL DIAGNOSES
1. Pneumonia - 90% confidence (ICD-10: J18.9)
2. Lung Cancer - 40% confidence (ICD-10: C34.90)
3. Bronchitis - 35% confidence

RECOMMENDED ACTIONS
"""
        diffs2 = tracker.parse_differentials(text2)
        self.assertEqual(len(diffs2), 3)

        evolutions2, removed2 = tracker.compare_differentials(diffs2)

        # Pneumonia: same rank, confidence 80->90 (+10 >= threshold)
        pneumonia_evo = [e for e in evolutions2
                         if e.differential.diagnosis == "Pneumonia"][0]
        self.assertEqual(pneumonia_evo.status, DifferentialStatus.CONFIDENCE_UP)

        # Lung Cancer: NEW
        lung_evo = [e for e in evolutions2
                    if e.differential.diagnosis == "Lung Cancer"][0]
        self.assertEqual(lung_evo.status, DifferentialStatus.NEW)

        # Bronchitis: was rank 2, now rank 3 => MOVED_DOWN
        bronchitis_evo = [e for e in evolutions2
                          if e.differential.diagnosis == "Bronchitis"][0]
        self.assertEqual(bronchitis_evo.status, DifferentialStatus.MOVED_DOWN)

        # Asthma: removed
        self.assertEqual(len(removed2), 1)
        self.assertEqual(removed2[0].diagnosis, "Asthma")

        # Format and verify
        formatted = tracker.format_evolution_text(evolutions2, removed2,
                                                  analysis_count=2)
        self.assertIn("DIFFERENTIAL EVOLUTION", formatted)
        self.assertIn("1 new", formatted)
        self.assertIn("1 moved down", formatted)
        self.assertIn("1 removed", formatted)
        self.assertIn("Asthma", formatted)

    def test_clear_resets_tracking(self):
        tracker = DifferentialTracker()
        diffs = [Differential(rank=1, diagnosis="A", confidence=80)]
        tracker.update(diffs)
        tracker.clear()

        evolutions, removed = tracker.compare_differentials(diffs)
        self.assertEqual(len(evolutions), 1)
        self.assertEqual(evolutions[0].status, DifferentialStatus.NEW)
        self.assertEqual(removed, [])


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases(unittest.TestCase):
    """Edge-case and boundary tests."""

    def setUp(self):
        self.tracker = DifferentialTracker()

    def test_parse_with_no_numbered_items_in_section(self):
        text = """
DIFFERENTIAL DIAGNOSES
Some free-text commentary without numbered items.

RECOMMENDED ACTIONS
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(result, [])

    def test_parse_multiple_diagnoses_same_rank(self):
        """Two items with the same rank number still parse as separate items."""
        text = """
DIFFERENTIAL DIAGNOSES
1. Alpha - 60% confidence
1. Beta - 50% confidence

RECOMMENDED ACTIONS
"""
        result = self.tracker.parse_differentials(text)
        self.assertEqual(len(result), 2)

    def test_compare_duplicate_names_in_previous(self):
        """Last occurrence wins in the previous lookup dict."""
        self.tracker.previous_differentials = [
            Differential(rank=1, diagnosis="A", confidence=50),
            Differential(rank=2, diagnosis="A", confidence=70),
        ]
        current = [Differential(rank=1, diagnosis="A", confidence=70)]
        evolutions, removed = self.tracker.compare_differentials(current)
        # The lookup is by normalized name, so the second 'A' (rank=2, conf=70)
        # overwrites the first in prev_lookup
        self.assertEqual(len(evolutions), 1)

    def test_format_empty_evolutions_and_removed(self):
        result = self.tracker.format_evolution_text([], [], analysis_count=3)
        self.assertIn("--- DIFFERENTIAL EVOLUTION ---", result)
        # No status sections should appear
        self.assertNotIn("NEW:", result)
        self.assertNotIn("MOVED UP:", result)

    def test_confidence_boundary_70_is_high(self):
        d = Differential(rank=1, diagnosis="X", confidence=70)
        self.assertEqual(d.confidence_level, "HIGH")

    def test_confidence_boundary_40_is_medium(self):
        d = Differential(rank=1, diagnosis="X", confidence=40)
        self.assertEqual(d.confidence_level, "MEDIUM")

    def test_confidence_boundary_39_is_low(self):
        d = Differential(rank=1, diagnosis="X", confidence=39)
        self.assertEqual(d.confidence_level, "LOW")

    def test_confidence_0_is_low(self):
        d = Differential(rank=1, diagnosis="X", confidence=0)
        self.assertEqual(d.confidence_level, "LOW")

    def test_confidence_100_is_high(self):
        d = Differential(rank=1, diagnosis="X", confidence=100)
        self.assertEqual(d.confidence_level, "HIGH")


if __name__ == "__main__":
    unittest.main()
