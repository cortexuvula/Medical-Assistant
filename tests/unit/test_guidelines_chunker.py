"""
Tests for src/rag/guidelines_chunker.py

Covers module constants/patterns, GuidelineChunkResult and Section
dataclasses, GuidelinesChunker private methods (_estimate_tokens,
_detect_sections, _is_recommendation_text, _split_into_sentences,
_chunk_section_content), and chunk_text() (empty input, section detection
path, fallback path, overlap, heading prefix, recommendation detection).
Pure regex/string logic — no network, no Tkinter, no file I/O.
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

from rag.guidelines_chunker import (
    DEFAULT_MAX_CHUNK_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    HEADING_PATTERNS,
    RECOMMENDATION_PATTERNS,
    GuidelineChunkResult,
    Section,
    GuidelinesChunker,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _chunker(
    max_chunk_tokens: int = DEFAULT_MAX_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    preserve_headings: bool = True,
) -> GuidelinesChunker:
    return GuidelinesChunker(max_chunk_tokens, overlap_tokens, preserve_headings)


# ===========================================================================
# Constants and Patterns
# ===========================================================================

class TestConstants:
    def test_default_max_chunk_tokens(self):
        assert DEFAULT_MAX_CHUNK_TOKENS == 500

    def test_default_overlap_tokens(self):
        assert DEFAULT_OVERLAP_TOKENS == 100

    def test_heading_patterns_is_list(self):
        assert isinstance(HEADING_PATTERNS, list)

    def test_heading_patterns_non_empty(self):
        assert len(HEADING_PATTERNS) > 0

    def test_recommendation_patterns_is_list(self):
        assert isinstance(RECOMMENDATION_PATTERNS, list)

    def test_recommendation_patterns_non_empty(self):
        assert len(RECOMMENDATION_PATTERNS) > 0


class TestHeadingPatterns:
    def test_markdown_h1_detected(self):
        assert any(p.search("# Introduction") for p in HEADING_PATTERNS)

    def test_markdown_h2_detected(self):
        assert any(p.search("## Methods") for p in HEADING_PATTERNS)

    def test_markdown_h3_detected(self):
        assert any(p.search("### Results") for p in HEADING_PATTERNS)

    def test_section_numbered_detected(self):
        assert any(p.search("Section 1.2 Background") for p in HEADING_PATTERNS)

    def test_all_caps_line_detected(self):
        assert any(p.search("RECOMMENDATIONS") for p in HEADING_PATTERNS)

    def test_numbered_section_header_detected(self):
        assert any(p.search("1. Background Information and Context") for p in HEADING_PATTERNS)

    def test_plain_text_not_detected_as_heading(self):
        # "hello world" should not match heading patterns
        assert not any(p.match("hello world") for p in HEADING_PATTERNS)


class TestRecommendationPatterns:
    def test_class_i_detected(self):
        assert any(p.search("Class I recommendation") for p in RECOMMENDATION_PATTERNS)

    def test_class_iia_detected(self):
        assert any(p.search("Class IIa evidence") for p in RECOMMENDATION_PATTERNS)

    def test_class_iib_detected(self):
        assert any(p.search("Class IIb weak") for p in RECOMMENDATION_PATTERNS)

    def test_level_a_detected(self):
        assert any(p.search("Level A evidence") for p in RECOMMENDATION_PATTERNS)

    def test_level_b_r_detected(self):
        assert any(p.search("Level B-R from randomized trial") for p in RECOMMENDATION_PATTERNS)

    def test_level_c_ld_detected(self):
        assert any(p.search("Level C-LD limited data") for p in RECOMMENDATION_PATTERNS)

    def test_recommendation_colon_detected(self):
        assert any(p.search("Recommendation 1:") for p in RECOMMENDATION_PATTERNS)

    def test_cor_detected(self):
        assert any(p.search("COR I") for p in RECOMMENDATION_PATTERNS)

    def test_loe_detected(self):
        assert any(p.search("LOE A") for p in RECOMMENDATION_PATTERNS)


# ===========================================================================
# GuidelineChunkResult dataclass
# ===========================================================================

class TestGuidelineChunkResult:
    def test_required_fields(self):
        r = GuidelineChunkResult(chunk_index=0, chunk_text="text", token_count=5)
        assert r.chunk_index == 0
        assert r.chunk_text == "text"
        assert r.token_count == 5

    def test_section_heading_defaults_none(self):
        r = GuidelineChunkResult(0, "text", 5)
        assert r.section_heading is None

    def test_is_recommendation_defaults_false(self):
        r = GuidelineChunkResult(0, "text", 5)
        assert r.is_recommendation is False

    def test_custom_values(self):
        r = GuidelineChunkResult(2, "rec text", 10, "METHODS", True)
        assert r.chunk_index == 2
        assert r.section_heading == "METHODS"
        assert r.is_recommendation is True


# ===========================================================================
# Section dataclass
# ===========================================================================

class TestSection:
    def test_required_fields(self):
        s = Section(heading="Methods", content="content", start_pos=0, end_pos=100)
        assert s.heading == "Methods"
        assert s.content == "content"
        assert s.start_pos == 0
        assert s.end_pos == 100

    def test_level_defaults_to_1(self):
        s = Section("h", "c", 0, 10)
        assert s.level == 1

    def test_custom_level(self):
        s = Section("h", "c", 0, 10, level=3)
        assert s.level == 3


# ===========================================================================
# _estimate_tokens
# ===========================================================================

class TestEstimateTokens:
    def setup_method(self):
        self.c = _chunker()

    def test_empty_string_is_zero(self):
        assert self.c._estimate_tokens("") == 0

    def test_four_chars_is_one_token(self):
        assert self.c._estimate_tokens("abcd") == 1

    def test_eight_chars_is_two_tokens(self):
        assert self.c._estimate_tokens("abcdefgh") == 2

    def test_returns_int(self):
        assert isinstance(self.c._estimate_tokens("hello"), int)

    def test_proportional_to_length(self):
        t1 = self.c._estimate_tokens("a" * 4)
        t2 = self.c._estimate_tokens("a" * 8)
        assert t2 == t1 * 2


# ===========================================================================
# _detect_sections
# ===========================================================================

class TestDetectSections:
    def setup_method(self):
        self.c = _chunker()

    def test_no_sections_returns_empty(self):
        result = self.c._detect_sections("This is plain text with no headings.")
        assert result == []

    def test_markdown_heading_detected(self):
        text = "# Introduction\nThis is the introduction."
        sections = self.c._detect_sections(text)
        assert len(sections) >= 1
        assert any(s.heading.strip("#").strip() == "Introduction" for s in sections)

    def test_multiple_headings_ordered(self):
        text = "# First\nContent A.\n\n# Second\nContent B."
        sections = self.c._detect_sections(text)
        assert len(sections) >= 2
        assert sections[0].start_pos < sections[1].start_pos

    def test_section_content_extracted(self):
        text = "# Methods\nPatients were enrolled from 2020."
        sections = self.c._detect_sections(text)
        assert len(sections) >= 1
        assert "Patients" in sections[0].content

    def test_all_caps_heading_detected(self):
        text = "METHODS\nStudy design was prospective."
        sections = self.c._detect_sections(text)
        assert len(sections) >= 1

    def test_returns_list_of_sections(self):
        result = self.c._detect_sections("# Heading\nContent.")
        for s in result:
            assert isinstance(s, Section)

    def test_section_heading_level_set_for_markdown(self):
        text = "## Section Two\nSome content here."
        sections = self.c._detect_sections(text)
        assert len(sections) >= 1
        # Level should be 2 for ## heading
        md_sections = [s for s in sections if "Section Two" in s.heading]
        if md_sections:
            assert md_sections[0].level == 2


# ===========================================================================
# _is_recommendation_text
# ===========================================================================

class TestIsRecommendationText:
    def setup_method(self):
        self.c = _chunker()

    def test_class_i_is_recommendation(self):
        assert self.c._is_recommendation_text("Class I is recommended for all patients")

    def test_class_iia_is_recommendation(self):
        assert self.c._is_recommendation_text("Class IIa evidence supports this")

    def test_level_a_is_recommendation(self):
        assert self.c._is_recommendation_text("Level A evidence from multiple RCTs")

    def test_level_b_r_is_recommendation(self):
        assert self.c._is_recommendation_text("Level B-R randomized trial data")

    def test_recommendation_colon_is_recommendation(self):
        assert self.c._is_recommendation_text("Recommendation 1: Patients should receive")

    def test_plain_text_not_recommendation(self):
        assert not self.c._is_recommendation_text("The patient presented with chest pain.")

    def test_empty_string_not_recommendation(self):
        assert not self.c._is_recommendation_text("")

    def test_case_insensitive(self):
        assert self.c._is_recommendation_text("class iia is recommended")


# ===========================================================================
# _split_into_sentences
# ===========================================================================

class TestSplitIntoSentences:
    def setup_method(self):
        self.c = _chunker()

    def test_single_sentence(self):
        result = self.c._split_into_sentences("Hello world.")
        assert len(result) == 1

    def test_two_sentences(self):
        result = self.c._split_into_sentences("First sentence. Second sentence.")
        assert len(result) == 2

    def test_exclamation_splits(self):
        result = self.c._split_into_sentences("Stop! Continue.")
        assert len(result) == 2

    def test_question_mark_splits(self):
        result = self.c._split_into_sentences("What? Answer here.")
        assert len(result) == 2

    def test_empty_string_returns_empty_list(self):
        assert self.c._split_into_sentences("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert self.c._split_into_sentences("   ") == []

    def test_returns_list(self):
        assert isinstance(self.c._split_into_sentences("Text."), list)

    def test_strips_whitespace_from_sentences(self):
        result = self.c._split_into_sentences("  Hello.  World.  ")
        for s in result:
            assert s == s.strip()


# ===========================================================================
# chunk_text() — main method
# ===========================================================================

class TestChunkText:
    def setup_method(self):
        self.c = _chunker()

    def test_empty_string_returns_empty(self):
        assert self.c.chunk_text("") == []

    def test_whitespace_only_returns_empty(self):
        assert self.c.chunk_text("   ") == []

    def test_returns_list(self):
        result = self.c.chunk_text("Simple text with some content.")
        assert isinstance(result, list)

    def test_each_result_is_guideline_chunk_result(self):
        results = self.c.chunk_text("Some plain text content here.")
        for r in results:
            assert isinstance(r, GuidelineChunkResult)

    def test_short_text_produces_single_chunk(self):
        result = self.c.chunk_text("Short text.")
        assert len(result) == 1

    def test_chunk_indices_are_sequential(self):
        # Use longer text to potentially produce multiple chunks
        text = "A" * 100 + ". " + "B" * 100 + ". " + "C" * 100 + "."
        results = self.c.chunk_text(text)
        for i, r in enumerate(results):
            assert r.chunk_index == i

    def test_token_count_populated(self):
        results = self.c.chunk_text("Some reasonable text content here.")
        for r in results:
            assert r.token_count > 0

    def test_chunk_text_not_empty(self):
        results = self.c.chunk_text("Some text content.")
        for r in results:
            assert r.chunk_text.strip() != ""

    def test_section_heading_detected_path(self):
        text = "# Introduction\nThis section introduces the topic."
        results = self.c.chunk_text(text)
        assert len(results) >= 1
        heading_chunks = [r for r in results if r.section_heading is not None]
        assert len(heading_chunks) >= 1

    def test_heading_prefix_in_chunk_text_when_preserve_headings(self):
        text = "# Methods\nPatients were enrolled prospectively."
        c = _chunker(preserve_headings=True)
        results = c.chunk_text(text)
        heading_chunks = [r for r in results if r.section_heading is not None]
        if heading_chunks:
            assert "[" in heading_chunks[0].chunk_text

    def test_no_heading_prefix_when_preserve_headings_false(self):
        text = "# Methods\nPatients were enrolled prospectively."
        c = _chunker(preserve_headings=False)
        results = c.chunk_text(text)
        for r in results:
            assert "[Methods]" not in r.chunk_text

    def test_recommendation_flagged_correctly(self):
        text = "Class I recommendation is that ACE inhibitors are preferred."
        results = self.c.chunk_text(text)
        assert any(r.is_recommendation for r in results)

    def test_plain_text_not_flagged_as_recommendation(self):
        text = "The patient was seen in clinic for a routine follow-up visit."
        results = self.c.chunk_text(text)
        assert all(not r.is_recommendation for r in results)

    def test_large_chunk_splits_into_multiple(self):
        # Create text larger than max_chunk_tokens (500 tokens ≈ 2000 chars)
        text = " ".join(["word"] * 600)  # ~600 * 5 = 3000 chars → ~750 tokens
        c = _chunker(max_chunk_tokens=100)  # Small limit → forces multiple chunks
        results = c.chunk_text(text)
        assert len(results) > 1

    def test_multi_section_document(self):
        text = (
            "# Background\n"
            "This is the background section with some content.\n\n"
            "# Methods\n"
            "Patients were enrolled from January 2020.\n\n"
            "# Results\n"
            "Outcomes were favorable in the treatment group."
        )
        results = self.c.chunk_text(text)
        assert len(results) >= 1
        section_headings = {r.section_heading for r in results if r.section_heading}
        assert len(section_headings) >= 2

    def test_fallback_when_no_sections(self):
        text = "Plain text without any headings or section markers. Just sentences."
        results = self.c.chunk_text(text)
        # Should still produce chunks via fallback path
        assert len(results) >= 1
        for r in results:
            assert r.section_heading is None
