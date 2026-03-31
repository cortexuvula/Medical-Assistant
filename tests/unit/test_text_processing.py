"""Tests for clean_text in src/ai/text_processing.py.

Only clean_text is tested here. The network-dependent functions
adjust_text_with_openai and improve_text_with_openai are excluded.
No network, no Tkinter, no filesystem I/O.
"""

import sys
import types
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# ---------------------------------------------------------------------------
# Stub out heavy transitive dependencies so the pure-regex clean_text can be
# imported without network-capable provider packages (httpx, openai, etc.).
# ---------------------------------------------------------------------------
_stub_router = types.ModuleType("ai.providers.router")
_stub_router.call_ai = lambda *a, **kw: None
sys.modules.setdefault("ai.providers.router", _stub_router)

_stub_providers_pkg = types.ModuleType("ai.providers")
sys.modules.setdefault("ai.providers", _stub_providers_pkg)

_stub_prompts = types.ModuleType("ai.prompts")
for _attr in ("REFINE_PROMPT", "REFINE_SYSTEM_MESSAGE", "IMPROVE_PROMPT", "IMPROVE_SYSTEM_MESSAGE"):
    setattr(_stub_prompts, _attr, "")
sys.modules.setdefault("ai.prompts", _stub_prompts)

_stub_settings_mod = types.ModuleType("settings.settings_manager")
_stub_settings_mod.settings_manager = types.SimpleNamespace(get_model_config=lambda *a, **kw: {})
sys.modules.setdefault("settings.settings_manager", _stub_settings_mod)
sys.modules.setdefault("settings", types.ModuleType("settings"))

from ai.text_processing import clean_text  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Empty string
# ---------------------------------------------------------------------------

class TestEmptyString:
    def test_empty_string_returns_empty(self):
        assert clean_text("") == ""

    def test_empty_string_remove_markdown_false(self):
        assert clean_text("", remove_markdown=False) == ""

    def test_empty_string_remove_citations_false(self):
        assert clean_text("", remove_citations=False) == ""

    def test_empty_string_both_false(self):
        assert clean_text("", remove_markdown=False, remove_citations=False) == ""

    def test_empty_string_returns_str_type(self):
        assert isinstance(clean_text(""), str)


# ---------------------------------------------------------------------------
# 2. Plain text unchanged
# ---------------------------------------------------------------------------

class TestPlainText:
    def test_plain_text_unchanged(self):
        text = "Patient presents with fever and cough."
        assert clean_text(text) == text

    def test_plain_text_with_numbers_unchanged(self):
        text = "BP 120/80 mmHg, HR 72 bpm, temp 37.5 C."
        assert clean_text(text) == text

    def test_plain_text_with_commas_unchanged(self):
        text = "Diagnosis: hypertension, diabetes type 2, hyperlipidemia."
        assert clean_text(text) == text

    def test_plain_text_multiword_unchanged(self):
        text = "The patient is a 45-year-old male with no known allergies."
        assert clean_text(text) == text

    def test_returns_str_type(self):
        assert isinstance(clean_text("hello"), str)


# ---------------------------------------------------------------------------
# 3. remove_markdown=True (default) — fenced code blocks
# ---------------------------------------------------------------------------

class TestFencedCodeBlocks:
    def test_fenced_code_block_removed(self):
        text = "Before\n```\nsome code\n```\nAfter"
        result = clean_text(text)
        assert "```" not in result
        assert "some code" not in result

    def test_fenced_code_block_with_language_tag_removed(self):
        text = "Before\n```python\nprint('hello')\n```\nAfter"
        result = clean_text(text)
        assert "```" not in result
        assert "print" not in result

    def test_text_before_code_block_preserved(self):
        text = "Before\n```\ncode\n```\nAfter"
        result = clean_text(text)
        assert "Before" in result

    def test_text_after_code_block_preserved(self):
        text = "Before\n```\ncode\n```\nAfter"
        result = clean_text(text)
        assert "After" in result

    def test_fenced_code_block_only_becomes_empty(self):
        text = "```\nonly code\n```"
        result = clean_text(text)
        assert result == ""

    def test_multiline_fenced_code_block_removed(self):
        text = "Text\n```\nline1\nline2\nline3\n```\nMore text"
        result = clean_text(text)
        assert "line1" not in result
        assert "line2" not in result
        assert "More text" in result


# ---------------------------------------------------------------------------
# 3. remove_markdown=True — inline code keeps content
# ---------------------------------------------------------------------------

class TestInlineCode:
    def test_inline_code_backticks_removed_content_kept(self):
        assert clean_text("`code`") == "code"

    def test_inline_code_in_sentence(self):
        result = clean_text("Use the `print()` function.")
        assert "`" not in result
        assert "print()" in result

    def test_multiple_inline_code_spans(self):
        result = clean_text("`foo` and `bar`")
        assert "`" not in result
        assert "foo" in result
        assert "bar" in result

    def test_inline_code_with_spaces_in_content(self):
        result = clean_text("`some value`")
        assert "`" not in result
        assert "some value" in result


# ---------------------------------------------------------------------------
# 3. remove_markdown=True — heading markers stripped
# ---------------------------------------------------------------------------

