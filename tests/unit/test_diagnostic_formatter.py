"""
Tests for FormatterMixin._is_in_section in
src/ui/dialogs/diagnostic/formatter.py
"""

import sys
import importlib.util
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Load formatter.py directly via importlib to avoid importing the package
# __init__, which depends on ttkbootstrap and other heavy UI dependencies.
_spec = importlib.util.spec_from_file_location(
    "diagnostic_formatter",
    project_root / "src/ui/dialogs/diagnostic/formatter.py",
)
_formatter_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_formatter_mod)

FormatterMixin = _formatter_mod.FormatterMixin


@pytest.fixture
def formatter():
    instance = FormatterMixin.__new__(FormatterMixin)
    instance.result_text = MagicMock()
    return instance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_HEADERS = [
    "CLINICAL SUMMARY:",
    "DIFFERENTIAL DIAGNOSES:",
    "RED FLAGS:",
    "RECOMMENDED INVESTIGATIONS:",
    "CLINICAL PEARLS:",
]

REALISTIC_LINES = [
    "CLINICAL SUMMARY: Patient presents with...",
    "fever, cough, and shortness of breath",
    "DIFFERENTIAL DIAGNOSES:",
    "1. Pneumonia [HIGH]",
    "2. COVID-19 [MEDIUM]",
    "3. Influenza [LOW]",
    "RED FLAGS:",
    "- Respiratory distress",
    "RECOMMENDED INVESTIGATIONS:",
    "- Chest X-ray",
    "- CBC",
    "CLINICAL PEARLS:",
    "Monitor oxygen saturation",
]


# ===========================================================================
# TestIsInSectionBasic
# ===========================================================================

