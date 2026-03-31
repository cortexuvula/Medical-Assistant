"""
Tests for src/rag/search_syntax_parser.py

Covers ParsedQuery (has_filters, to_dict), SearchSyntaxParser class constants,
and all private extraction methods (_extract_types, _extract_dates,
_extract_entities, _extract_min_score, _extract_excludes, _extract_phrases,
_clean_query), plus parse(), format_help(), the singleton, and the convenience
function.  No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import rag.search_syntax_parser as ssp_module
from rag.search_syntax_parser import (
    ParsedQuery,
    SearchSyntaxParser,
    get_search_syntax_parser,
    parse_search_query,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    ssp_module._parser = None
    yield
    ssp_module._parser = None


def _parser() -> SearchSyntaxParser:
    return SearchSyntaxParser()


# ===========================================================================
# ParsedQuery.has_filters
# ===========================================================================

class TestParsedQueryHasFilters:
    def _empty(self) -> ParsedQuery:
        return ParsedQuery(text="hello", original_query="hello")

    def test_no_filters_is_false(self):
        pq = self._empty()
        assert pq.has_filters is False

    def test_document_types_triggers_true(self):
        pq = self._empty()
        pq.document_types = ["pdf"]
        assert pq.has_filters is True

    def test_date_range_triggers_true(self):
        pq = self._empty()
        pq.date_range = (datetime(2024, 1, 1), datetime(2024, 12, 31))
        assert pq.has_filters is True

    def test_entity_filters_triggers_true(self):
        pq = self._empty()
        pq.entity_filters = {"medication": ["aspirin"]}
        assert pq.has_filters is True

    def test_exclude_terms_triggers_true(self):
        pq = self._empty()
        pq.exclude_terms = ["old"]
        assert pq.has_filters is True

    def test_exact_phrases_triggers_true(self):
        pq = self._empty()
        pq.exact_phrases = ["heart failure"]
        assert pq.has_filters is True

    def test_min_score_gt_zero_triggers_true(self):
        pq = self._empty()
        pq.min_score = 0.8
        assert pq.has_filters is True

    def test_min_score_zero_no_trigger(self):
        pq = self._empty()
        pq.min_score = 0.0
        assert pq.has_filters is False

    def test_empty_lists_no_trigger(self):
        pq = ParsedQuery(
            text="test",
            original_query="test",
            document_types=[],
            entity_filters={},
            exclude_terms=[],
            exact_phrases=[],
            min_score=0.0,
        )
        assert pq.has_filters is False


# ===========================================================================
# ParsedQuery.to_dict
# ===========================================================================

class TestParsedQueryToDict:
    def test_returns_dict(self):
        pq = ParsedQuery(text="hello", original_query="hello")
        assert isinstance(pq.to_dict(), dict)

    def test_text_key_present(self):
        pq = ParsedQuery(text="hello", original_query="hello")
        assert pq.to_dict()["text"] == "hello"

    def test_original_query_key_present(self):
        pq = ParsedQuery(text="hello", original_query="original hello")
        assert pq.to_dict()["original_query"] == "original hello"

    def test_document_types_key_present(self):
        pq = ParsedQuery(text="hello", original_query="hello", document_types=["pdf"])
        assert pq.to_dict()["document_types"] == ["pdf"]

    def test_entity_filters_key_present(self):
        pq = ParsedQuery(text="hello", original_query="hello", entity_filters={"medication": ["aspirin"]})
        assert pq.to_dict()["entity_filters"] == {"medication": ["aspirin"]}

    def test_min_score_key_present(self):
        pq = ParsedQuery(text="hello", original_query="hello", min_score=0.75)
        assert pq.to_dict()["min_score"] == 0.75

    def test_date_range_none_serialized_as_none(self):
        pq = ParsedQuery(text="hello", original_query="hello")
        assert pq.to_dict()["date_range"] is None

    def test_date_range_serialized_as_iso_list(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        pq = ParsedQuery(text="hello", original_query="hello", date_range=(start, end))
        result = pq.to_dict()["date_range"]
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == start.isoformat()
        assert result[1] == end.isoformat()

    def test_exclude_terms_key_present(self):
        pq = ParsedQuery(text="hello", original_query="hello", exclude_terms=["old"])
        assert pq.to_dict()["exclude_terms"] == ["old"]

    def test_exact_phrases_key_present(self):
        pq = ParsedQuery(text="hello", original_query="hello", exact_phrases=["heart failure"])
        assert pq.to_dict()["exact_phrases"] == ["heart failure"]


# ===========================================================================
# SearchSyntaxParser class constants
# ===========================================================================

class TestSearchSyntaxParserConstants:
    def test_supported_types_contains_pdf(self):
        assert "pdf" in SearchSyntaxParser.SUPPORTED_TYPES

    def test_supported_types_contains_docx(self):
        assert "docx" in SearchSyntaxParser.SUPPORTED_TYPES

    def test_supported_types_contains_txt(self):
        assert "txt" in SearchSyntaxParser.SUPPORTED_TYPES

    def test_supported_types_contains_image(self):
        assert "image" in SearchSyntaxParser.SUPPORTED_TYPES

    def test_date_aliases_keys(self):
        aliases = SearchSyntaxParser.DATE_ALIASES
        for key in ["today", "yesterday", "last-week", "last-month", "last-year"]:
            assert key in aliases

    def test_entity_type_aliases_med(self):
        assert SearchSyntaxParser.ENTITY_TYPE_ALIASES["med"] == "medication"

    def test_entity_type_aliases_drug(self):
        assert SearchSyntaxParser.ENTITY_TYPE_ALIASES["drug"] == "medication"

    def test_entity_type_aliases_disease(self):
        assert SearchSyntaxParser.ENTITY_TYPE_ALIASES["disease"] == "condition"

    def test_entity_type_aliases_diagnosis(self):
        assert SearchSyntaxParser.ENTITY_TYPE_ALIASES["diagnosis"] == "condition"

    def test_entity_type_aliases_sx(self):
        assert SearchSyntaxParser.ENTITY_TYPE_ALIASES["sx"] == "symptom"

    def test_entity_type_aliases_lab(self):
        assert SearchSyntaxParser.ENTITY_TYPE_ALIASES["lab"] == "lab_test"

    def test_entity_type_aliases_test(self):
        assert SearchSyntaxParser.ENTITY_TYPE_ALIASES["test"] == "lab_test"

    def test_entity_type_aliases_body(self):
        assert SearchSyntaxParser.ENTITY_TYPE_ALIASES["body"] == "anatomy"

    def test_patterns_dict_has_type(self):
        assert "type" in SearchSyntaxParser.PATTERNS

    def test_patterns_dict_has_date(self):
        assert "date" in SearchSyntaxParser.PATTERNS

    def test_patterns_dict_has_entity(self):
        assert "entity" in SearchSyntaxParser.PATTERNS

    def test_patterns_dict_has_score(self):
        assert "score" in SearchSyntaxParser.PATTERNS

    def test_patterns_dict_has_exclude(self):
        assert "exclude" in SearchSyntaxParser.PATTERNS

    def test_patterns_dict_has_exact(self):
        assert "exact" in SearchSyntaxParser.PATTERNS


# ===========================================================================
# _extract_types
# ===========================================================================

class TestExtractTypes:
    def setup_method(self):
        self.p = _parser()

    def test_no_type_returns_empty_list(self):
        _, types = self.p._extract_types("diabetes treatment")
        assert types == []

    def test_type_pdf(self):
        _, types = self.p._extract_types("diabetes type:pdf")
        assert types == ["pdf"]

    def test_type_docx(self):
        _, types = self.p._extract_types("query type:docx")
        assert types == ["docx"]

    def test_type_txt(self):
        _, types = self.p._extract_types("query type:txt")
        assert types == ["txt"]

    def test_type_pdf_case_insensitive(self):
        _, types = self.p._extract_types("query type:PDF")
        assert "pdf" in types

    def test_type_jpg_normalized_to_image(self):
        _, types = self.p._extract_types("query type:jpg")
        assert types == ["image"]

    def test_type_jpeg_normalized_to_image(self):
        _, types = self.p._extract_types("query type:jpeg")
        assert types == ["image"]

    def test_type_png_normalized_to_image(self):
        _, types = self.p._extract_types("query type:png")
        assert types == ["image"]

    def test_unknown_type_excluded(self):
        _, types = self.p._extract_types("query type:mp4")
        assert types == []

    def test_deduplication_two_pdf(self):
        _, types = self.p._extract_types("query type:pdf type:pdf")
        assert types.count("pdf") == 1

    def test_type_removed_from_query(self):
        remaining, _ = self.p._extract_types("diabetes type:pdf treatment")
        assert "type:pdf" not in remaining
        assert "diabetes" in remaining

    def test_multiple_types(self):
        _, types = self.p._extract_types("query type:pdf type:docx")
        assert "pdf" in types
        assert "docx" in types


# ===========================================================================
# _extract_dates
# ===========================================================================

class TestExtractDates:
    def setup_method(self):
        self.p = _parser()

    def test_no_date_returns_none(self):
        _, date_range = self.p._extract_dates("diabetes treatment")
        assert date_range is None

    def test_date_today_returns_tuple(self):
        _, date_range = self.p._extract_dates("query date:today")
        assert date_range is not None
        assert isinstance(date_range, tuple)
        assert len(date_range) == 2

    def test_date_today_start_is_midnight(self):
        _, date_range = self.p._extract_dates("query date:today")
        assert date_range[0].hour == 0
        assert date_range[0].minute == 0
        assert date_range[0].second == 0

    def test_date_yesterday_returns_tuple(self):
        _, date_range = self.p._extract_dates("query date:yesterday")
        assert date_range is not None

    def test_date_yesterday_start_before_today_midnight(self):
        today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        _, date_range = self.p._extract_dates("query date:yesterday")
        assert date_range[0] < today_midnight

    def test_date_last_week_returns_tuple(self):
        _, date_range = self.p._extract_dates("query date:last-week")
        assert date_range is not None

    def test_date_last_week_start_approx_7_days_ago(self):
        _, date_range = self.p._extract_dates("query date:last-week")
        diff = datetime.now() - date_range[0]
        assert 6 <= diff.days <= 8

    def test_date_last_month_returns_tuple(self):
        _, date_range = self.p._extract_dates("query date:last-month")
        assert date_range is not None

    def test_date_last_year_returns_tuple(self):
        _, date_range = self.p._extract_dates("query date:last-year")
        assert date_range is not None

    def test_date_this_year_returns_tuple(self):
        _, date_range = self.p._extract_dates("query date:this-year")
        assert date_range is not None

    def test_date_year_2024(self):
        _, date_range = self.p._extract_dates("query date:2024")
        assert date_range is not None
        assert date_range[0].year == 2024
        assert date_range[0].month == 1
        assert date_range[1].year == 2024
        assert date_range[1].month == 12

    def test_date_year_month(self):
        _, date_range = self.p._extract_dates("query date:2024-06")
        assert date_range is not None
        assert date_range[0].year == 2024
        assert date_range[0].month == 6
        assert date_range[0].day == 1
        assert date_range[1].month == 6  # still June

    def test_date_specific_day(self):
        _, date_range = self.p._extract_dates("query date:2024-06-15")
        assert date_range is not None
        assert date_range[0].year == 2024
        assert date_range[0].month == 6
        assert date_range[0].day == 15
        assert date_range[1].day == 15

    def test_date_specific_day_spans_full_day(self):
        _, date_range = self.p._extract_dates("query date:2024-06-15")
        assert date_range[0].hour == 0
        assert date_range[1].hour == 23

    def test_invalid_date_returns_none(self):
        _, date_range = self.p._extract_dates("query date:notadate")
        assert date_range is None

    def test_date_removed_from_query(self):
        remaining, _ = self.p._extract_dates("diabetes date:2024 treatment")
        assert "date:2024" not in remaining
        assert "diabetes" in remaining

    def test_date_december_month_range_correct(self):
        _, date_range = self.p._extract_dates("query date:2024-12")
        assert date_range is not None
        assert date_range[0].month == 12
        assert date_range[1].month == 12


# ===========================================================================
# _extract_entities
# ===========================================================================

class TestExtractEntities:
    def setup_method(self):
        self.p = _parser()

    def test_no_entity_returns_empty_dict(self):
        _, entities = self.p._extract_entities("diabetes treatment")
        assert entities == {}

    def test_entity_medication_aspirin(self):
        _, entities = self.p._extract_entities("query entity:medication:aspirin")
        assert "medication" in entities
        assert "aspirin" in entities["medication"]

    def test_entity_alias_med(self):
        _, entities = self.p._extract_entities("query entity:med:aspirin")
        assert "medication" in entities

    def test_entity_alias_drug(self):
        _, entities = self.p._extract_entities("query entity:drug:metformin")
        assert "medication" in entities
        assert "metformin" in entities["medication"]

    def test_entity_condition_diabetes(self):
        _, entities = self.p._extract_entities("query entity:condition:diabetes")
        assert "condition" in entities
        assert "diabetes" in entities["condition"]

    def test_entity_alias_disease(self):
        _, entities = self.p._extract_entities("query entity:disease:diabetes")
        assert "condition" in entities

    def test_entity_alias_diagnosis(self):
        _, entities = self.p._extract_entities("query entity:diagnosis:hypertension")
        assert "condition" in entities

    def test_entity_symptom(self):
        _, entities = self.p._extract_entities("query entity:symptom:pain")
        assert "symptom" in entities

    def test_entity_alias_sx(self):
        _, entities = self.p._extract_entities("query entity:sx:pain")
        assert "symptom" in entities

    def test_entity_lab_alias(self):
        _, entities = self.p._extract_entities("query entity:lab:creatinine")
        assert "lab_test" in entities

    def test_entity_body_alias(self):
        _, entities = self.p._extract_entities("query entity:body:kidney")
        assert "anatomy" in entities

    def test_entity_unknown_type_passthrough(self):
        _, entities = self.p._extract_entities("query entity:foobar:xyz")
        assert "foobar" in entities

    def test_entity_removed_from_query(self):
        remaining, _ = self.p._extract_entities("diabetes entity:medication:aspirin treatment")
        assert "entity:medication:aspirin" not in remaining
        assert "diabetes" in remaining

    def test_multiple_entities_same_type_combined(self):
        query = "query entity:medication:aspirin entity:medication:warfarin"
        _, entities = self.p._extract_entities(query)
        assert len(entities.get("medication", [])) == 2

    def test_deduplication_same_entity(self):
        query = "query entity:medication:aspirin entity:medication:aspirin"
        _, entities = self.p._extract_entities(query)
        assert entities["medication"].count("aspirin") == 1


# ===========================================================================
# _extract_min_score
# ===========================================================================

class TestExtractMinScore:
    def setup_method(self):
        self.p = _parser()

    def test_no_score_returns_zero(self):
        _, score = self.p._extract_min_score("diabetes treatment")
        assert score == 0.0

    def test_score_decimal(self):
        _, score = self.p._extract_min_score("query score:>0.8")
        assert abs(score - 0.8) < 1e-9

    def test_score_percentage_normalized(self):
        _, score = self.p._extract_min_score("query score:>80")
        assert abs(score - 0.8) < 1e-9

    def test_score_50_percent(self):
        _, score = self.p._extract_min_score("query score:>50")
        assert abs(score - 0.5) < 1e-9

    def test_score_clamped_at_1(self):
        _, score = self.p._extract_min_score("query score:>200")
        assert score == 1.0

    def test_score_zero_returns_zero(self):
        _, score = self.p._extract_min_score("query score:>0")
        assert score == 0.0

    def test_score_returns_float(self):
        _, score = self.p._extract_min_score("query score:>0.5")
        assert isinstance(score, float)

    def test_score_removed_from_query(self):
        remaining, _ = self.p._extract_min_score("diabetes score:>0.7 treatment")
        assert "score:>0.7" not in remaining
        assert "diabetes" in remaining


# ===========================================================================
# _extract_excludes
# ===========================================================================

class TestExtractExcludes:
    def setup_method(self):
        self.p = _parser()

    def test_no_exclude_returns_empty(self):
        _, excludes = self.p._extract_excludes("diabetes treatment")
        assert excludes == []

    def test_single_exclude_term(self):
        _, excludes = self.p._extract_excludes("diabetes -old treatment")
        assert "old" in excludes

    def test_exclude_lowercased(self):
        _, excludes = self.p._extract_excludes("query -OUTDATED")
        # Exclude pattern finds the term; it normalizes to lowercase
        assert any(t == t.lower() for t in excludes)

    def test_multiple_excludes(self):
        _, excludes = self.p._extract_excludes("diabetes -old -outdated treatment")
        assert len(excludes) == 2

    def test_deduplication_same_exclude(self):
        _, excludes = self.p._extract_excludes("query -old -old")
        assert excludes.count("old") == 1

    def test_exclude_removed_from_query(self):
        remaining, _ = self.p._extract_excludes("diabetes -old treatment")
        # The minus and term should not appear as -word in remaining
        assert "-old" not in remaining


# ===========================================================================
# _extract_phrases
# ===========================================================================

class TestExtractPhrases:
    def setup_method(self):
        self.p = _parser()

    def test_no_quotes_returns_empty(self):
        _, phrases = self.p._extract_phrases("diabetes treatment")
        assert phrases == []

    def test_single_phrase(self):
        _, phrases = self.p._extract_phrases('query "heart failure"')
        assert "heart failure" in phrases

    def test_multiple_phrases(self):
        _, phrases = self.p._extract_phrases('"heart failure" "blood pressure"')
        assert "heart failure" in phrases
        assert "blood pressure" in phrases

    def test_deduplication(self):
        _, phrases = self.p._extract_phrases('"heart failure" "heart failure"')
        assert phrases.count("heart failure") == 1

    def test_quotes_removed_from_query(self):
        remaining, _ = self.p._extract_phrases('diabetes "heart failure" treatment')
        assert '"heart failure"' not in remaining

    def test_phrase_text_preserved_in_query(self):
        # Quotes removed but text remains in working query
        remaining, _ = self.p._extract_phrases('diabetes "heart failure" treatment')
        assert "heart failure" in remaining


# ===========================================================================
# _clean_query
# ===========================================================================

class TestCleanQuery:
    def setup_method(self):
        self.p = _parser()

    def test_multiple_spaces_collapsed(self):
        result = self.p._clean_query("diabetes   treatment")
        assert "  " not in result

    def test_leading_whitespace_stripped(self):
        result = self.p._clean_query("   diabetes")
        assert result == "diabetes"

    def test_trailing_whitespace_stripped(self):
        result = self.p._clean_query("diabetes   ")
        assert result == "diabetes"

    def test_empty_string_returns_empty(self):
        result = self.p._clean_query("")
        assert result == ""

    def test_only_spaces_returns_empty(self):
        result = self.p._clean_query("    ")
        assert result == ""

    def test_normal_query_unchanged(self):
        result = self.p._clean_query("diabetes treatment")
        assert result == "diabetes treatment"


# ===========================================================================
# parse() integration
# ===========================================================================

class TestParseIntegration:
    def setup_method(self):
        self.p = _parser()

    def test_plain_query_no_filters(self):
        pq = self.p.parse("diabetes treatment guidelines")
        assert pq.has_filters is False

    def test_plain_query_text_preserved(self):
        pq = self.p.parse("diabetes treatment guidelines")
        assert "diabetes" in pq.text

    def test_original_query_always_preserved(self):
        q = "diabetes type:pdf date:2024"
        pq = self.p.parse(q)
        assert pq.original_query == q

    def test_type_filter_extracted(self):
        pq = self.p.parse("diabetes treatment type:pdf")
        assert "pdf" in pq.document_types

    def test_date_filter_extracted(self):
        pq = self.p.parse("diabetes date:2024")
        assert pq.date_range is not None

    def test_entity_filter_extracted(self):
        pq = self.p.parse("query entity:medication:aspirin")
        assert "medication" in pq.entity_filters

    def test_score_filter_extracted(self):
        pq = self.p.parse("diabetes score:>0.8")
        assert pq.min_score == pytest.approx(0.8)

    def test_exclude_extracted(self):
        pq = self.p.parse("diabetes -old treatment")
        assert "old" in pq.exclude_terms

    def test_phrase_extracted(self):
        pq = self.p.parse('"heart failure" treatment')
        assert "heart failure" in pq.exact_phrases

    def test_complex_query_multiple_filters(self):
        q = 'diabetes type:pdf date:2024 entity:medication:metformin -old "type 2 diabetes" score:>0.7'
        pq = self.p.parse(q)
        assert "pdf" in pq.document_types
        assert pq.date_range is not None
        assert "medication" in pq.entity_filters
        assert "old" in pq.exclude_terms
        assert "type 2 diabetes" in pq.exact_phrases
        assert pq.min_score > 0

    def test_empty_query_returns_parsed_query(self):
        pq = self.p.parse("")
        assert isinstance(pq, ParsedQuery)

    def test_returns_parsed_query_type(self):
        pq = self.p.parse("test query")
        assert isinstance(pq, ParsedQuery)


# ===========================================================================
# format_help
# ===========================================================================

class TestFormatHelp:
    def setup_method(self):
        self.p = _parser()

    def test_returns_non_empty_string(self):
        result = self.p.format_help()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_type_syntax(self):
        assert "type:" in self.p.format_help()

    def test_contains_date_syntax(self):
        assert "date:" in self.p.format_help()

    def test_contains_entity_syntax(self):
        assert "entity:" in self.p.format_help()

    def test_contains_score_syntax(self):
        assert "score:" in self.p.format_help()


# ===========================================================================
# Singleton and convenience function
# ===========================================================================

class TestSingletonAndConvenience:
    def test_get_parser_returns_instance(self):
        p = get_search_syntax_parser()
        assert isinstance(p, SearchSyntaxParser)

    def test_get_parser_same_instance_twice(self):
        p1 = get_search_syntax_parser()
        p2 = get_search_syntax_parser()
        assert p1 is p2

    def test_reset_clears_singleton(self):
        p1 = get_search_syntax_parser()
        ssp_module._parser = None
        p2 = get_search_syntax_parser()
        assert p1 is not p2

    def test_parse_search_query_returns_parsed_query(self):
        pq = parse_search_query("diabetes treatment")
        assert isinstance(pq, ParsedQuery)

    def test_parse_search_query_preserves_original(self):
        q = "diabetes type:pdf"
        pq = parse_search_query(q)
        assert pq.original_query == q

    def test_parse_search_query_extracts_type(self):
        pq = parse_search_query("diabetes type:pdf")
        assert "pdf" in pq.document_types