class TestHeadings:
    def test_h1_marker_removed(self):
        result = clean_text("# Title")
        assert "#" not in result
        assert "Title" in result

    def test_h2_marker_removed(self):
        result = clean_text("## Section")
        assert "##" not in result
        assert "Section" in result

    def test_h3_marker_removed(self):
        result = clean_text("### Subsection")
        assert "###" not in result
        assert "Subsection" in result

    def test_heading_in_multiline(self):
        text = "# Heading\nBody text."
        result = clean_text(text)
        assert "#" not in result
        assert "Heading" in result
        assert "Body text." in result

    def test_heading_with_leading_whitespace(self):
        result = clean_text("  ## Indented")
        assert "#" not in result
        assert "Indented" in result


# ---------------------------------------------------------------------------
# 3. remove_markdown=True — bold markers
# ---------------------------------------------------------------------------

class TestBold:
    def test_double_asterisk_bold_removed(self):
        assert clean_text("**bold**") == "bold"

    def test_double_underscore_bold_removed(self):
        assert clean_text("__bold__") == "bold"

    def test_bold_in_sentence(self):
        result = clean_text("This is **important** text.")
        assert "**" not in result
        assert "important" in result

    def test_double_underscore_bold_in_sentence(self):
        result = clean_text("This is __critical__ info.")
        assert "__" not in result
        assert "critical" in result

    def test_multiple_bold_spans(self):
        result = clean_text("**A** and **B**")
        assert "**" not in result
        assert "A" in result
        assert "B" in result


# ---------------------------------------------------------------------------
# 3. remove_markdown=True — italic markers
# ---------------------------------------------------------------------------

class TestItalic:
    def test_single_asterisk_italic_removed(self):
        assert clean_text("*italic*") == "italic"

    def test_single_underscore_italic_removed(self):
        assert clean_text("_italic_") == "italic"

    def test_italic_in_sentence(self):
        result = clean_text("The *diagnosis* is confirmed.")
        assert "*diagnosis*" not in result
        assert "diagnosis" in result

    def test_underscore_italic_in_sentence(self):
        result = clean_text("The _prognosis_ is good.")
        assert "_prognosis_" not in result
        assert "prognosis" in result

    def test_multiple_italic_spans(self):
        result = clean_text("*A* and *B*")
        assert "*A*" not in result
        assert "*B*" not in result
        assert "A" in result
        assert "B" in result


# ---------------------------------------------------------------------------
# 4. remove_markdown=False — markers NOT removed
# ---------------------------------------------------------------------------

class TestRemoveMarkdownFalse:
    def test_fenced_code_block_kept(self):
        text = "Before\n```\ncode\n```\nAfter"
        result = clean_text(text, remove_markdown=False)
        assert "```" in result

    def test_inline_code_backticks_kept(self):
        result = clean_text("`code`", remove_markdown=False)
        assert "`code`" in result

    def test_heading_marker_kept(self):
        result = clean_text("## Section", remove_markdown=False)
        assert "##" in result

    def test_bold_asterisk_kept(self):
        result = clean_text("**bold**", remove_markdown=False)
        assert "**bold**" in result

    def test_bold_underscore_kept(self):
        result = clean_text("__bold__", remove_markdown=False)
        assert "__bold__" in result

    def test_italic_asterisk_kept(self):
        result = clean_text("*italic*", remove_markdown=False)
        assert "*italic*" in result

    def test_italic_underscore_kept(self):
        result = clean_text("_italic_", remove_markdown=False)
        assert "_italic_" in result


# ---------------------------------------------------------------------------
# 5. remove_citations=True (default)
# ---------------------------------------------------------------------------

class TestRemoveCitationsTrue:
    def test_single_digit_citation_removed(self):
        result = clean_text("See reference [1].")
        assert "[1]" not in result
        assert "See reference" in result

    def test_two_digit_citation_removed(self):
        result = clean_text("Evidence [12] supports this.")
        assert "[12]" not in result

    def test_consecutive_citations_removed(self):
        result = clean_text("Multiple sources [1][2] agree.")
        assert "[1]" not in result
        assert "[2]" not in result

    def test_three_consecutive_citations_removed(self):
        result = clean_text("Sources [1][2][3] confirm.")
        assert "[1]" not in result
        assert "[2]" not in result
        assert "[3]" not in result

    def test_alphabetic_bracket_not_removed(self):
        # [abc] contains only letters — must NOT be treated as a citation
        result = clean_text("See [abc] for details.")
        assert "[abc]" in result

    def test_mixed_letter_digit_bracket_not_removed(self):
        # [1a] is not all digits — must NOT be removed
        result = clean_text("Note [1a] here.")
        assert "[1a]" in result

    def test_empty_bracket_not_removed(self):
        result = clean_text("Empty [] bracket.")
        assert "[]" in result

    def test_citation_only_input_becomes_empty(self):
        result = clean_text("[1]")
        assert result == ""

    def test_surrounding_text_preserved_after_citation_removal(self):
        result = clean_text("First [1] claim and second [2] claim.")
        assert "[1]" not in result
        assert "[2]" not in result
        assert "First" in result
        assert "claim and second" in result


