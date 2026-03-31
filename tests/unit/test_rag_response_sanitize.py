"""
Tests for RagResponseMixin._sanitize_response() in src/ai/rag_response.py

Covers truncation at MAX_RESPONSE_LENGTH, dangerous pattern removal
(script tags, event handlers, iframes, control chars, ANSI sequences,
null bytes), line-length truncation at MAX_LINE_LENGTH.
Pure string transformation — no network, no Tkinter, no file I/O.
"""

import sys
import re
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.rag_response import RagResponseMixin


# ---------------------------------------------------------------------------
# Minimal stub that provides the constants RagResponseMixin needs
# ---------------------------------------------------------------------------

class _FakeRAGProcessor(RagResponseMixin):
    MAX_RESPONSE_LENGTH = 100000  # 100KB
    MAX_LINE_LENGTH = 5000
    DANGEROUS_PATTERNS = [
        (re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL), ''),
        (re.compile(r'<[^>]+on\w+\s*=', re.IGNORECASE), '<'),
        (re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL), ''),
        (re.compile(r'<object[^>]*>.*?</object>', re.IGNORECASE | re.DOTALL), ''),
        (re.compile(r'<embed[^>]*>', re.IGNORECASE), ''),
        (re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]'), ''),
        (re.compile(r'\x1b\[[0-9;]*[a-zA-Z]'), ''),
        (re.compile(r'\x00'), ''),
    ]


def _proc() -> _FakeRAGProcessor:
    return _FakeRAGProcessor()


# ===========================================================================
# Basic behavior
# ===========================================================================

class TestSanitizeResponseBasic:
    def setup_method(self):
        self.p = _proc()

    def test_returns_string(self):
        assert isinstance(self.p._sanitize_response("hello"), str)

    def test_empty_string_returns_empty(self):
        assert self.p._sanitize_response("") == ""

    def test_none_returns_empty(self):
        assert self.p._sanitize_response(None) == ""

    def test_normal_text_unchanged(self):
        text = "Patient has hypertension and diabetes."
        assert self.p._sanitize_response(text) == text

    def test_multiline_text_preserved(self):
        text = "Line 1\nLine 2\nLine 3"
        result = self.p._sanitize_response(text)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


# ===========================================================================
# Response length truncation
# ===========================================================================

class TestSanitizeResponseLengthTruncation:
    def setup_method(self):
        self.p = _proc()
        self.limit = _FakeRAGProcessor.MAX_RESPONSE_LENGTH

    def test_response_at_limit_not_truncated(self):
        text = "x" * self.limit
        result = self.p._sanitize_response(text)
        assert "[Response truncated" not in result

    def test_response_one_over_limit_truncated(self):
        text = "x" * (self.limit + 1)
        result = self.p._sanitize_response(text)
        assert "[Response truncated" in result

    def test_truncated_response_starts_with_original(self):
        text = "a" * (self.limit + 500)
        result = self.p._sanitize_response(text)
        assert result.startswith("a" * 50)

    def test_short_response_not_truncated(self):
        text = "short text"
        result = self.p._sanitize_response(text)
        assert "[Response truncated" not in result


# ===========================================================================
# Dangerous pattern removal — script tags
# ===========================================================================

class TestSanitizeResponseScriptTags:
    def setup_method(self):
        self.p = _proc()

    def test_removes_script_tag(self):
        text = "normal <script>alert('xss')</script> text"
        result = self.p._sanitize_response(text)
        assert "<script>" not in result
        assert "alert('xss')" not in result

    def test_removes_script_with_src(self):
        text = "text <script src='evil.js'></script> after"
        result = self.p._sanitize_response(text)
        assert "<script" not in result

    def test_removes_case_insensitive_script(self):
        text = "text <SCRIPT>evil()</SCRIPT> after"
        result = self.p._sanitize_response(text)
        assert "<SCRIPT>" not in result
        assert "evil()" not in result

    def test_surrounding_text_preserved(self):
        text = "before <script>bad()</script> after"
        result = self.p._sanitize_response(text)
        assert "before" in result
        assert "after" in result


