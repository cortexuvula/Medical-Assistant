"""
Pure-logic tests for MedicationAgent in src/ai/agents/medication.py.

Covers:
  - _determine_task_type
  - _parse_medication_list
  - TDM_DRUGS module-level data
  - BEERS_HIGH_RISK module-level data

No network calls, no Tkinter, no real AI calls.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.medication import MedicationAgent, TDM_DRUGS, BEERS_HIGH_RISK
from ai.agents.models import AgentTask


# ---------------------------------------------------------------------------
# Fixture / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def agent():
    mock_caller = MagicMock()
    mock_caller.call.return_value = "mocked response"
    return MedicationAgent(ai_caller=mock_caller)


def _task(description: str) -> AgentTask:
    """Build an AgentTask with the given description and empty input_data."""
    return AgentTask(task_description=description, input_data={})


# ---------------------------------------------------------------------------
# TestDetermineTaskType  (15 tests)
# ---------------------------------------------------------------------------

class TestDetermineTaskType:
    """Tests for MedicationAgent._determine_task_type."""

    def test_extract_keyword_returns_extract(self, agent):
        assert agent._determine_task_type(_task("extract all medications")) == "extract"

    def test_identify_keyword_returns_extract(self, agent):
        assert agent._determine_task_type(_task("identify medications in note")) == "extract"

    def test_interaction_keyword_returns_check_interactions(self, agent):
        assert agent._determine_task_type(_task("interaction between these drugs")) == "check_interactions"

    def test_check_interaction_phrase_returns_check_interactions(self, agent):
        assert agent._determine_task_type(_task("check interaction for patient")) == "check_interactions"

    def test_prescription_keyword_returns_generate_prescription(self, agent):
        assert agent._determine_task_type(_task("write a prescription for lisinopril")) == "generate_prescription"

    def test_prescribe_keyword_returns_generate_prescription(self, agent):
        assert agent._determine_task_type(_task("prescribe metformin for this patient")) == "generate_prescription"

    def test_dosing_keyword_returns_validate_dosing(self, agent):
        assert agent._determine_task_type(_task("validate dosing for renal impairment")) == "validate_dosing"

    def test_dose_keyword_returns_validate_dosing(self, agent):
        assert agent._determine_task_type(_task("is this dose appropriate for child?")) == "validate_dosing"

    def test_alternative_keyword_returns_suggest_alternatives(self, agent):
        assert agent._determine_task_type(_task("suggest alternative to atenolol")) == "suggest_alternatives"

    def test_substitute_keyword_returns_suggest_alternatives(self, agent):
        assert agent._determine_task_type(_task("substitute for metoprolol in elderly")) == "suggest_alternatives"

    def test_unrelated_description_returns_comprehensive(self, agent):
        assert agent._determine_task_type(_task("review chart for medication summary")) == "comprehensive"

    def test_empty_string_returns_comprehensive(self, agent):
        assert agent._determine_task_type(_task("")) == "comprehensive"

    def test_uppercase_extract_uses_lower_comparison(self, agent):
        # .lower() is applied before comparison, so EXTRACT should match
        assert agent._determine_task_type(_task("EXTRACT medications from text")) == "extract"

    def test_first_match_wins_extract_before_interaction(self, agent):
        # "extract" appears before "interaction" in the elif chain; extract wins
        assert agent._determine_task_type(_task("extract and check interaction")) == "extract"

    def test_clinical_sentence_multiple_keywords_first_match_wins(self, agent):
        # "identify" (→ extract) appears before "dose" in description; extract wins
        assert agent._determine_task_type(_task("identify correct dose for patient")) == "extract"


# ---------------------------------------------------------------------------
# TestParseMedicationList  (25 tests)
# ---------------------------------------------------------------------------

class TestParseMedicationList:
    """Tests for MedicationAgent._parse_medication_list."""

    def test_empty_string_returns_empty_list(self, agent):
        assert agent._parse_medication_list("") == []

    def test_whitespace_only_returns_empty_list(self, agent):
        assert agent._parse_medication_list("   \n  \n  ") == []

    def test_single_dash_line_returns_one_entry(self, agent):
        result = agent._parse_medication_list("- Lisinopril 10mg")
        assert len(result) == 1

    def test_single_dash_line_name_extracted(self, agent):
        result = agent._parse_medication_list("- Lisinopril 10mg")
        assert result[0]["name"] == "Lisinopril 10mg"

    def test_single_dash_line_raw_preserved(self, agent):
        result = agent._parse_medication_list("- Lisinopril 10mg")
        assert result[0]["raw"] == "- Lisinopril 10mg"

    def test_numbered_line_returns_one_entry(self, agent):
        result = agent._parse_medication_list("1. Metformin 500mg")
        assert len(result) == 1

    def test_numbered_line_name_excludes_prefix(self, agent):
        result = agent._parse_medication_list("1. Metformin 500mg")
        assert result[0]["name"] == "Metformin 500mg"

    def test_two_digit_numbered_line_strips_prefix(self, agent):
        result = agent._parse_medication_list("2. Aspirin 81mg")
        assert result[0]["name"] == "Aspirin 81mg"

    def test_multiple_meds_separated_by_blank_line(self, agent):
        text = "- Aspirin 81mg\n\n- Metformin 500mg"
        result = agent._parse_medication_list(text)
        assert len(result) == 2

    def test_multiple_consecutive_dash_lines_each_becomes_entry(self, agent):
        text = "- Aspirin 81mg\n- Metformin 500mg\n- Lisinopril 10mg"
        result = agent._parse_medication_list(text)
        assert len(result) == 3

    def test_dose_property_after_header_added_to_entry(self, agent):
        text = "- Aspirin\nDose: 81mg"
        result = agent._parse_medication_list(text)
        assert result[0].get("dose") == "81mg"

    def test_property_key_lowercased(self, agent):
        text = "- Aspirin\nDOSE: 81mg"
        result = agent._parse_medication_list(text)
        assert "dose" in result[0]

    def test_property_key_spaces_replaced_with_underscore(self, agent):
        text = "- Aspirin\nRoute of Administration: oral"
        result = agent._parse_medication_list(text)
        assert "route_of_administration" in result[0]

    def test_property_value_whitespace_stripped(self, agent):
        text = "- Aspirin\nDose:  81mg   "
        result = agent._parse_medication_list(text)
        assert result[0]["dose"] == "81mg"

    def test_colon_splits_only_on_first_colon(self, agent):
        # Value itself contains a colon; line.split(':', 1) keeps rest intact
        text = "- Aspirin\nTiming: 08:00 daily"
        result = agent._parse_medication_list(text)
        assert result[0]["timing"] == "08:00 daily"

    def test_multiple_properties_per_medication(self, agent):
        text = "- Warfarin\nDose: 5mg\nFrequency: Daily\nIndication: AFib"
        result = agent._parse_medication_list(text)
        assert result[0].get("dose") == "5mg"
        assert result[0].get("frequency") == "Daily"
        assert result[0].get("indication") == "AFib"

    def test_no_trailing_blank_line_last_med_still_appended(self, agent):
        # No blank line after the last entry; the final current_med flush must fire
        text = "- Aspirin 81mg\n- Metformin 500mg"
        result = agent._parse_medication_list(text)
        assert len(result) == 2

    def test_line_starting_with_digit_starts_new_entry(self, agent):
        # A line that begins with a digit (e.g. "12. Atorvastatin") is treated as a new med
        result = agent._parse_medication_list("12. Atorvastatin 40mg")
        assert len(result) == 1
        assert "Atorvastatin 40mg" in result[0]["name"]

    def test_dash_followed_by_space_strips_correctly(self, agent):
        result = agent._parse_medication_list("- Vancomycin 1g IV")
        assert not result[0]["name"].startswith("-")
        assert not result[0]["name"].startswith(" ")

    def test_colon_line_without_prior_header_goes_into_empty_current_med(self, agent):
        # A colon line with no preceding med header accumulates into current_med {}
        # and is flushed at the end; result length is 1 with property but no 'name'
        text = "Dose: 81mg"
        result = agent._parse_medication_list(text)
        assert len(result) == 1
        assert result[0].get("dose") == "81mg"

    def test_only_colon_lines_no_med_starters(self, agent):
        # Multiple colon lines with no dash/digit headers all accumulate into one block
        text = "Dose: 10mg\nFrequency: BID"
        result = agent._parse_medication_list(text)
        assert len(result) == 1
        assert result[0].get("dose") == "10mg"
        assert result[0].get("frequency") == "BID"

    def test_pure_text_line_no_dash_no_digit_no_colon_ignored(self, agent):
        # A line with no leading digit, no dash, and no colon does not match any branch
        # If there is no current_med yet it's silently skipped; result is empty
        result = agent._parse_medication_list("plain text with no structure")
        assert result == []

    def test_two_meds_with_properties_in_blocks(self, agent):
        text = (
            "- Aspirin 81mg\n"
            "Frequency: Once daily\n"
            "\n"
            "- Metformin 500mg\n"
            "Frequency: BID\n"
        )
        result = agent._parse_medication_list(text)
        assert len(result) == 2
        assert result[0].get("frequency") == "Once daily"
        assert result[1].get("frequency") == "BID"

    def test_five_numbered_meds_returns_five(self, agent):
        lines = "\n".join(f"{i}. Drug{i} {i * 10}mg" for i in range(1, 6))
        result = agent._parse_medication_list(lines)
        assert len(result) == 5

    def test_each_result_entry_is_dict(self, agent):
        text = "- Aspirin 81mg\n- Metformin 500mg"
        result = agent._parse_medication_list(text)
        assert all(isinstance(m, dict) for m in result)


# ---------------------------------------------------------------------------
# TestTDMDrugsData  (18 tests — all 16 drug-present checks + structural checks)
# ---------------------------------------------------------------------------

EXPECTED_TDM_KEYS = [
    "vancomycin", "digoxin", "lithium", "warfarin", "phenytoin",
    "carbamazepine", "valproic_acid", "aminoglycosides", "theophylline",
    "cyclosporine", "tacrolimus", "methotrexate", "sirolimus",
    "amikacin", "gentamicin", "tobramycin",
]


class TestTDMDrugsData:
    """Tests for the TDM_DRUGS module-level dict."""

    def test_tdm_drugs_is_dict(self):
        assert isinstance(TDM_DRUGS, dict)

    def test_tdm_drugs_has_exactly_16_keys(self):
        assert len(TDM_DRUGS) == 16

    def test_each_entry_has_target_key(self):
        for drug, data in TDM_DRUGS.items():
            assert "target" in data, f"'{drug}' entry missing 'target'"

    def test_each_entry_has_timing_key(self):
        for drug, data in TDM_DRUGS.items():
            assert "timing" in data, f"'{drug}' entry missing 'timing'"

    def test_each_entry_has_guideline_key(self):
        for drug, data in TDM_DRUGS.items():
            assert "guideline" in data, f"'{drug}' entry missing 'guideline'"

    def test_all_values_are_nonempty_strings(self):
        for drug, data in TDM_DRUGS.items():
            for field in ("target", "timing", "guideline"):
                assert isinstance(data[field], str) and data[field], (
                    f"'{drug}.{field}' is empty or not a string"
                )

    def test_vancomycin_target_contains_auc_or_trough(self):
        target = TDM_DRUGS["vancomycin"]["target"].upper()
        assert "AUC" in target or "TROUGH" in target

    def test_warfarin_guideline_is_chest(self):
        assert TDM_DRUGS["warfarin"]["guideline"] == "CHEST"

    def test_lithium_target_contains_meq_per_l(self):
        assert "mEq/L" in TDM_DRUGS["lithium"]["target"]

    @pytest.mark.parametrize("drug", EXPECTED_TDM_KEYS)
    def test_expected_drug_present(self, drug):
        assert drug in TDM_DRUGS, f"'{drug}' not found in TDM_DRUGS"


# ---------------------------------------------------------------------------
# TestBeersCriteriaData  (10 tests)
# ---------------------------------------------------------------------------

class TestBeersCriteriaData:
    """Tests for the BEERS_HIGH_RISK module-level list."""

    def test_beers_high_risk_is_list(self):
        assert isinstance(BEERS_HIGH_RISK, list)

    def test_beers_has_at_least_40_items(self):
        assert len(BEERS_HIGH_RISK) >= 40

    def test_all_items_are_strings(self):
        assert all(isinstance(item, str) for item in BEERS_HIGH_RISK)

    def test_diphenhydramine_in_list(self):
        assert "diphenhydramine" in BEERS_HIGH_RISK

    def test_diazepam_in_list(self):
        assert "diazepam" in BEERS_HIGH_RISK

    def test_amitriptyline_in_list(self):
        assert "amitriptyline" in BEERS_HIGH_RISK

    def test_meperidine_in_list(self):
        assert "meperidine" in BEERS_HIGH_RISK

    def test_haloperidol_in_list(self):
        assert "haloperidol" in BEERS_HIGH_RISK

    def test_cyclobenzaprine_in_list(self):
        assert "cyclobenzaprine" in BEERS_HIGH_RISK

    def test_nitrofurantoin_in_list(self):
        assert "nitrofurantoin" in BEERS_HIGH_RISK

    def test_metoclopramide_in_list(self):
        assert "metoclopramide" in BEERS_HIGH_RISK
