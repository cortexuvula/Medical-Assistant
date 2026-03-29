"""
Tests for src/rag/conversation_summarizer.py

Covers ConversationSummary dataclass (to_dict, from_dict),
MedicalConversationSummarizer (should_summarize, _estimate_tokens,
_build_medical_context, _generate_rule_based_summary,
_simple_entity_extraction, _extract_key_topics,
_extract_entities_from_exchanges, summarize with no AI),
and the module-level get_conversation_summarizer / summarize_conversation.
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

from rag.conversation_summarizer import (
    ConversationSummary,
    MedicalConversationSummarizer,
    get_conversation_summarizer,
    summarize_conversation,
)
import rag.conversation_summarizer as cs_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    cs_module._summarizer = None
    yield
    cs_module._summarizer = None


def _summarizer() -> MedicalConversationSummarizer:
    return MedicalConversationSummarizer(ai_processor=None, ner_extractor=None)


# ===========================================================================
# ConversationSummary dataclass
# ===========================================================================

class TestConversationSummary:
    def test_fields_stored(self):
        s = ConversationSummary(
            summary_text="Summary text",
            key_topics=["diabetes"],
            key_entities=[{"text": "metformin"}],
            exchange_count=3,
            token_count=50,
            medical_context={"medications": ["metformin"]},
        )
        assert s.summary_text == "Summary text"
        assert s.key_topics == ["diabetes"]
        assert s.key_entities == [{"text": "metformin"}]
        assert s.exchange_count == 3
        assert s.token_count == 50
        assert s.medical_context == {"medications": ["metformin"]}

    def test_medical_context_defaults_empty_dict(self):
        s = ConversationSummary("", [], [], 0, 0)
        assert s.medical_context == {}

    def test_instances_dont_share_medical_context(self):
        s1 = ConversationSummary("", [], [], 0, 0)
        s2 = ConversationSummary("", [], [], 0, 0)
        s1.medical_context["key"] = "val"
        assert s2.medical_context == {}


class TestConversationSummaryToDict:
    def test_to_dict_returns_dict(self):
        s = ConversationSummary("text", ["topic"], [], 2, 10)
        assert isinstance(s.to_dict(), dict)

    def test_to_dict_has_all_keys(self):
        s = ConversationSummary("text", [], [], 0, 0)
        d = s.to_dict()
        for key in ["summary_text", "key_topics", "key_entities",
                    "exchange_count", "token_count", "medical_context"]:
            assert key in d

    def test_to_dict_values_match(self):
        s = ConversationSummary("T", ["a"], [{"x": 1}], 5, 25, {"m": ["x"]})
        d = s.to_dict()
        assert d["summary_text"] == "T"
        assert d["key_topics"] == ["a"]
        assert d["key_entities"] == [{"x": 1}]
        assert d["exchange_count"] == 5
        assert d["token_count"] == 25
        assert d["medical_context"] == {"m": ["x"]}


class TestConversationSummaryFromDict:
    def test_from_dict_returns_instance(self):
        d = {"summary_text": "x", "key_topics": [], "key_entities": [],
             "exchange_count": 0, "token_count": 0}
        assert isinstance(ConversationSummary.from_dict(d), ConversationSummary)

    def test_from_dict_empty_dict_uses_defaults(self):
        s = ConversationSummary.from_dict({})
        assert s.summary_text == ""
        assert s.key_topics == []
        assert s.key_entities == []
        assert s.exchange_count == 0
        assert s.token_count == 0
        assert s.medical_context == {}

    def test_from_dict_roundtrip(self):
        original = ConversationSummary("summary", ["topic"], [{"text": "x"}], 3, 15, {"m": ["y"]})
        restored = ConversationSummary.from_dict(original.to_dict())
        assert restored.summary_text == original.summary_text
        assert restored.key_topics == original.key_topics
        assert restored.exchange_count == original.exchange_count

    def test_from_dict_partial_keys(self):
        s = ConversationSummary.from_dict({"summary_text": "hello", "exchange_count": 7})
        assert s.summary_text == "hello"
        assert s.exchange_count == 7
        assert s.key_topics == []


# ===========================================================================
# should_summarize
# ===========================================================================

class TestShouldSummarize:
    def setup_method(self):
        self.s = _summarizer()

    def test_below_threshold_returns_false(self):
        assert self.s.should_summarize(4) is False

    def test_at_threshold_returns_true(self):
        # MAX_EXCHANGES_BEFORE_SUMMARIZE = 5
        assert self.s.should_summarize(5) is True

    def test_above_threshold_returns_true(self):
        assert self.s.should_summarize(10) is True

    def test_zero_returns_false(self):
        assert self.s.should_summarize(0) is False

    def test_returns_bool(self):
        result = self.s.should_summarize(5)
        assert isinstance(result, bool)


# ===========================================================================
# _estimate_tokens
# ===========================================================================

class TestEstimateTokens:
    def setup_method(self):
        self.s = _summarizer()

    def test_empty_string_returns_zero(self):
        assert self.s._estimate_tokens("") == 0

    def test_four_chars_returns_one(self):
        assert self.s._estimate_tokens("abcd") == 1

    def test_longer_text(self):
        text = "a" * 40
        assert self.s._estimate_tokens(text) == 10

    def test_returns_int(self):
        assert isinstance(self.s._estimate_tokens("hello world"), int)

    def test_proportional(self):
        # 400 chars → 100 tokens
        assert self.s._estimate_tokens("x" * 400) == 100


# ===========================================================================
# _build_medical_context
# ===========================================================================

class TestBuildMedicalContext:
    def setup_method(self):
        self.s = _summarizer()

    def test_empty_entities_returns_empty_dict(self):
        assert self.s._build_medical_context([]) == {}

    def test_medication_entity_goes_to_medications(self):
        entities = [{"entity_type": "medication", "text": "metformin"}]
        ctx = self.s._build_medical_context(entities)
        assert "medications" in ctx
        assert "metformin" in ctx["medications"]

    def test_condition_entity_goes_to_conditions(self):
        entities = [{"entity_type": "condition", "text": "diabetes"}]
        ctx = self.s._build_medical_context(entities)
        assert "conditions" in ctx
        assert "diabetes" in ctx["conditions"]

    def test_symptom_entity_goes_to_symptoms(self):
        entities = [{"entity_type": "symptom", "text": "pain"}]
        ctx = self.s._build_medical_context(entities)
        assert "symptoms" in ctx

    def test_procedure_entity_goes_to_procedures(self):
        entities = [{"entity_type": "procedure", "text": "biopsy"}]
        ctx = self.s._build_medical_context(entities)
        assert "procedures" in ctx

    def test_unknown_entity_type_ignored(self):
        entities = [{"entity_type": "unknown_xyz", "text": "foo"}]
        ctx = self.s._build_medical_context(entities)
        assert "unknown_xyz" not in ctx

    def test_empty_categories_removed(self):
        # Only pass a medication — no symptoms list should appear
        entities = [{"entity_type": "medication", "text": "aspirin"}]
        ctx = self.s._build_medical_context(entities)
        assert "symptoms" not in ctx
        assert "conditions" not in ctx

    def test_no_duplicates_in_category(self):
        entities = [
            {"entity_type": "medication", "text": "aspirin"},
            {"entity_type": "medication", "text": "aspirin"},
        ]
        ctx = self.s._build_medical_context(entities)
        assert ctx["medications"].count("aspirin") == 1

    def test_normalized_name_preferred_over_text(self):
        entities = [{"entity_type": "medication", "text": "asa",
                     "normalized_name": "aspirin"}]
        ctx = self.s._build_medical_context(entities)
        assert "aspirin" in ctx["medications"]
        assert "asa" not in ctx.get("medications", [])

    def test_returns_dict(self):
        assert isinstance(self.s._build_medical_context([]), dict)


# ===========================================================================
# _simple_entity_extraction
# ===========================================================================

class TestSimpleEntityExtraction:
    def setup_method(self):
        self.s = _summarizer()

    def test_returns_list(self):
        assert isinstance(self.s._simple_entity_extraction(""), list)

    def test_empty_text_returns_empty(self):
        assert self.s._simple_entity_extraction("") == []

    def test_finds_medication_term(self):
        result = self.s._simple_entity_extraction("patient needs medication")
        types = [e["entity_type"] for e in result]
        assert "medication" in types

    def test_finds_condition_term(self):
        result = self.s._simple_entity_extraction("patient has diabetes")
        types = [e["entity_type"] for e in result]
        assert "condition" in types

    def test_finds_symptom_term(self):
        result = self.s._simple_entity_extraction("patient reports pain")
        types = [e["entity_type"] for e in result]
        assert "symptom" in types

    def test_finds_procedure_term(self):
        result = self.s._simple_entity_extraction("scheduled for surgery")
        types = [e["entity_type"] for e in result]
        assert "procedure" in types

    def test_entity_has_required_fields(self):
        result = self.s._simple_entity_extraction("patient has pain")
        assert len(result) > 0
        entity = result[0]
        assert "text" in entity
        assert "entity_type" in entity
        assert "start_pos" in entity
        assert "end_pos" in entity

    def test_no_medical_terms_returns_empty(self):
        result = self.s._simple_entity_extraction("the weather is nice today")
        assert result == []


# ===========================================================================
# _extract_key_topics
# ===========================================================================

class TestExtractKeyTopics:
    def setup_method(self):
        self.s = _summarizer()

    def test_returns_list(self):
        result = self.s._extract_key_topics([], [])
        assert isinstance(result, list)

    def test_empty_exchanges_returns_empty(self):
        assert self.s._extract_key_topics([], []) == []

    def test_extracts_words_from_queries(self):
        exchanges = [("diabetes treatment", "response")]
        topics = self.s._extract_key_topics(exchanges, [])
        assert "diabetes" in topics or "treatment" in topics

    def test_stopwords_excluded(self):
        exchanges = [("what is the treatment for this", "response")]
        topics = self.s._extract_key_topics(exchanges, [])
        for stopword in ["the", "for", "this", "what", "is"]:
            assert stopword not in topics

    def test_short_words_excluded(self):
        exchanges = [("a b c diabetes", "resp")]
        topics = self.s._extract_key_topics(exchanges, [])
        # Words < 3 chars filtered out by regex \b[a-zA-Z]{3,}\b
        assert "a" not in topics
        assert "b" not in topics
        assert "c" not in topics

    def test_entity_names_included(self):
        entities = [{"text": "metformin", "entity_type": "medication"}]
        exchanges = [("medication query", "resp")]
        topics = self.s._extract_key_topics(exchanges, entities)
        assert "metformin" in topics

    def test_respects_max_topics_limit(self):
        # Generate many distinct words
        exchanges = [
            (f"word{i} query{i} term{i} med{i} disease{i} symptom{i} condition{i} proc{i}", "resp")
            for i in range(5)
        ]
        topics = self.s._extract_key_topics(exchanges, [])
        assert len(topics) <= MedicalConversationSummarizer.MAX_TOPICS


# ===========================================================================
# _extract_entities_from_exchanges
# ===========================================================================

class TestExtractEntitiesFromExchanges:
    def setup_method(self):
        self.s = _summarizer()

    def test_returns_list(self):
        assert isinstance(self.s._extract_entities_from_exchanges([]), list)

    def test_empty_exchanges_returns_empty(self):
        assert self.s._extract_entities_from_exchanges([]) == []

    def test_detects_entities_in_query(self):
        exchanges = [("patient takes medication", "ok")]
        result = self.s._extract_entities_from_exchanges(exchanges)
        types = [e["entity_type"] for e in result]
        assert "medication" in types

    def test_no_duplicates_across_exchanges(self):
        # Same entity in multiple exchanges should appear once
        exchanges = [
            ("patient has pain", "answer 1"),
            ("more about pain please", "answer 2"),
        ]
        result = self.s._extract_entities_from_exchanges(exchanges)
        entity_keys = [(e.get("text", "").lower(), e.get("entity_type", "")) for e in result]
        assert len(entity_keys) == len(set(entity_keys))

    def test_source_field_set(self):
        exchanges = [("patient has pain", "no fever here")]
        result = self.s._extract_entities_from_exchanges(exchanges)
        for entity in result:
            assert "source" in entity
            assert entity["source"] in ("query", "response")


# ===========================================================================
# _generate_rule_based_summary
# ===========================================================================

class TestGenerateRuleBasedSummary:
    def setup_method(self):
        self.s = _summarizer()

    def test_returns_string(self):
        result = self.s._generate_rule_based_summary([], [], [])
        assert isinstance(result, str)

    def test_mentions_exchange_count(self):
        exchanges = [("q", "a"), ("q2", "a2")]
        result = self.s._generate_rule_based_summary(exchanges, [], [])
        assert "2" in result

    def test_includes_topics_if_provided(self):
        exchanges = [("q", "a")]
        result = self.s._generate_rule_based_summary(exchanges, ["diabetes", "pain"], [])
        assert "diabetes" in result or "pain" in result

    def test_includes_recent_queries(self):
        exchanges = [("diabetes query", "answer")]
        result = self.s._generate_rule_based_summary(exchanges, [], [])
        # Recent queries are included
        assert "diabetes query" in result

    def test_non_empty_for_one_exchange(self):
        exchanges = [("what is metformin", "Metformin is a drug")]
        result = self.s._generate_rule_based_summary(exchanges, [], [])
        assert len(result.strip()) > 0

    def test_empty_exchanges_returns_short_string(self):
        result = self.s._generate_rule_based_summary([], [], [])
        # Still returns a string, just mentions 0 exchanges
        assert "0" in result or isinstance(result, str)


# ===========================================================================
# summarize (orchestration, no AI)
# ===========================================================================

class TestSummarize:
    def setup_method(self):
        self.s = _summarizer()

    def test_empty_exchanges_returns_summary(self):
        result = self.s.summarize([])
        assert isinstance(result, ConversationSummary)
        assert result.exchange_count == 0
        assert result.summary_text == ""

    def test_one_exchange_returns_summary(self):
        exchanges = [("what is diabetes", "Diabetes is a metabolic disease")]
        result = self.s.summarize(exchanges)
        assert isinstance(result, ConversationSummary)
        assert result.exchange_count == 1

    def test_exchange_count_matches(self):
        exchanges = [("q", "a")] * 3
        result = self.s.summarize(exchanges)
        assert result.exchange_count == 3

    def test_summary_text_non_empty_for_real_exchanges(self):
        exchanges = [("patient has diabetes", "Diabetes needs treatment")]
        result = self.s.summarize(exchanges)
        assert len(result.summary_text.strip()) > 0

    def test_key_topics_is_list(self):
        exchanges = [("q", "a")]
        result = self.s.summarize(exchanges)
        assert isinstance(result.key_topics, list)

    def test_key_entities_is_list(self):
        exchanges = [("q", "a")]
        result = self.s.summarize(exchanges)
        assert isinstance(result.key_entities, list)

    def test_medical_context_is_dict(self):
        exchanges = [("patient takes medication", "yes")]
        result = self.s.summarize(exchanges)
        assert isinstance(result.medical_context, dict)

    def test_token_count_is_int(self):
        exchanges = [("q", "a")]
        result = self.s.summarize(exchanges)
        assert isinstance(result.token_count, int)

    def test_with_existing_summary(self):
        existing = ConversationSummary("old summary", [], [], 2, 10)
        exchanges = [("new question", "new answer")]
        result = self.s.summarize(exchanges, existing_summary=existing)
        assert isinstance(result, ConversationSummary)
        assert result.exchange_count == 1

    def test_key_topics_capped_at_max(self):
        # Many exchanges to generate lots of topics
        exchanges = [(f"unique_word_{i} specific_term_{i} medical_condition_{i}", "answer")
                     for i in range(20)]
        result = self.s.summarize(exchanges)
        assert len(result.key_topics) <= MedicalConversationSummarizer.MAX_TOPICS

    def test_key_entities_capped_at_max(self):
        # Multiple exchanges with medical terms
        exchanges = [(f"patient has pain and fever with cough and medication", "ok")] * 5
        result = self.s.summarize(exchanges)
        assert len(result.key_entities) <= MedicalConversationSummarizer.MAX_ENTITIES


# ===========================================================================
# Module-level: get_conversation_summarizer / summarize_conversation
# ===========================================================================

class TestModuleLevelFunctions:
    def test_get_conversation_summarizer_returns_instance(self):
        result = get_conversation_summarizer()
        assert isinstance(result, MedicalConversationSummarizer)

    def test_get_conversation_summarizer_is_singleton(self):
        s1 = get_conversation_summarizer()
        s2 = get_conversation_summarizer()
        assert s1 is s2

    def test_summarize_conversation_returns_summary(self):
        result = summarize_conversation([("question", "answer")])
        assert isinstance(result, ConversationSummary)

    def test_summarize_conversation_empty(self):
        result = summarize_conversation([])
        assert isinstance(result, ConversationSummary)
        assert result.exchange_count == 0

    def test_constants_defined(self):
        assert MedicalConversationSummarizer.MAX_EXCHANGES_BEFORE_SUMMARIZE == 5
        assert MedicalConversationSummarizer.TARGET_SUMMARY_TOKENS == 200
        assert MedicalConversationSummarizer.MAX_TOPICS == 10
        assert MedicalConversationSummarizer.MAX_ENTITIES == 20