# ===========================================================================
# Dangerous pattern removal — event handlers
# ===========================================================================

class TestSanitizeResponseEventHandlers:
    def setup_method(self):
        self.p = _proc()

    def test_removes_onclick_handler(self):
        text = '<button onclick="evil()">Click</button>'
        result = self.p._sanitize_response(text)
        assert "onclick" not in result

    def test_removes_onmouseover_handler(self):
        text = '<div onmouseover="bad()">hover</div>'
        result = self.p._sanitize_response(text)
        assert "onmouseover" not in result


# ===========================================================================
# Dangerous pattern removal — iframe/object/embed
# ===========================================================================

class TestSanitizeResponseIframes:
    def setup_method(self):
        self.p = _proc()

    def test_removes_iframe_tag(self):
        text = 'text <iframe src="evil.com"></iframe> after'
        result = self.p._sanitize_response(text)
        assert "<iframe" not in result

    def test_removes_object_tag(self):
        text = '<object data="malware.swf"></object>'
        result = self.p._sanitize_response(text)
        assert "<object" not in result

    def test_removes_embed_tag(self):
        text = '<embed src="malware.swf">'
        result = self.p._sanitize_response(text)
        assert "<embed" not in result


# ===========================================================================
# Dangerous pattern removal — control characters
# ===========================================================================

class TestSanitizeResponseControlChars:
    def setup_method(self):
        self.p = _proc()

    def test_removes_null_bytes(self):
        text = "text\x00with\x00nulls"
        result = self.p._sanitize_response(text)
        assert "\x00" not in result

    def test_removes_control_char_0x01(self):
        text = "text\x01control"
        result = self.p._sanitize_response(text)
        assert "\x01" not in result

    def test_preserves_newline(self):
        text = "line1\nline2"
        result = self.p._sanitize_response(text)
        assert "\n" in result

    def test_preserves_tab(self):
        text = "col1\tcol2"
        result = self.p._sanitize_response(text)
        assert "\t" in result

    def test_removes_ansi_escape_sequences(self):
        text = "text \x1b[31mred\x1b[0m normal"
        result = self.p._sanitize_response(text)
        assert "\x1b[" not in result

    def test_ansi_color_codes_stripped_text_preserved(self):
        text = "before \x1b[32mGreen text\x1b[0m after"
        result = self.p._sanitize_response(text)
        # The actual text should remain, ANSI codes removed
        assert "before" in result
        assert "after" in result


# ===========================================================================
# Line length truncation
# ===========================================================================

class TestSanitizeResponseLineLength:
    def setup_method(self):
        self.p = _proc()
        self.limit = _FakeRAGProcessor.MAX_LINE_LENGTH

    def test_short_lines_unchanged(self):
        text = "short line\nanother short line"
        result = self.p._sanitize_response(text)
        lines = result.split('\n')
        assert lines[0] == "short line"

    def test_long_line_truncated(self):
        long_line = "x" * (self.limit + 100)
        result = self.p._sanitize_response(long_line)
        assert "[line truncated]" in result

    def test_long_line_starts_with_original(self):
        long_line = "y" * (self.limit + 500)
        result = self.p._sanitize_response(long_line)
        # The first MAX_LINE_LENGTH chars of the original should be present
        assert result.startswith("y" * 20)

    def test_only_long_lines_truncated(self):
        short_line = "short"
        long_line = "x" * (self.limit + 100)
        text = f"{short_line}\n{long_line}\n{short_line}"
        result = self.p._sanitize_response(text)
        lines = result.split('\n')
        assert lines[0] == "short"
        assert "[line truncated]" in lines[1]
        assert lines[2] == "short"

    def test_line_at_limit_not_truncated(self):
        line_at_limit = "z" * self.limit
        result = self.p._sanitize_response(line_at_limit)
        assert "[line truncated]" not in result
