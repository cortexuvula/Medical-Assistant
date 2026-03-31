"""
Pure-method tests for SynopsisAgent.

Covers:
  - _build_prompt(soap_note, context)
  - _clean_synopsis(synopsis)
  - _truncate_to_word_limit(text, word_limit)

No real AI calls are made; the agent is constructed with a MagicMock caller.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.synopsis import SynopsisAgent


@pytest.fixture
def agent():
    mock_caller = MagicMock()
    mock_caller.call.return_value = "mocked response"
    return SynopsisAgent(ai_caller=mock_caller)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_SOAP = "S: headache\nO: normal\nA: tension headache\nP: ibuprofen"


# ===========================================================================
# TestBuildPrompt
# ===========================================================================

class TestBuildPrompt:
    """Tests for SynopsisAgent._build_prompt."""

    # --- No context ---

    def test_no_context_does_not_contain_additional_context_label(self, agent):
        result = agent._build_prompt(SIMPLE_SOAP)
        assert "Additional Context" not in result

    def test_no_context_contains_instruction_line(self, agent):
        result = agent._build_prompt(SIMPLE_SOAP)
        assert "Please create a clinical synopsis (under 200 words) for the following SOAP note:" in result

    def test_no_context_contains_soap_note_header_and_body(self, agent):
        result = agent._build_prompt(SIMPLE_SOAP)
        assert f"SOAP Note:\n{SIMPLE_SOAP}\n" in result

    def test_no_context_ends_with_synopsis_label(self, agent):
        result = agent._build_prompt(SIMPLE_SOAP)
        assert result.endswith("Synopsis:")

    def test_no_context_is_join_of_three_parts(self, agent):
        soap = "S: cough\nO: clear lungs\nA: URI\nP: rest"
        expected = "\n".join([
            "Please create a clinical synopsis (under 200 words) for the following SOAP note:\n",
            f"SOAP Note:\n{soap}\n",
            "Synopsis:",
        ])
        assert agent._build_prompt(soap) == expected

    # --- With context ---

    def test_with_context_starts_with_additional_context_block(self, agent):
        ctx = "Patient has diabetes"
        result = agent._build_prompt(SIMPLE_SOAP, context=ctx)
        assert result.startswith(f"Additional Context: {ctx}\n")

    def test_with_context_still_contains_soap_note(self, agent):
        result = agent._build_prompt(SIMPLE_SOAP, context="some context")
        assert f"SOAP Note:\n{SIMPLE_SOAP}\n" in result

    def test_with_context_still_ends_with_synopsis_label(self, agent):
        result = agent._build_prompt(SIMPLE_SOAP, context="ctx")
        assert result.endswith("Synopsis:")

    def test_with_context_is_join_of_four_parts(self, agent):
        soap = "S: fatigue\nO: normal\nA: anemia\nP: iron"
        ctx = "Patient is elderly"
        expected = "\n".join([
            f"Additional Context: {ctx}\n",
            "Please create a clinical synopsis (under 200 words) for the following SOAP note:\n",
            f"SOAP Note:\n{soap}\n",
            "Synopsis:",
        ])
        assert agent._build_prompt(soap, context=ctx) == expected

    # --- Edge cases ---

    def test_empty_soap_note_produces_empty_soap_block(self, agent):
        result = agent._build_prompt("")
        assert "SOAP Note:\n\n" in result

    def test_empty_string_context_is_falsy_not_prepended(self, agent):
        result = agent._build_prompt(SIMPLE_SOAP, context="")
        assert "Additional Context" not in result

    def test_none_context_not_prepended(self, agent):
        result = agent._build_prompt(SIMPLE_SOAP, context=None)
        assert "Additional Context" not in result

    def test_multi_line_soap_note_preserved_exactly(self, agent):
        soap = "S: line1\nS: line2\nO: obs\nA: diag\nP: plan\nP: followup"
        result = agent._build_prompt(soap)
        assert f"SOAP Note:\n{soap}\n" in result

    def test_soap_note_with_special_characters_preserved(self, agent):
        soap = "S: pain (8/10) w/ radiation\nO: BP 140/90\nA: HTN\nP: lisinopril 10mg"
        result = agent._build_prompt(soap)
        assert f"SOAP Note:\n{soap}\n" in result

    def test_context_with_embedded_newlines_preserved_as_is(self, agent):
        ctx = "Line A\nLine B"
        result = agent._build_prompt(SIMPLE_SOAP, context=ctx)
        assert f"Additional Context: {ctx}\n" in result

    def test_exact_output_structure_without_context(self, agent):
        soap = "S: nausea\nO: mild\nA: gastritis\nP: antacid"
        parts = [
            "Please create a clinical synopsis (under 200 words) for the following SOAP note:\n",
            f"SOAP Note:\n{soap}\n",
            "Synopsis:",
        ]
        assert agent._build_prompt(soap) == "\n".join(parts)

    def test_exact_output_structure_with_context(self, agent):
        soap = "S: nausea\nO: mild\nA: gastritis\nP: antacid"
        ctx = "Post-op day 1"
        parts = [
            f"Additional Context: {ctx}\n",
            "Please create a clinical synopsis (under 200 words) for the following SOAP note:\n",
            f"SOAP Note:\n{soap}\n",
            "Synopsis:",
        ]
        assert agent._build_prompt(soap, context=ctx) == "\n".join(parts)

    def test_full_soap_note_embedded_correctly(self, agent):
        soap = "S: chest pain\nO: normal\nA: angina\nP: nitro"
        result = agent._build_prompt(soap)
        assert "S: chest pain\nO: normal\nA: angina\nP: nitro" in result

    def test_very_long_soap_note_builds_correctly(self, agent):
        soap = ("S: " + "word " * 300).strip()
        result = agent._build_prompt(soap)
        assert soap in result
        assert result.endswith("Synopsis:")

    def test_context_value_appears_as_full_additional_context_line(self, agent):
        ctx = "Patient has diabetes"
        result = agent._build_prompt(SIMPLE_SOAP, context=ctx)
        assert f"Additional Context: Patient has diabetes\n" in result

    def test_no_context_result_contains_exactly_three_newline_joined_parts(self, agent):
        soap = "S: test\nO: test\nA: test\nP: test"
        result = agent._build_prompt(soap)
        # Split on the joining newlines between parts — expect 3 parts
        parts = result.split("\n\n")
        # The join character is \n (single), so let's verify part count differently:
        # Each part is joined by single \n, so count the three fixed strings
        assert result.count("Please create a clinical synopsis") == 1
        assert result.count("SOAP Note:") == 1
        assert result.count("Synopsis:") == 1

    def test_context_with_special_chars_preserved(self, agent):
        ctx = "HbA1c > 9%, BP: 140/90"
        result = agent._build_prompt(SIMPLE_SOAP, context=ctx)
        assert f"Additional Context: {ctx}\n" in result


# ===========================================================================
# TestCleanSynopsis
# ===========================================================================

class TestCleanSynopsis:
    """Tests for SynopsisAgent._clean_synopsis."""

    def test_leading_whitespace_stripped(self, agent):
        assert agent._clean_synopsis("   text") == "text"

    def test_trailing_whitespace_stripped(self, agent):
        assert agent._clean_synopsis("text   ") == "text"

    def test_both_sides_whitespace_stripped(self, agent):
        assert agent._clean_synopsis("  text  ") == "text"

    def test_double_asterisk_bold_removed(self, agent):
        assert agent._clean_synopsis("**bold**") == "bold"

    def test_single_asterisk_italic_removed(self, agent):
        assert agent._clean_synopsis("*italic*") == "italic"

    def test_mix_of_double_and_single_asterisk_removed(self, agent):
        result = agent._clean_synopsis("**bold** and *italic*")
        assert result == "bold and italic"

    def test_no_markdown_unchanged(self, agent):
        text = "Patient presents with chest pain."
        assert agent._clean_synopsis(text) == text

    def test_synopsis_prefix_removed(self, agent):
        result = agent._clean_synopsis("Synopsis: The patient presents.")
        assert result == "The patient presents."

    def test_summary_prefix_removed(self, agent):
        result = agent._clean_synopsis("Summary: The patient presents.")
        assert result == "The patient presents."

    def test_clinical_synopsis_prefix_removed(self, agent):
        result = agent._clean_synopsis("Clinical Synopsis: The patient presents.")
        assert result == "The patient presents."

    def test_prefix_check_is_case_sensitive_lowercase_not_stripped(self, agent):
        text = "synopsis: should not be stripped"
        assert agent._clean_synopsis(text) == text

    def test_prefix_check_case_sensitive_summary_lowercase_not_stripped(self, agent):
        text = "summary: should not be stripped"
        assert agent._clean_synopsis(text) == text

    def test_synopsis_prefix_strips_and_remaining_checked_for_second_prefix(self, agent):
        # After stripping "Synopsis:" the rest is "Summary: content".
        # The loop continues and would strip "Summary:" too.
        result = agent._clean_synopsis("Synopsis: Summary: content")
        assert result == "content"

    def test_leading_whitespace_on_result_after_prefix_strip(self, agent):
        result = agent._clean_synopsis("  Synopsis: content  ")
        assert result == "content"

    def test_synopsis_with_extra_spaces_after_prefix_stripped(self, agent):
        result = agent._clean_synopsis("Synopsis:   spaced content")
        assert result == "spaced content"

    def test_multiple_double_asterisk_sequences_all_removed(self, agent):
        result = agent._clean_synopsis("**bold** and **more**")
        assert result == "bold and more"

    def test_empty_string_returns_empty_string(self, agent):
        assert agent._clean_synopsis("") == ""

    def test_only_whitespace_returns_empty_string(self, agent):
        assert agent._clean_synopsis("   ") == ""

    def test_synopsis_prefix_only_returns_empty(self, agent):
        assert agent._clean_synopsis("Synopsis:") == ""

    def test_summary_prefix_only_returns_empty(self, agent):
        assert agent._clean_synopsis("Summary:") == ""

    def test_no_prefix_no_markdown_returned_as_is_after_strip(self, agent):
        text = "Patient is a 45-year-old male."
        assert agent._clean_synopsis(text) == text

    def test_asterisk_in_middle_of_word_removed(self, agent):
        result = agent._clean_synopsis("some*thing")
        assert result == "something"

    def test_clinical_synopsis_prefix_with_extra_whitespace(self, agent):
        result = agent._clean_synopsis("Clinical Synopsis:  content here")
        assert result == "content here"

    def test_real_world_synopsis_with_markdown(self, agent):
        raw = "Synopsis: **Patient** presents with *hypertension* and diabetes."
        result = agent._clean_synopsis(raw)
        assert result == "Patient presents with hypertension and diabetes."

    def test_whitespace_only_after_prefix_strip_returns_empty(self, agent):
        result = agent._clean_synopsis("Synopsis:   ")
        assert result == ""

    def test_newlines_in_synopsis_preserved_after_strip(self, agent):
        text = "Line one.\nLine two."
        assert agent._clean_synopsis(text) == text

    def test_triple_asterisk_reduces_correctly(self, agent):
        # "***text***": replace '**' first → '*text*', then replace '*' → 'text'
        result = agent._clean_synopsis("***text***")
        assert result == "text"


# ===========================================================================
# TestTruncateToWordLimit
# ===========================================================================

class TestTruncateToWordLimit:
    """Tests for SynopsisAgent._truncate_to_word_limit."""

    # --- At or below limit: return unchanged ---

    def test_fewer_words_than_limit_returned_unchanged(self, agent):
        text = "This is five words here"
        assert agent._truncate_to_word_limit(text, 10) == text

    def test_exact_word_count_equals_limit_returned_unchanged(self, agent):
        text = "one two three four five"
        assert agent._truncate_to_word_limit(text, 5) == text

    def test_single_word_within_limit_returned_unchanged(self, agent):
        text = "word"
        assert agent._truncate_to_word_limit(text, 1) == text

    def test_single_word_with_large_limit_returned_unchanged(self, agent):
        text = "word"
        assert agent._truncate_to_word_limit(text, 100) == text

    def test_empty_string_with_positive_limit_returned_as_is(self, agent):
        # len([]) == 0 <= any positive limit
        assert agent._truncate_to_word_limit("", 5) == ""

    # --- Over limit with sentence boundaries ---

    def test_truncation_ends_at_last_period(self, agent):
        # 10 words, limit 6: "one two three four five six" → find last '.'
        text = "one two. three four. five six seven eight nine ten"
        result = agent._truncate_to_word_limit(text, 6)
        assert result.endswith(".")
        assert "seven" not in result

    def test_truncation_ends_at_question_mark(self, agent):
        text = "Is the patient stable? more words here extra filler now"
        result = agent._truncate_to_word_limit(text, 5)
        assert result.endswith("?")

    def test_truncation_ends_at_exclamation_mark(self, agent):
        text = "Stop the medication! additional words beyond the limit here"
        result = agent._truncate_to_word_limit(text, 4)
        assert result.endswith("!")

    def test_no_sentence_ending_punctuation_appends_ellipsis(self, agent):
        text = "one two three four five six seven eight"
        result = agent._truncate_to_word_limit(text, 4)
        assert result.endswith("...")

    def test_truncation_does_not_include_words_beyond_limit(self, agent):
        text = "word " * 20
        text = text.strip()
        result = agent._truncate_to_word_limit(text, 10)
        # Should not include more than 10 words (before sentence-boundary search)
        # The sentence boundary search only looks within the truncated text
        assert len(result.split()) <= 10 or result.endswith("...")

    def test_multiple_sentences_truncates_at_last_complete_sentence(self, agent):
        text = "First sentence ends here. Second sentence here. Third goes beyond limit now extra"
        result = agent._truncate_to_word_limit(text, 8)
        assert result.endswith(".")
        # "beyond" is word 9, so it should not be present
        assert "beyond" not in result

    def test_period_at_end_of_truncated_text_included(self, agent):
        # Exactly at the last truncated word position
        text = "Alpha beta gamma. delta epsilon zeta eta theta"
        result = agent._truncate_to_word_limit(text, 3)
        assert result == "Alpha beta gamma."

    def test_word_limit_one_with_multi_word_input_produces_ellipsis_or_sentence(self, agent):
        text = "Hello world today"
        result = agent._truncate_to_word_limit(text, 1)
        # truncated_text = "Hello", no sentence ending → "Hello..."
        assert result == "Hello..."

    def test_word_limit_one_with_sentence_ending(self, agent):
        text = "Hello. world today"
        result = agent._truncate_to_word_limit(text, 1)
        # truncated_text = "Hello.", rfind('.') = 5 → returns "Hello."
        assert result == "Hello."

    def test_word_limit_zero_single_word_produces_ellipsis(self, agent):
        # len(["word"]) = 1 > 0, so truncate; words[:0] = []
        # truncated_text = "", all rfind = -1, last_sentence_end = -1 (NOT > 0)
        result = agent._truncate_to_word_limit("word", 0)
        assert result == "..."

    def test_twenty_word_text_truncated_to_ten(self, agent):
        words = [f"w{i}" for i in range(20)]
        text = " ".join(words)
        result = agent._truncate_to_word_limit(text, 10)
        # No periods in these words, so should end with "..."
        assert result.endswith("...")
        assert "w10" not in result

    def test_truncation_lands_exactly_on_period(self, agent):
        # Word 5 is "done." so truncated_text ends with period
        text = "one two three four done. six seven eight nine ten"
        result = agent._truncate_to_word_limit(text, 5)
        assert result.endswith("done.")

    def test_period_deep_in_truncated_region_used_as_boundary(self, agent):
        text = "Start here. More words without punctuation filler extra beyond"
        # limit 7: "Start here. More words without punctuation"
        result = agent._truncate_to_word_limit(text, 7)
        assert result.endswith(".")

    def test_multiple_periods_uses_last_one_in_truncated_text(self, agent):
        text = "First. Second. Third. fourth fifth sixth seventh eighth"
        result = agent._truncate_to_word_limit(text, 6)
        # truncated = "First. Second. Third. fourth fifth sixth"
        # last period is after "Third"
        assert result == "First. Second. Third."

    def test_no_period_but_has_question_mark(self, agent):
        text = "Is this correct? more words beyond the limit here now"
        result = agent._truncate_to_word_limit(text, 5)
        assert result.endswith("?")

    def test_all_three_punctuations_uses_max_position(self, agent):
        # Construct so that '!' comes last in truncated region
        text = "First? Second! more words beyond limit here"
        result = agent._truncate_to_word_limit(text, 4)
        # truncated = "First? Second! more words"
        # period=-1, question=6, exclamation=14 → max=14
        assert result.endswith("!")

    def test_question_mark_after_exclamation_uses_question(self, agent):
        text = "Stop! Really? more words beyond limit extra"
        result = agent._truncate_to_word_limit(text, 4)
        # truncated = "Stop! Really? more words"
        # period=-1, question=13, exclamation=5 → max=13
        assert result.endswith("?")

    def test_last_sentence_end_at_position_zero_not_used(self, agent):
        # If the only punctuation is at index 0 (e.g. "? word word word word")
        # last_sentence_end = 0, NOT > 0 → return truncated_text + "..."
        text = "? word word word word word word word word"
        result = agent._truncate_to_word_limit(text, 3)
        # truncated = "? word word", period=-1, question=0, exclamation=-1
        # max = 0, NOT > 0 → "? word word..."
        assert result.endswith("...")

    def test_sentence_end_at_position_one_is_used(self, agent):
        # "a. word word word" → truncated "a. word" (limit 2)
        # rfind('.') = 1, which is > 0 → return "a."
        text = "a. word word word word word word word"
        result = agent._truncate_to_word_limit(text, 2)
        assert result == "a."

    def test_200_word_text_truncated_to_150_with_sentence_boundary(self, agent):
        # Build 200 words in groups of 10 words each ending with a period
        sentences = []
        for i in range(20):
            sentences.append(" ".join([f"w{i}_{j}" for j in range(9)]) + ".")
        text = " ".join(sentences)
        result = agent._truncate_to_word_limit(text, 150)
        assert result.endswith(".")
        assert len(result.split()) <= 150

    def test_result_does_not_start_with_space(self, agent):
        text = "word " * 20
        text = text.strip()
        result = agent._truncate_to_word_limit(text, 10)
        assert not result.startswith(" ")

    def test_ellipsis_not_added_when_sentence_boundary_found(self, agent):
        text = "First sentence done. more overflow words here extra"
        result = agent._truncate_to_word_limit(text, 4)
        assert not result.endswith("...")
        assert result.endswith(".")

    def test_preserves_medical_abbreviations_before_truncation(self, agent):
        text = "Patient presents with HTN. BP 140/90. HR 72. additional filler words here beyond"
        result = agent._truncate_to_word_limit(text, 6)
        assert result.endswith(".")
        assert "HTN" in result or "140/90" in result