# ---------------------------------------------------------------------------
# 6. remove_citations=False — citation NOT removed
# ---------------------------------------------------------------------------

class TestRemoveCitationsFalse:
    def test_single_citation_kept(self):
        result = clean_text("See [1] here.", remove_citations=False)
        assert "[1]" in result

    def test_consecutive_citations_kept(self):
        result = clean_text("Sources [1][2].", remove_citations=False)
        assert "[1]" in result
        assert "[2]" in result

    def test_large_citation_number_kept(self):
        result = clean_text("Reference [42].", remove_citations=False)
        assert "[42]" in result


# ---------------------------------------------------------------------------
# 7. Both remove_markdown=False, remove_citations=False
# ---------------------------------------------------------------------------

class TestBothFalse:
    def test_markdown_and_citations_both_kept(self):
        text = "**bold** [1] `code`"
        result = clean_text(text, remove_markdown=False, remove_citations=False)
        assert "**bold**" in result
        assert "[1]" in result
        assert "`code`" in result

    def test_heading_and_citation_both_kept(self):
        text = "## Heading [2]"
        result = clean_text(text, remove_markdown=False, remove_citations=False)
        assert "##" in result
        assert "[2]" in result

    def test_plain_text_both_false_unchanged(self):
        text = "Plain sentence here."
        assert clean_text(text, remove_markdown=False, remove_citations=False) == text

    def test_italic_and_citation_both_kept(self):
        text = "*note* [3]"
        result = clean_text(text, remove_markdown=False, remove_citations=False)
        assert "*note*" in result
        assert "[3]" in result


# ---------------------------------------------------------------------------
# 8. Multiline text with mixed content
# ---------------------------------------------------------------------------

class TestMultilineText:
    def test_multiline_headings_and_body(self):
        text = "## Assessment\nPatient is stable.\n### Plan\nContinue current meds."
        result = clean_text(text)
        assert "#" not in result
        assert "Assessment" in result
        assert "Patient is stable." in result
        assert "Plan" in result
        assert "Continue current meds." in result

    def test_multiline_bold_italic_citation(self):
        text = "**Diagnosis**: pneumonia [1]\n*Treatment*: antibiotics [2]"
        result = clean_text(text)
        assert "**" not in result
        assert "[1]" not in result
        assert "[2]" not in result
        assert "Diagnosis" in result
        assert "pneumonia" in result
        assert "Treatment" in result
        assert "antibiotics" in result

    def test_multiline_code_block_between_text(self):
        text = "Intro paragraph.\n```\ncode here\n```\nConclusion paragraph."
        result = clean_text(text)
        assert "code here" not in result
        assert "Intro paragraph." in result
        assert "Conclusion paragraph." in result


# ---------------------------------------------------------------------------
# 9. Whitespace stripping
# ---------------------------------------------------------------------------

class TestWhitespaceStripping:
    def test_leading_whitespace_stripped(self):
        assert clean_text("   hello") == "hello"

    def test_trailing_whitespace_stripped(self):
        assert clean_text("hello   ") == "hello"

    def test_both_ends_whitespace_stripped(self):
        assert clean_text("  hello  ") == "hello"

    def test_whitespace_only_becomes_empty(self):
        assert clean_text("   ") == ""

    def test_newlines_only_becomes_empty(self):
        assert clean_text("\n\n\n") == ""

    def test_stripping_with_both_false(self):
        assert clean_text("  text  ", remove_markdown=False, remove_citations=False) == "text"

    def test_stripping_applied_after_heading_removal(self):
        # Leading whitespace before the hash, trailing whitespace after the title
        result = clean_text("  # Heading  ")
        assert result == "Heading"


# ---------------------------------------------------------------------------
# 10. Combination: bold + citation both cleaned
# ---------------------------------------------------------------------------

class TestCombinationBoldAndCitation:
    def test_bold_and_citation_cleaned(self):
        text = "**Important finding** [1]."
        result = clean_text(text)
        assert "**" not in result
        assert "[1]" not in result
        assert "Important finding" in result

    def test_italic_and_consecutive_citations_cleaned(self):
        text = "*See note* [2][3]."
        result = clean_text(text)
        assert "*See note*" not in result
        assert "[2]" not in result
        assert "[3]" not in result
        assert "See note" in result

    def test_heading_bold_italic_citation_all_cleaned(self):
        text = "## **Assessment** [1]\n*Stable* condition."
        result = clean_text(text)
        assert "#" not in result
        assert "**" not in result
        assert "[1]" not in result
        assert "Assessment" in result
        assert "Stable" in result
        assert "condition." in result

    def test_inline_code_and_citation_cleaned(self):
        text = "Run `grep` for details [4]."
        result = clean_text(text)
        assert "`" not in result
        assert "[4]" not in result
        assert "grep" in result
        assert "for details" in result

    def test_defaults_remove_both_markdown_and_citations(self):
        # Verify the documented defaults (remove_markdown=True, remove_citations=True) are active
        result = clean_text("# Title\nSome text[1]")
        assert "#" not in result
        assert "[1]" not in result
        assert "Some text" in result
