"""
Pure unit tests for StreamingHybridRetriever._build_context.

No network, no embedding, no external services required.
"""

import sys
sys.path.insert(0, 'src')

import pytest
from unittest.mock import MagicMock

from rag.streaming_retriever import StreamingHybridRetriever
from rag.models import HybridSearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(chunk_text="some text", filename="doc.pdf",
                related_entities=None, **kwargs):
    """Create a HybridSearchResult with sensible defaults."""
    return HybridSearchResult(
        chunk_text=chunk_text,
        document_id="doc1",
        document_filename=filename,
        chunk_index=0,
        related_entities=related_entities if related_entities is not None else [],
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def retriever():
    from rag.search_config import SearchQualityConfig
    return StreamingHybridRetriever(config=SearchQualityConfig())


# ---------------------------------------------------------------------------
# 1. Empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_list_returns_empty_string(self, retriever):
        assert retriever._build_context([]) == ""

    def test_return_type_is_str(self, retriever):
        result = retriever._build_context([])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 2. Single result – header
# ---------------------------------------------------------------------------

class TestSingleResultHeader:
    def test_output_starts_with_source_header(self, retriever):
        r = make_result(filename="report.pdf")
        output = retriever._build_context([r])
        assert output.startswith("[Source 1: report.pdf]")

    def test_header_uses_document_filename(self, retriever):
        r = make_result(filename="my_file.txt")
        output = retriever._build_context([r])
        assert "[Source 1: my_file.txt]" in output

    def test_header_bracket_format(self, retriever):
        r = make_result(filename="notes.docx")
        output = retriever._build_context([r])
        assert "[Source 1: notes.docx]" in output

    def test_filename_with_spaces_in_header(self, retriever):
        r = make_result(filename="patient notes 2024.pdf")
        output = retriever._build_context([r])
        assert "[Source 1: patient notes 2024.pdf]" in output


# ---------------------------------------------------------------------------
# 3. Single result – chunk text
# ---------------------------------------------------------------------------

class TestSingleResultChunkText:
    def test_output_contains_chunk_text(self, retriever):
        r = make_result(chunk_text="The patient presents with fever.")
        output = retriever._build_context([r])
        assert "The patient presents with fever." in output

    def test_chunk_text_with_newlines_preserved(self, retriever):
        r = make_result(chunk_text="line one\nline two\nline three")
        output = retriever._build_context([r])
        assert "line one\nline two\nline three" in output

    def test_empty_chunk_text_included(self, retriever):
        r = make_result(chunk_text="")
        output = retriever._build_context([r])
        # header must still appear
        assert "[Source 1:" in output

    def test_chunk_text_appears_after_header(self, retriever):
        r = make_result(chunk_text="body text", filename="f.pdf")
        output = retriever._build_context([r])
        header_pos = output.index("[Source 1: f.pdf]")
        body_pos = output.index("body text")
        assert body_pos > header_pos


# ---------------------------------------------------------------------------
# 4. Single result – related entities absent
# ---------------------------------------------------------------------------

class TestNoRelatedEntities:
    def test_no_related_concepts_line_when_empty_list(self, retriever):
        r = make_result(related_entities=[])
        output = retriever._build_context([r])
        assert "Related concepts" not in output

    def test_no_related_concepts_line_when_none_given(self, retriever):
        # make_result defaults to []
        r = make_result()
        output = retriever._build_context([r])
        assert "Related concepts" not in output


# ---------------------------------------------------------------------------
# 5. Single result – related entities present
# ---------------------------------------------------------------------------

class TestRelatedEntitiesPresent:
    def test_related_concepts_line_present(self, retriever):
        r = make_result(related_entities=["A", "B"])
        output = retriever._build_context([r])
        assert "Related concepts:" in output

    def test_two_entities_joined_by_comma_space(self, retriever):
        r = make_result(related_entities=["Alpha", "Beta"])
        output = retriever._build_context([r])
        assert "Related concepts: Alpha, Beta" in output

    def test_single_entity_no_trailing_comma(self, retriever):
        r = make_result(related_entities=["only_one"])
        output = retriever._build_context([r])
        assert "Related concepts: only_one" in output

    def test_exactly_five_entities_all_included(self, retriever):
        entities = ["a", "b", "c", "d", "e"]
        r = make_result(related_entities=entities)
        output = retriever._build_context([r])
        assert "Related concepts: a, b, c, d, e" in output

    def test_six_entities_only_first_five_included(self, retriever):
        entities = ["a", "b", "c", "d", "e", "f"]
        r = make_result(related_entities=entities)
        output = retriever._build_context([r])
        assert "Related concepts: a, b, c, d, e" in output
        assert "f" not in output.split("Related concepts:")[1].split("\n")[0]

    def test_seven_entities_only_first_five(self, retriever):
        entities = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"]
        r = make_result(related_entities=entities)
        output = retriever._build_context([r])
        concepts_line = [ln for ln in output.splitlines() if "Related concepts:" in ln][0]
        items = [x.strip() for x in concepts_line.replace("Related concepts:", "").split(",")]
        assert len(items) == 5

    def test_entities_line_after_chunk_text(self, retriever):
        r = make_result(chunk_text="chunk body", related_entities=["X"])
        output = retriever._build_context([r])
        body_pos = output.index("chunk body")
        concepts_pos = output.index("Related concepts:")
        assert concepts_pos > body_pos


# ---------------------------------------------------------------------------
# 6. Blank-line separator mechanics
# ---------------------------------------------------------------------------

class TestBlankLineSeparator:
    def test_single_result_ends_with_blank_line(self, retriever):
        """context_parts.append('') means last element is '' → output ends with \n"""
        r = make_result()
        output = retriever._build_context([r])
        assert output.endswith("\n")

    def test_blank_line_between_two_results(self, retriever):
        r1 = make_result(filename="a.pdf", chunk_text="first")
        r2 = make_result(filename="b.pdf", chunk_text="second")
        output = retriever._build_context([r1, r2])
        # There must be at least one empty line between the two sources
        assert "\n\n" in output

    def test_join_uses_newlines(self, retriever):
        """"\n".join means elements separated by single newline."""
        r = make_result(chunk_text="text", filename="f.pdf")
        output = retriever._build_context([r])
        lines = output.split("\n")
        assert "[Source 1: f.pdf]" in lines
        assert "text" in lines


# ---------------------------------------------------------------------------
# 7. Exact output structure – no entities
# ---------------------------------------------------------------------------

class TestExactStructureNoEntities:
    def test_exact_output_no_entities(self, retriever):
        r = make_result(chunk_text="chunk text", filename="file.pdf")
        output = retriever._build_context([r])
        expected = "[Source 1: file.pdf]\nchunk text\n"
        assert output == expected

    def test_exact_lines_no_entities(self, retriever):
        r = make_result(chunk_text="hello", filename="x.pdf")
        output = retriever._build_context([r])
        lines = output.split("\n")
        # Parts list: [header, chunk, ""] → joined → "header\nchunk\n"  (trailing "")
        assert lines[0] == "[Source 1: x.pdf]"
        assert lines[1] == "hello"
        assert lines[2] == ""


# ---------------------------------------------------------------------------
# 8. Exact output structure – with entities
# ---------------------------------------------------------------------------

class TestExactStructureWithEntities:
    def test_exact_output_with_two_entities(self, retriever):
        r = make_result(chunk_text="chunk text", filename="file.pdf",
                        related_entities=["a", "b"])
        output = retriever._build_context([r])
        expected = "[Source 1: file.pdf]\nchunk text\nRelated concepts: a, b\n"
        assert output == expected

    def test_exact_lines_with_entities(self, retriever):
        r = make_result(chunk_text="body", filename="doc.pdf",
                        related_entities=["X", "Y"])
        output = retriever._build_context([r])
        lines = output.split("\n")
        assert lines[0] == "[Source 1: doc.pdf]"
        assert lines[1] == "body"
        assert lines[2] == "Related concepts: X, Y"
        assert lines[3] == ""


# ---------------------------------------------------------------------------
# 9. Multiple results – numbering
# ---------------------------------------------------------------------------

class TestMultipleResultsNumbering:
    def test_two_results_numbered_sequentially(self, retriever):
        r1 = make_result(filename="a.pdf")
        r2 = make_result(filename="b.pdf")
        output = retriever._build_context([r1, r2])
        assert "[Source 1: a.pdf]" in output
        assert "[Source 2: b.pdf]" in output

    def test_three_results_numbered_sequentially(self, retriever):
        results = [make_result(filename=f"f{i}.pdf") for i in range(1, 4)]
        output = retriever._build_context(results)
        for i in range(1, 4):
            assert f"[Source {i}: f{i}.pdf]" in output

    def test_ten_results_all_numbered(self, retriever):
        results = [make_result(filename=f"doc{i}.pdf", chunk_text=f"text{i}")
                   for i in range(1, 11)]
        output = retriever._build_context(results)
        for i in range(1, 11):
            assert f"[Source {i}: doc{i}.pdf]" in output

    def test_results_appear_in_order(self, retriever):
        r1 = make_result(filename="first.pdf", chunk_text="alpha")
        r2 = make_result(filename="second.pdf", chunk_text="beta")
        output = retriever._build_context([r1, r2])
        pos_1 = output.index("[Source 1: first.pdf]")
        pos_2 = output.index("[Source 2: second.pdf]")
        assert pos_1 < pos_2

    def test_no_source_0_header(self, retriever):
        r = make_result()
        output = retriever._build_context([r])
        assert "[Source 0:" not in output


# ---------------------------------------------------------------------------
# 10. Mixed entity / no-entity results
# ---------------------------------------------------------------------------

class TestMixedEntityResults:
    def test_first_has_entities_second_does_not(self, retriever):
        r1 = make_result(filename="with.pdf", chunk_text="ct1",
                         related_entities=["E1", "E2"])
        r2 = make_result(filename="without.pdf", chunk_text="ct2",
                         related_entities=[])
        output = retriever._build_context([r1, r2])
        assert "[Source 1: with.pdf]" in output
        assert "Related concepts: E1, E2" in output
        assert "[Source 2: without.pdf]" in output
        # Only one "Related concepts" line
        assert output.count("Related concepts:") == 1

    def test_second_has_entities_first_does_not(self, retriever):
        r1 = make_result(filename="no_ent.pdf", chunk_text="first",
                         related_entities=[])
        r2 = make_result(filename="yes_ent.pdf", chunk_text="second",
                         related_entities=["Z"])
        output = retriever._build_context([r1, r2])
        assert "Related concepts: Z" in output
        idx_source2 = output.index("[Source 2: yes_ent.pdf]")
        idx_concepts = output.index("Related concepts: Z")
        assert idx_concepts > idx_source2

    def test_all_results_have_entities(self, retriever):
        r1 = make_result(related_entities=["A"])
        r2 = make_result(related_entities=["B"])
        output = retriever._build_context([r1, r2])
        assert output.count("Related concepts:") == 2


# ---------------------------------------------------------------------------
# 11. Return type and idempotency
# ---------------------------------------------------------------------------

class TestReturnTypeAndIdempotency:
    def test_return_type_is_str_single(self, retriever):
        r = make_result()
        assert isinstance(retriever._build_context([r]), str)

    def test_return_type_is_str_multiple(self, retriever):
        results = [make_result() for _ in range(3)]
        assert isinstance(retriever._build_context(results), str)

    def test_same_input_produces_same_output(self, retriever):
        r = make_result(chunk_text="stable", filename="same.pdf",
                        related_entities=["X"])
        out1 = retriever._build_context([r])
        out2 = retriever._build_context([r])
        assert out1 == out2


# ---------------------------------------------------------------------------
# 12. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_whitespace_only_chunk_text(self, retriever):
        r = make_result(chunk_text="   ")
        output = retriever._build_context([r])
        assert "   " in output

    def test_chunk_text_with_special_characters(self, retriever):
        r = make_result(chunk_text="BP: 120/80 mmHg, HR: 72 bpm [normal]")
        output = retriever._build_context([r])
        assert "BP: 120/80 mmHg, HR: 72 bpm [normal]" in output

    def test_entity_with_spaces(self, retriever):
        r = make_result(related_entities=["type 2 diabetes", "heart failure"])
        output = retriever._build_context([r])
        assert "Related concepts: type 2 diabetes, heart failure" in output

    def test_filename_with_special_characters(self, retriever):
        r = make_result(filename="report_2024-01-01_v2.pdf")
        output = retriever._build_context([r])
        assert "[Source 1: report_2024-01-01_v2.pdf]" in output

    def test_single_result_no_entities_exact_newline_count(self, retriever):
        """Parts: [header, chunk, ''] → join → 'header\nchunk\n' → 2 newlines."""
        r = make_result(chunk_text="abc", filename="x.pdf")
        output = retriever._build_context([r])
        assert output.count("\n") == 2

    def test_single_result_with_one_entity_exact_newline_count(self, retriever):
        """Parts: [header, chunk, concepts, ''] → 3 newlines."""
        r = make_result(chunk_text="abc", filename="x.pdf",
                        related_entities=["Z"])
        output = retriever._build_context([r])
        assert output.count("\n") == 3

    def test_two_results_no_entities_correct_structure(self, retriever):
        """Two results without entities: each block is 'header\nchunk\n'."""
        r1 = make_result(chunk_text="first body", filename="r1.pdf")
        r2 = make_result(chunk_text="second body", filename="r2.pdf")
        output = retriever._build_context([r1, r2])
        expected = (
            "[Source 1: r1.pdf]\nfirst body\n"
            "\n"
            "[Source 2: r2.pdf]\nsecond body\n"
        )
        assert output == expected
