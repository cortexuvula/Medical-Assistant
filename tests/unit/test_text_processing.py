"""
Tests for src/ai/text_processing.py

Covers clean_text() — the pure regex cleaning function.
(adjust_text_with_openai and improve_text_with_openai make live AI calls
and are not unit-tested here.)
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.text_processing import clean_text


# ===========================================================================
# clean_text — markdown removal
# ===========================================================================

class TestCleanTextMarkdown:
    def test_removes_code_block(self):
        text = "Before\n```python\ncode here\n```\nAfter"
        result = clean_text(text, remove_markdown=True, remove_citations=False)
        assert "```" not in result
        assert "code here" not in result

    def test_removes_inline_code_backtick(self):
        result = clean_text("Use `print()` here", remove_markdown=True, remove_citations=False)
        assert "`" not in result
        assert "print()" in result

    def test_removes_markdown_h1(self):
        result = clean_text("# Title\nContent", remove_markdown=True, remove_citations=False)
        assert "#" not in result
        assert "Title" in result

    def test_removes_markdown_h2(self):
        result = clean_text("## Subtitle\nContent", remove_markdown=True, remove_citations=False)
        assert "##" not in result
        assert "Subtitle" in result

    def test_removes_bold_double_asterisk(self):
        result = clean_text("This is **bold** text", remove_markdown=True, remove_citations=False)
        assert "**" not in result
        assert "bold" in result

    def test_removes_bold_double_underscore(self):
        result = clean_text("This is __bold__ text", remove_markdown=True, remove_citations=False)
        assert "__" not in result
        assert "bold" in result

    def test_removes_italic_single_asterisk(self):
        result = clean_text("This is *italic* text", remove_markdown=True, remove_citations=False)
        assert "*italic*" not in result
        assert "italic" in result

    def test_removes_italic_single_underscore(self):
        result = clean_text("This is _italic_ text", remove_markdown=True, remove_citations=False)
        assert "_italic_" not in result
        assert "italic" in result

    def test_preserve_markdown_when_disabled(self):
        text = "## Title\n**bold**"
        result = clean_text(text, remove_markdown=False, remove_citations=False)
        assert "##" in result
        assert "**" in result

    def test_returns_string(self):
        assert isinstance(clean_text("hello"), str)

    def test_empty_string_returns_empty(self):
        assert clean_text("") == ""

    def test_strips_leading_trailing_whitespace(self):
        result = clean_text("  hello  ")
        assert result == result.strip()


# ===========================================================================
# clean_text — citation removal
# ===========================================================================

class TestCleanTextCitations:
    def test_removes_single_citation(self):
        result = clean_text("See study[1] for details.", remove_markdown=False, remove_citations=True)
        assert "[1]" not in result
        assert "See study" in result

    def test_removes_multiple_citations(self):
        result = clean_text("Source[1][2][3]", remove_markdown=False, remove_citations=True)
        assert "[1]" not in result
        assert "[2]" not in result
        assert "[3]" not in result

    def test_removes_consecutive_citations(self):
        result = clean_text("Data[10][11]", remove_markdown=False, remove_citations=True)
        assert "[10]" not in result
        assert "[11]" not in result

    def test_preserves_text_around_citation(self):
        result = clean_text("text before[1] text after", remove_markdown=False, remove_citations=True)
        assert "text before" in result
        assert "text after" in result

    def test_preserve_citations_when_disabled(self):
        text = "Reference[1] here"
        result = clean_text(text, remove_markdown=False, remove_citations=False)
        assert "[1]" in result

    def test_no_citation_text_unchanged(self):
        text = "Plain text without any citations."
        result = clean_text(text, remove_markdown=False, remove_citations=True)
        assert "Plain text without any citations." in result


# ===========================================================================
# clean_text — both options
# ===========================================================================

class TestCleanTextBoth:
    def test_both_enabled_removes_markdown_and_citations(self):
        text = "## Heading\n**bold**[1] text"
        result = clean_text(text, remove_markdown=True, remove_citations=True)
        assert "##" not in result
        assert "**" not in result
        assert "[1]" not in result
        assert "bold" in result
        assert "text" in result

    def test_both_disabled_returns_original_stripped(self):
        text = "## Title\n**bold**[1]"
        result = clean_text(text, remove_markdown=False, remove_citations=False)
        assert "##" in result
        assert "**" in result
        assert "[1]" in result

    def test_default_removes_both(self):
        # Default: remove_markdown=True, remove_citations=True
        result = clean_text("# Title\nSome text[1]")
        assert "#" not in result
        assert "[1]" not in result
        assert "Some text" in result

    def test_multiline_code_block_fully_removed(self):
        text = "Before\n```\nline1\nline2\n```\nAfter"
        result = clean_text(text, remove_markdown=True, remove_citations=False)
        assert "line1" not in result
        assert "line2" not in result
        assert "Before" in result
        assert "After" in result