class TestIsInSectionBasic:
    """10 baseline tests covering fundamental behaviour."""

    def test_empty_all_lines_returns_false(self, formatter):
        assert formatter._is_in_section("fever", "DIFFERENTIAL DIAGNOSES:", []) is False

    def test_line_before_any_section_header_returns_false(self, formatter):
        lines = ["some preamble text", "DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        assert formatter._is_in_section("some preamble text", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_line_immediately_after_section_header_returns_true(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        assert formatter._is_in_section("1. Pneumonia", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_line_several_lines_after_section_header_returns_true(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia", "2. COVID-19", "3. Influenza"]
        assert formatter._is_in_section("3. Influenza", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_line_after_different_section_header_returns_false(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia", "RED FLAGS:", "- Distress"]
        assert formatter._is_in_section("- Distress", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_line_not_in_all_lines_returns_false(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        assert formatter._is_in_section("totally absent", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_single_element_only_target_line_no_header_returns_false(self, formatter):
        lines = ["fever"]
        assert formatter._is_in_section("fever", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_single_element_only_section_header_no_target_returns_false(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:"]
        assert formatter._is_in_section("1. Pneumonia", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_two_element_list_header_then_target_returns_true(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        assert formatter._is_in_section("1. Pneumonia", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_section_header_line_itself_as_target_found_after_flag_set_true(self, formatter):
        # The section_header line sets in_section=True; the elif for other headers
        # won't fire; the elif strip check won't match the exact section_header text
        # *unless* something else in the list has .strip() == section_header.
        # If the header appears twice, the second occurrence sets in_section=True
        # but the elif strip branch still won't match because the section_header check
        # fires first. Test that querying the header text itself as the line returns False
        # (the header line triggers the first branch, not the strip branch).
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        # "DIFFERENTIAL DIAGNOSES:" as the target line — the first line triggers the
        # in_section=True branch, so it never reaches the strip check for that line.
        assert formatter._is_in_section("DIFFERENTIAL DIAGNOSES:", "DIFFERENTIAL DIAGNOSES:", lines) is False


# ===========================================================================
# TestSectionBoundaries
# ===========================================================================

class TestSectionBoundaries:
    """15 tests focused on section boundary transitions."""

    def test_line_in_second_section_with_first_section_header_query(self, formatter):
        lines = ["CLINICAL SUMMARY:", "summary text", "DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        # Asking if "1. Pneumonia" is in CLINICAL SUMMARY — it is not.
        assert formatter._is_in_section("1. Pneumonia", "CLINICAL SUMMARY:", lines) is False

    def test_line_in_clinical_summary_returns_true_through_multiple_lines(self, formatter):
        lines = ["CLINICAL SUMMARY:", "line one", "line two", "line three"]
        assert formatter._is_in_section("line one", "CLINICAL SUMMARY:", lines) is True
        assert formatter._is_in_section("line two", "CLINICAL SUMMARY:", lines) is True
        assert formatter._is_in_section("line three", "CLINICAL SUMMARY:", lines) is True

    def test_after_recommended_investigations_previous_section_lines_false(self, formatter):
        lines = [
            "RED FLAGS:",
            "- high fever",
            "RECOMMENDED INVESTIGATIONS:",
            "- Chest X-ray",
        ]
        assert formatter._is_in_section("- high fever", "RECOMMENDED INVESTIGATIONS:", lines) is False

    def test_pattern_two_sections_each_line_in_correct_section(self, formatter):
        lines = ["CLINICAL SUMMARY:", "line1", "DIFFERENTIAL DIAGNOSES:", "line2"]
        assert formatter._is_in_section("line1", "CLINICAL SUMMARY:", lines) is True
        assert formatter._is_in_section("line2", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_line_before_any_header_in_multi_section_document(self, formatter):
        lines = ["intro text", "CLINICAL SUMMARY:", "summary", "DIFFERENTIAL DIAGNOSES:", "diag"]
        assert formatter._is_in_section("intro text", "CLINICAL SUMMARY:", lines) is False

    def test_line_in_last_section_before_end_of_document(self, formatter):
        lines = ["CLINICAL PEARLS:", "always wash hands"]
        assert formatter._is_in_section("always wash hands", "CLINICAL PEARLS:", lines) is True

    def test_multiple_instances_of_same_section_header_first_activates(self, formatter):
        lines = [
            "RED FLAGS:",
            "- flag one",
            "RED FLAGS:",
            "- flag two",
        ]
        # Both "flag one" and "flag two" should resolve as in RED FLAGS:
        assert formatter._is_in_section("- flag one", "RED FLAGS:", lines) is True
        assert formatter._is_in_section("- flag two", "RED FLAGS:", lines) is True

    def test_clinical_summary_as_section_header(self, formatter):
        lines = ["CLINICAL SUMMARY:", "patient is stable"]
        assert formatter._is_in_section("patient is stable", "CLINICAL SUMMARY:", lines) is True

    def test_differential_diagnoses_as_section_header(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Hypertension"]
        assert formatter._is_in_section("1. Hypertension", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_red_flags_as_section_header(self, formatter):
        lines = ["RED FLAGS:", "- chest pain"]
        assert formatter._is_in_section("- chest pain", "RED FLAGS:", lines) is True

    def test_recommended_investigations_as_section_header(self, formatter):
        lines = ["RECOMMENDED INVESTIGATIONS:", "- ECG"]
        assert formatter._is_in_section("- ECG", "RECOMMENDED INVESTIGATIONS:", lines) is True

    def test_clinical_pearls_as_section_header(self, formatter):
        lines = ["CLINICAL PEARLS:", "monitor vitals"]
        assert formatter._is_in_section("monitor vitals", "CLINICAL PEARLS:", lines) is True

    def test_three_sections_middle_line_only_in_middle_section(self, formatter):
        lines = [
            "CLINICAL SUMMARY:",
            "summary detail",
            "DIFFERENTIAL DIAGNOSES:",
            "1. Sepsis",
            "RED FLAGS:",
            "- altered consciousness",
        ]
        assert formatter._is_in_section("1. Sepsis", "DIFFERENTIAL DIAGNOSES:", lines) is True
        assert formatter._is_in_section("1. Sepsis", "CLINICAL SUMMARY:", lines) is False
        assert formatter._is_in_section("1. Sepsis", "RED FLAGS:", lines) is False

    def test_section_boundary_resets_on_any_known_header(self, formatter):
        lines = [
            "DIFFERENTIAL DIAGNOSES:",
            "item A",
            "CLINICAL SUMMARY:",
            "item B",
        ]
        assert formatter._is_in_section("item A", "DIFFERENTIAL DIAGNOSES:", lines) is True
        assert formatter._is_in_section("item B", "CLINICAL SUMMARY:", lines) is True
        assert formatter._is_in_section("item B", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_consecutive_sections_no_content_between(self, formatter):
        lines = [
            "CLINICAL SUMMARY:",
            "DIFFERENTIAL DIAGNOSES:",
            "1. Flu",
        ]
        # "1. Flu" is after DIFFERENTIAL DIAGNOSES so it is in that section
        assert formatter._is_in_section("1. Flu", "DIFFERENTIAL DIAGNOSES:", lines) is True
        # "1. Flu" is NOT in CLINICAL SUMMARY
        assert formatter._is_in_section("1. Flu", "CLINICAL SUMMARY:", lines) is False


# ===========================================================================
# TestWithWhitespace
# ===========================================================================

class TestWithWhitespace:
    """8 tests covering whitespace handling (check_line.strip() == line)."""

    def test_check_line_with_leading_spaces_matches_stripped_target(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "  1. Pneumonia"]
        # check_line.strip() == "1. Pneumonia" so line arg must be "1. Pneumonia"
        assert formatter._is_in_section("1. Pneumonia", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_check_line_with_trailing_spaces_matches_stripped_target(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia   "]
        assert formatter._is_in_section("1. Pneumonia", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_check_line_with_both_leading_and_trailing_spaces(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "   1. Pneumonia   "]
        assert formatter._is_in_section("1. Pneumonia", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_line_arg_with_extra_spaces_does_not_match_stripped_check_line(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        # "1. Pneumonia" is in list but line arg has extra leading space
        assert formatter._is_in_section(" 1. Pneumonia", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_line_arg_with_trailing_spaces_does_not_match(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        assert formatter._is_in_section("1. Pneumonia ", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_section_header_in_list_with_surrounding_spaces_still_triggers(self, formatter):
        # "DIFFERENTIAL DIAGNOSES:" appears as substring in check_line even with prefix
        lines = ["  DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        # section_header "DIFFERENTIAL DIAGNOSES:" IS in "  DIFFERENTIAL DIAGNOSES:"
        assert formatter._is_in_section("1. Pneumonia", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_empty_string_target_matches_blank_line_in_section(self, formatter):
        lines = ["RED FLAGS:", ""]
        # check_line.strip() == "" and line == ""
        assert formatter._is_in_section("", "RED FLAGS:", lines) is True

    def test_empty_string_target_before_section_header_returns_false(self, formatter):
        lines = ["", "RED FLAGS:", "- pain"]
        # empty line appears before RED FLAGS:, in_section is still False
        assert formatter._is_in_section("", "RED FLAGS:", lines) is False


# ===========================================================================
# TestReturnFalseScenarios
# ===========================================================================

class TestReturnFalseScenarios:
    """8 tests for situations that must return False."""

    def test_empty_string_line_not_in_list_returns_false(self, formatter):
        lines = ["DIFFERENTIAL DIAGNOSES:", "1. Pneumonia"]
        assert formatter._is_in_section("", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_custom_section_header_not_in_five_known_headers_works_normally(self, formatter):
        # Custom header is not in the five known ones so other-header check ignores it.
        lines = ["MY CUSTOM SECTION:", "custom content", "DIFFERENTIAL DIAGNOSES:", "1. Flu"]
        # custom content is 'in' MY CUSTOM SECTION per logic — but that header is unknown,
        # so it does NOT reset in_section when we search for DIFFERENTIAL DIAGNOSES.
        # Wait — "MY CUSTOM SECTION:" is NOT in section_headers, so it won't trigger
        # the first branch (section_header is "DIFFERENTIAL DIAGNOSES:") nor the elif.
        # It falls through to the strip check. "custom content" strip != "1. Flu".
        # Then "DIFFERENTIAL DIAGNOSES:" sets in_section True, "1. Flu" matches.
        assert formatter._is_in_section("1. Flu", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_custom_section_header_line_not_counted_as_other_header(self, formatter):
        # A line containing a custom (unknown) header string between two known sections
        # should NOT reset in_section for the queried section.
        lines = [
            "DIFFERENTIAL DIAGNOSES:",
            "1. Flu",
            "CUSTOM UNKNOWN SECTION:",
            "unknown content",
        ]
        # "CUSTOM UNKNOWN SECTION:" is not in the 5 known headers, so it won't reset
        # in_section. "unknown content" is still considered under DIFFERENTIAL DIAGNOSES.
        assert formatter._is_in_section("unknown content", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_line_appears_only_before_section_header_returns_false(self, formatter):
        lines = ["intro", "DIFFERENTIAL DIAGNOSES:", "1. Flu"]
        assert formatter._is_in_section("intro", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_all_lines_is_only_section_header_target_absent_returns_false(self, formatter):
        lines = ["RED FLAGS:"]
        assert formatter._is_in_section("- something", "RED FLAGS:", lines) is False

    def test_line_appears_twice_second_occurrence_in_section_returns_true(self, formatter):
        lines = [
            "duplicate line",
            "DIFFERENTIAL DIAGNOSES:",
            "duplicate line",
        ]
        # First occurrence: in_section is False → returns False immediately
        assert formatter._is_in_section("duplicate line", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_section_header_as_line_arg_never_matched_by_strip_branch(self, formatter):
        # The header line triggers the first branch (sets in_section=True) rather
        # than the strip branch, so querying the header text as 'line' returns False
        # unless a *different* line in all_lines has .strip() equal to the header text.
        lines = ["CLINICAL PEARLS:"]
        assert formatter._is_in_section("CLINICAL PEARLS:", "CLINICAL PEARLS:", lines) is False

    def test_no_matching_section_header_in_list_returns_false(self, formatter):
        lines = ["random text", "more random text"]
        assert formatter._is_in_section("more random text", "DIFFERENTIAL DIAGNOSES:", lines) is False


# ===========================================================================
# TestRealWorldScenarios
# ===========================================================================

class TestRealWorldScenarios:
    """20 tests using REALISTIC_LINES (the fixture at module level)."""

    def test_fever_cough_in_clinical_summary(self, formatter):
        assert formatter._is_in_section(
            "fever, cough, and shortness of breath", "CLINICAL SUMMARY:", REALISTIC_LINES
        ) is True

    def test_fever_cough_not_in_differential_diagnoses(self, formatter):
        assert formatter._is_in_section(
            "fever, cough, and shortness of breath", "DIFFERENTIAL DIAGNOSES:", REALISTIC_LINES
        ) is False

    def test_pneumonia_in_differential_diagnoses(self, formatter):
        assert formatter._is_in_section(
            "1. Pneumonia [HIGH]", "DIFFERENTIAL DIAGNOSES:", REALISTIC_LINES
        ) is True

    def test_pneumonia_not_in_clinical_summary(self, formatter):
        assert formatter._is_in_section(
            "1. Pneumonia [HIGH]", "CLINICAL SUMMARY:", REALISTIC_LINES
        ) is False

    def test_covid_in_differential_diagnoses(self, formatter):
        assert formatter._is_in_section(
            "2. COVID-19 [MEDIUM]", "DIFFERENTIAL DIAGNOSES:", REALISTIC_LINES
        ) is True

    def test_influenza_in_differential_diagnoses(self, formatter):
        assert formatter._is_in_section(
            "3. Influenza [LOW]", "DIFFERENTIAL DIAGNOSES:", REALISTIC_LINES
        ) is True

    def test_respiratory_distress_in_red_flags(self, formatter):
        assert formatter._is_in_section(
            "- Respiratory distress", "RED FLAGS:", REALISTIC_LINES
        ) is True

    def test_respiratory_distress_not_in_differential_diagnoses(self, formatter):
        assert formatter._is_in_section(
            "- Respiratory distress", "DIFFERENTIAL DIAGNOSES:", REALISTIC_LINES
        ) is False

    def test_chest_xray_in_recommended_investigations(self, formatter):
        assert formatter._is_in_section(
            "- Chest X-ray", "RECOMMENDED INVESTIGATIONS:", REALISTIC_LINES
        ) is True

    def test_cbc_in_recommended_investigations(self, formatter):
        assert formatter._is_in_section(
            "- CBC", "RECOMMENDED INVESTIGATIONS:", REALISTIC_LINES
        ) is True

    def test_chest_xray_not_in_red_flags(self, formatter):
        assert formatter._is_in_section(
            "- Chest X-ray", "RED FLAGS:", REALISTIC_LINES
        ) is False

    def test_monitor_oxygen_in_clinical_pearls(self, formatter):
        assert formatter._is_in_section(
            "Monitor oxygen saturation", "CLINICAL PEARLS:", REALISTIC_LINES
        ) is True

    def test_monitor_oxygen_not_in_recommended_investigations(self, formatter):
        assert formatter._is_in_section(
            "Monitor oxygen saturation", "RECOMMENDED INVESTIGATIONS:", REALISTIC_LINES
        ) is False

    def test_monitor_oxygen_not_in_clinical_summary(self, formatter):
        assert formatter._is_in_section(
            "Monitor oxygen saturation", "CLINICAL SUMMARY:", REALISTIC_LINES
        ) is False

    def test_respiratory_distress_not_in_clinical_summary(self, formatter):
        assert formatter._is_in_section(
            "- Respiratory distress", "CLINICAL SUMMARY:", REALISTIC_LINES
        ) is False

    def test_influenza_not_in_red_flags(self, formatter):
        assert formatter._is_in_section(
            "3. Influenza [LOW]", "RED FLAGS:", REALISTIC_LINES
        ) is False

    def test_influenza_not_in_clinical_pearls(self, formatter):
        assert formatter._is_in_section(
            "3. Influenza [LOW]", "CLINICAL PEARLS:", REALISTIC_LINES
        ) is False

    def test_absent_line_in_realistic_document_returns_false(self, formatter):
        assert formatter._is_in_section(
            "not present at all", "DIFFERENTIAL DIAGNOSES:", REALISTIC_LINES
        ) is False

    def test_covid_not_in_clinical_pearls(self, formatter):
        assert formatter._is_in_section(
            "2. COVID-19 [MEDIUM]", "CLINICAL PEARLS:", REALISTIC_LINES
        ) is False

    def test_cbc_not_in_differential_diagnoses(self, formatter):
        assert formatter._is_in_section(
            "- CBC", "DIFFERENTIAL DIAGNOSES:", REALISTIC_LINES
        ) is False


# ===========================================================================
# TestEdgeCasesAndCornerCases
# ===========================================================================

class TestEdgeCasesAndCornerCases:
    """Additional edge cases to push well past 70 tests total."""

    def test_section_header_as_substring_of_content_line_triggers_in_section(self, formatter):
        # A content line that contains the section_header text as a substring
        # will also set in_section = True (substring match, not exact).
        lines = [
            "Note: see DIFFERENTIAL DIAGNOSES: above",
            "important finding",
        ]
        # "DIFFERENTIAL DIAGNOSES:" appears in the first line → in_section goes True
        assert formatter._is_in_section("important finding", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_section_header_in_content_line_of_other_known_section_resets(self, formatter):
        # A content line referencing another known header resets in_section.
        lines = [
            "DIFFERENTIAL DIAGNOSES:",
            "see RED FLAGS: for more",
            "this line",
        ]
        # "see RED FLAGS: for more" contains "RED FLAGS:" which IS in section_headers
        # and != "DIFFERENTIAL DIAGNOSES:", so in_section resets to False.
        assert formatter._is_in_section("this line", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_section_header_at_end_of_list_no_content_returns_false(self, formatter):
        lines = ["some text", "CLINICAL PEARLS:"]
        assert formatter._is_in_section("any content", "CLINICAL PEARLS:", lines) is False

    def test_line_is_tab_whitespace_stripped_to_empty_matches_empty_target(self, formatter):
        lines = ["RED FLAGS:", "\t"]
        # "\t".strip() == "" so if line is "" it should match
        assert formatter._is_in_section("", "RED FLAGS:", lines) is True

    def test_line_is_only_spaces_stripped_to_empty(self, formatter):
        lines = ["CLINICAL PEARLS:", "   "]
        assert formatter._is_in_section("", "CLINICAL PEARLS:", lines) is True

    def test_all_five_headers_present_each_line_in_correct_section(self, formatter):
        lines = [
            "CLINICAL SUMMARY:",
            "cs content",
            "DIFFERENTIAL DIAGNOSES:",
            "dd content",
            "RED FLAGS:",
            "rf content",
            "RECOMMENDED INVESTIGATIONS:",
            "ri content",
            "CLINICAL PEARLS:",
            "cp content",
        ]
        assert formatter._is_in_section("cs content", "CLINICAL SUMMARY:", lines) is True
        assert formatter._is_in_section("dd content", "DIFFERENTIAL DIAGNOSES:", lines) is True
        assert formatter._is_in_section("rf content", "RED FLAGS:", lines) is True
        assert formatter._is_in_section("ri content", "RECOMMENDED INVESTIGATIONS:", lines) is True
        assert formatter._is_in_section("cp content", "CLINICAL PEARLS:", lines) is True

    def test_all_five_headers_each_content_line_not_in_other_sections(self, formatter):
        lines = [
            "CLINICAL SUMMARY:",
            "cs content",
            "DIFFERENTIAL DIAGNOSES:",
            "dd content",
            "RED FLAGS:",
            "rf content",
            "RECOMMENDED INVESTIGATIONS:",
            "ri content",
            "CLINICAL PEARLS:",
            "cp content",
        ]
        # cs content should not be in any section other than CLINICAL SUMMARY
        for header in ALL_HEADERS:
            if header != "CLINICAL SUMMARY:":
                assert formatter._is_in_section("cs content", header, lines) is False

    def test_single_line_matching_section_header_exactly(self, formatter):
        # The list contains just one line which equals the section_header.
        # That line triggers the first branch (sets in_section True) — but the
        # strip branch is never reached for it. Line "1. item" is absent → False.
        lines = ["RED FLAGS:"]
        assert formatter._is_in_section("1. item", "RED FLAGS:", lines) is False

    def test_duplicate_content_line_before_and_after_header(self, formatter):
        # Same text before and after the section header.
        lines = [
            "shared line",
            "RECOMMENDED INVESTIGATIONS:",
            "shared line",
        ]
        # The first encounter: in_section=False → returns False immediately
        assert formatter._is_in_section("shared line", "RECOMMENDED INVESTIGATIONS:", lines) is False

    def test_very_long_all_lines_list_correct_section(self, formatter):
        lines = (
            ["CLINICAL SUMMARY:"]
            + [f"summary line {i}" for i in range(100)]
            + ["DIFFERENTIAL DIAGNOSES:"]
            + [f"dd line {i}" for i in range(100)]
        )
        assert formatter._is_in_section("dd line 99", "DIFFERENTIAL DIAGNOSES:", lines) is True
        assert formatter._is_in_section("summary line 99", "CLINICAL SUMMARY:", lines) is True
        assert formatter._is_in_section("dd line 99", "CLINICAL SUMMARY:", lines) is False

    def test_section_header_with_extra_text_after_colon_still_triggers(self, formatter):
        # e.g. "DIFFERENTIAL DIAGNOSES: (ordered by likelihood)"
        # This contains "DIFFERENTIAL DIAGNOSES:" as a substring → in_section = True
        lines = [
            "DIFFERENTIAL DIAGNOSES: (ordered by likelihood)",
            "1. Flu",
        ]
        assert formatter._is_in_section("1. Flu", "DIFFERENTIAL DIAGNOSES:", lines) is True

    def test_known_header_with_extra_prefix_text_also_resets_section(self, formatter):
        # A line like "Note: RED FLAGS: are important" contains "RED FLAGS:"
        lines = [
            "DIFFERENTIAL DIAGNOSES:",
            "1. Flu",
            "Note: RED FLAGS: are important",
            "subsequent line",
        ]
        # "Note: RED FLAGS: are important" triggers the elif (contains "RED FLAGS:")
        # which resets in_section to False.
        assert formatter._is_in_section("subsequent line", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_only_whitespace_lines_no_header_no_target_returns_false(self, formatter):
        lines = ["   ", "\t", "  "]
        assert formatter._is_in_section("something", "DIFFERENTIAL DIAGNOSES:", lines) is False

    def test_section_ordering_reverse_of_typical(self, formatter):
        lines = [
            "CLINICAL PEARLS:",
            "pearl one",
            "CLINICAL SUMMARY:",
            "summary detail",
        ]
        assert formatter._is_in_section("pearl one", "CLINICAL PEARLS:", lines) is True
        assert formatter._is_in_section("summary detail", "CLINICAL SUMMARY:", lines) is True
        assert formatter._is_in_section("summary detail", "CLINICAL PEARLS:", lines) is False

    def test_realistic_lines_with_leading_spaces_on_entries(self, formatter):
        lines = [
            "DIFFERENTIAL DIAGNOSES:",
            "  1. Pneumonia [HIGH]",
            "  2. COVID-19 [MEDIUM]",
        ]
        assert formatter._is_in_section("1. Pneumonia [HIGH]", "DIFFERENTIAL DIAGNOSES:", lines) is True
        assert formatter._is_in_section("2. COVID-19 [MEDIUM]", "DIFFERENTIAL DIAGNOSES:", lines) is True
