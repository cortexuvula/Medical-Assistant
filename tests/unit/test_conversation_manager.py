"""
Tests for src/rag/conversation_manager.py

Covers ConversationExchange dataclass, ConversationSession dataclass,
RAGConversationManager, get_conversation_manager, and
reset_conversation_manager.

No network, no Tkinter, no I/O.
"""
import sys
import uuid
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import rag.conversation_manager as _cm_module
from rag.conversation_manager import (
    ConversationExchange,
    ConversationSession,
    RAGConversationManager,
    get_conversation_manager,
    reset_conversation_manager,
)


# ---------------------------------------------------------------------------
# Singleton reset fixture (autouse so every test gets a clean slate)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_manager():
    _cm_module._manager = None
    yield
    _cm_module._manager = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(session_id: str = None) -> ConversationSession:
    return ConversationSession(session_id=session_id or str(uuid.uuid4()))


def _make_exchange(index: int = 0, query: str = "What is hypertension?") -> ConversationExchange:
    return ConversationExchange(exchange_index=index, query_text=query)


# ---------------------------------------------------------------------------
# TestConversationExchange
# ---------------------------------------------------------------------------

class TestConversationExchange:
    """Tests for ConversationExchange dataclass."""

    def test_create_with_required_fields(self):
        ex = ConversationExchange(exchange_index=0, query_text="test query")
        assert ex.exchange_index == 0
        assert ex.query_text == "test query"

    def test_default_response_summary_empty(self):
        ex = _make_exchange()
        assert ex.response_summary == ""

    def test_default_query_embedding_none(self):
        ex = _make_exchange()
        assert ex.query_embedding is None

    def test_default_extracted_entities_empty_list(self):
        ex = _make_exchange()
        assert ex.extracted_entities == []

    def test_default_is_followup_false(self):
        ex = _make_exchange()
        assert ex.is_followup is False

    def test_default_followup_confidence_zero(self):
        ex = _make_exchange()
        assert ex.followup_confidence == 0.0

    def test_default_intent_type(self):
        ex = _make_exchange()
        assert ex.intent_type == "new_topic"

    def test_created_at_is_datetime(self):
        ex = _make_exchange()
        assert isinstance(ex.created_at, datetime)

    def test_created_at_is_recent(self):
        before = datetime.now()
        ex = _make_exchange()
        after = datetime.now()
        assert before <= ex.created_at <= after

    def test_custom_response_summary(self):
        ex = ConversationExchange(exchange_index=1, query_text="q", response_summary="brief")
        assert ex.response_summary == "brief"

    def test_custom_query_embedding(self):
        emb = [0.1, 0.2, 0.3]
        ex = ConversationExchange(exchange_index=0, query_text="q", query_embedding=emb)
        assert ex.query_embedding == emb

    def test_custom_extracted_entities(self):
        ents = [{"text": "aspirin", "type": "medication"}]
        ex = ConversationExchange(exchange_index=0, query_text="q", extracted_entities=ents)
        assert ex.extracted_entities == ents

    def test_custom_is_followup_true(self):
        ex = ConversationExchange(exchange_index=0, query_text="q", is_followup=True)
        assert ex.is_followup is True

    def test_custom_followup_confidence(self):
        ex = ConversationExchange(exchange_index=0, query_text="q", followup_confidence=0.87)
        assert ex.followup_confidence == pytest.approx(0.87)

    def test_custom_intent_type(self):
        ex = ConversationExchange(exchange_index=0, query_text="q", intent_type="elaboration")
        assert ex.intent_type == "elaboration"

    def test_to_dict_returns_dict(self):
        ex = _make_exchange()
        assert isinstance(ex.to_dict(), dict)

    def test_to_dict_contains_exchange_index(self):
        ex = _make_exchange(index=3)
        assert "exchange_index" in ex.to_dict()
        assert ex.to_dict()["exchange_index"] == 3

    def test_to_dict_contains_query_text(self):
        ex = _make_exchange(query="my query")
        assert ex.to_dict()["query_text"] == "my query"

    def test_to_dict_contains_response_summary(self):
        ex = ConversationExchange(exchange_index=0, query_text="q", response_summary="summ")
        assert ex.to_dict()["response_summary"] == "summ"

    def test_to_dict_contains_extracted_entities(self):
        ex = _make_exchange()
        assert "extracted_entities" in ex.to_dict()

    def test_to_dict_contains_is_followup(self):
        ex = _make_exchange()
        assert "is_followup" in ex.to_dict()

    def test_to_dict_contains_followup_confidence(self):
        ex = _make_exchange()
        assert "followup_confidence" in ex.to_dict()

    def test_to_dict_contains_intent_type(self):
        ex = _make_exchange()
        assert "intent_type" in ex.to_dict()

    def test_to_dict_contains_created_at(self):
        ex = _make_exchange()
        d = ex.to_dict()
        assert "created_at" in d

    def test_to_dict_created_at_is_isoformat_string(self):
        ex = _make_exchange()
        d = ex.to_dict()
        # Should be parseable as ISO datetime
        dt = datetime.fromisoformat(d["created_at"])
        assert isinstance(dt, datetime)


# ---------------------------------------------------------------------------
# TestConversationSession
# ---------------------------------------------------------------------------

class TestConversationSession:
    """Tests for ConversationSession dataclass."""

    def test_exchange_count_zero_initially(self):
        session = _make_session()
        assert session.exchange_count == 0

    def test_last_query_none_when_empty(self):
        session = _make_session()
        assert session.last_query is None

    def test_last_embedding_none_when_empty(self):
        session = _make_session()
        assert session.last_embedding is None

    def test_topics_empty_when_no_exchanges_no_key_topics(self):
        session = _make_session()
        assert session.topics == []

    def test_topics_returns_key_topics_when_set(self):
        session = _make_session()
        session.key_topics = ["hypertension", "diabetes"]
        assert session.topics == ["hypertension", "diabetes"]

    def test_add_exchange_increases_count(self):
        session = _make_session()
        session.add_exchange(query="q1", response="r1")
        assert session.exchange_count == 1

    def test_add_exchange_twice_count_is_two(self):
        session = _make_session()
        session.add_exchange(query="q1", response="r1")
        session.add_exchange(query="q2", response="r2")
        assert session.exchange_count == 2

    def test_last_query_returns_latest(self):
        session = _make_session()
        session.add_exchange(query="first", response="r1")
        session.add_exchange(query="second", response="r2")
        assert session.last_query == "second"

    def test_last_embedding_returns_latest(self):
        session = _make_session()
        emb1 = [0.1, 0.2]
        emb2 = [0.3, 0.4]
        session.add_exchange(query="q1", response="r1", embedding=emb1)
        session.add_exchange(query="q2", response="r2", embedding=emb2)
        assert session.last_embedding == emb2

    def test_last_embedding_none_when_no_embedding_provided(self):
        session = _make_session()
        session.add_exchange(query="q1", response="r1")
        assert session.last_embedding is None

    def test_add_exchange_stores_is_followup(self):
        session = _make_session()
        session.add_exchange(query="q", response="r", is_followup=True)
        assert session.exchanges[-1].is_followup is True

    def test_add_exchange_stores_intent_type(self):
        session = _make_session()
        session.add_exchange(query="q", response="r", intent_type="elaboration")
        assert session.exchanges[-1].intent_type == "elaboration"

    def test_add_exchange_truncates_long_response(self):
        session = _make_session()
        long_response = "x" * 500
        session.add_exchange(query="q", response=long_response)
        assert len(session.exchanges[-1].response_summary) <= 200

    def test_add_exchange_stores_entities(self):
        session = _make_session()
        ents = [{"text": "metformin"}]
        session.add_exchange(query="q", response="r", entities=ents)
        assert session.exchanges[-1].extracted_entities == ents

    def test_compress_exchanges_keeps_recent(self):
        session = _make_session()
        for i in range(5):
            session.add_exchange(query=f"q{i}", response=f"r{i}")
        session.compress_exchanges(keep_recent=2)
        assert session.exchange_count == 2

    def test_compress_exchanges_reindexes(self):
        session = _make_session()
        for i in range(5):
            session.add_exchange(query=f"q{i}", response=f"r{i}")
        session.compress_exchanges(keep_recent=2)
        for idx, ex in enumerate(session.exchanges):
            assert ex.exchange_index == idx

    def test_compress_exchanges_keeps_most_recent_queries(self):
        session = _make_session()
        for i in range(5):
            session.add_exchange(query=f"query_{i}", response="r")
        session.compress_exchanges(keep_recent=2)
        assert session.exchanges[0].query_text == "query_3"
        assert session.exchanges[1].query_text == "query_4"

    def test_compress_exchanges_noop_when_few_exchanges(self):
        session = _make_session()
        session.add_exchange(query="q1", response="r1")
        session.compress_exchanges(keep_recent=3)
        assert session.exchange_count == 1

    def test_compress_exchanges_noop_when_exactly_keep_recent(self):
        session = _make_session()
        for i in range(2):
            session.add_exchange(query=f"q{i}", response="r")
        session.compress_exchanges(keep_recent=2)
        assert session.exchange_count == 2

    def test_topics_fallback_from_exchange_entities(self):
        session = _make_session()
        session.key_topics = []
        session.add_exchange(
            query="q",
            response="r",
            entities=[{"normalized_name": "Metformin"}, {"text": "HbA1c"}],
        )
        topics = session.topics
        assert "metformin" in topics

    def test_topics_fallback_uses_text_when_no_normalized_name(self):
        session = _make_session()
        session.key_topics = []
        session.add_exchange(
            query="q",
            response="r",
            entities=[{"text": "aspirin"}],
        )
        assert "aspirin" in session.topics

    def test_topics_fallback_ignores_empty_entity_names(self):
        session = _make_session()
        session.key_topics = []
        session.add_exchange(query="q", response="r", entities=[{}])
        # Should not crash and should return empty list
        assert isinstance(session.topics, list)

    def test_to_dict_has_session_id(self):
        sid = str(uuid.uuid4())
        session = ConversationSession(session_id=sid)
        assert session.to_dict()["session_id"] == sid

    def test_to_dict_has_exchanges_list(self):
        session = _make_session()
        assert isinstance(session.to_dict()["exchanges"], list)

    def test_to_dict_exchanges_list_matches(self):
        session = _make_session()
        session.add_exchange(query="q1", response="r1")
        session.add_exchange(query="q2", response="r2")
        d = session.to_dict()
        assert len(d["exchanges"]) == 2

    def test_to_dict_has_summary_text(self):
        session = _make_session()
        assert "summary_text" in session.to_dict()

    def test_to_dict_has_key_topics(self):
        session = _make_session()
        assert "key_topics" in session.to_dict()

    def test_to_dict_has_key_entities(self):
        session = _make_session()
        assert "key_entities" in session.to_dict()

    def test_to_dict_has_created_at(self):
        session = _make_session()
        d = session.to_dict()
        assert "created_at" in d
        datetime.fromisoformat(d["created_at"])  # must be valid ISO string

    def test_to_dict_has_last_activity_at(self):
        session = _make_session()
        d = session.to_dict()
        assert "last_activity_at" in d
        datetime.fromisoformat(d["last_activity_at"])  # must be valid ISO string


# ---------------------------------------------------------------------------
# TestRAGConversationManager
# ---------------------------------------------------------------------------

class TestRAGConversationManager:
    """Tests for RAGConversationManager."""

    def test_init_with_no_args(self):
        mgr = RAGConversationManager()
        assert mgr is not None

    def test_init_with_all_none(self):
        mgr = RAGConversationManager(
            followup_detector=None,
            summarizer=None,
            entity_extractor=None,
            db_manager=None,
            embedding_manager=None,
        )
        assert mgr is not None

    def test_get_or_create_session_creates_new(self):
        mgr = RAGConversationManager()
        session = mgr._get_or_create_session("sess-001")
        assert isinstance(session, ConversationSession)
        assert session.session_id == "sess-001"

    def test_get_or_create_session_returns_same_instance(self):
        mgr = RAGConversationManager()
        s1 = mgr._get_or_create_session("sess-001")
        s2 = mgr._get_or_create_session("sess-001")
        assert s1 is s2

    def test_process_query_returns_four_tuple(self):
        mgr = RAGConversationManager()
        result = mgr.process_query("sess-1", "What is diabetes?")
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_process_query_enhanced_query_equals_original_when_no_prior_exchanges(self):
        mgr = RAGConversationManager()
        enhanced_query, is_followup, confidence, intent_type = mgr.process_query(
            "sess-x", "Tell me about metformin"
        )
        assert enhanced_query == "Tell me about metformin"

    def test_process_query_is_followup_false_with_no_detector(self):
        mgr = RAGConversationManager()
        _, is_followup, _, _ = mgr.process_query("sess-x", "Tell me about metformin")
        assert is_followup is False

    def test_process_query_confidence_zero_with_no_detector(self):
        mgr = RAGConversationManager()
        _, _, confidence, _ = mgr.process_query("sess-x", "query")
        assert confidence == 0.0

    def test_process_query_intent_type_new_topic_with_no_detector(self):
        mgr = RAGConversationManager()
        _, _, _, intent_type = mgr.process_query("sess-x", "query")
        assert intent_type == "new_topic"

    def test_process_query_with_embedding(self):
        mgr = RAGConversationManager()
        result = mgr.process_query("sess-emb", "query", query_embedding=[0.1, 0.2, 0.3])
        assert len(result) == 4

    def test_process_query_detector_none_no_crash_with_prior_exchanges(self):
        mgr = RAGConversationManager()
        # Build some prior context
        mgr._sessions["sess-y"] = ConversationSession(session_id="sess-y")
        mgr._sessions["sess-y"].add_exchange(query="prior", response="r")
        # Second query — detector is None so no follow-up detection
        enhanced, is_followup, conf, intent = mgr.process_query("sess-y", "follow up")
        assert is_followup is False

    def test_update_after_response_adds_exchange(self):
        mgr = RAGConversationManager()
        mgr.update_after_response(
            session_id="sess-u",
            query="What is aspirin?",
            response="Aspirin is a medication.",
        )
        session = mgr._get_or_create_session("sess-u")
        assert session.exchange_count == 1

    def test_update_after_response_stores_query(self):
        mgr = RAGConversationManager()
        mgr.update_after_response("sess-u2", "my query", "my response")
        session = mgr._get_or_create_session("sess-u2")
        assert session.last_query == "my query"

    def test_update_after_response_with_embedding(self):
        mgr = RAGConversationManager()
        emb = [0.1, 0.2, 0.3]
        mgr.update_after_response("sess-e", "q", "r", embedding=emb)
        session = mgr._get_or_create_session("sess-e")
        assert session.last_embedding == emb

    def test_update_after_response_with_is_followup_true(self):
        mgr = RAGConversationManager()
        mgr.update_after_response("sess-f", "q", "r", is_followup=True)
        session = mgr._get_or_create_session("sess-f")
        assert session.exchanges[-1].is_followup is True

    def test_update_after_response_with_ner_none_no_crash(self):
        mgr = RAGConversationManager(entity_extractor=None)
        mgr.update_after_response("sess-ner", "q", "r")
        session = mgr._get_or_create_session("sess-ner")
        assert session.exchange_count == 1

    def test_get_session_context_returns_dict(self):
        mgr = RAGConversationManager()
        ctx = mgr.get_session_context("sess-ctx")
        assert isinstance(ctx, dict)

    def test_get_session_context_has_session_id(self):
        mgr = RAGConversationManager()
        ctx = mgr.get_session_context("sess-ctx")
        assert ctx["session_id"] == "sess-ctx"

    def test_get_session_context_has_exchange_count(self):
        mgr = RAGConversationManager()
        ctx = mgr.get_session_context("sess-ctx")
        assert "exchange_count" in ctx

    def test_get_session_context_has_summary(self):
        mgr = RAGConversationManager()
        ctx = mgr.get_session_context("sess-ctx")
        assert "summary" in ctx

    def test_get_session_context_has_topics(self):
        mgr = RAGConversationManager()
        ctx = mgr.get_session_context("sess-ctx")
        assert "topics" in ctx

    def test_get_session_context_has_entities(self):
        mgr = RAGConversationManager()
        ctx = mgr.get_session_context("sess-ctx")
        assert "entities" in ctx

    def test_get_session_context_has_last_query(self):
        mgr = RAGConversationManager()
        ctx = mgr.get_session_context("sess-ctx")
        assert "last_query" in ctx

    def test_get_session_context_exchange_count_matches(self):
        mgr = RAGConversationManager()
        mgr.update_after_response("sess-cnt", "q1", "r1")
        mgr.update_after_response("sess-cnt", "q2", "r2")
        ctx = mgr.get_session_context("sess-cnt")
        assert ctx["exchange_count"] == 2

    def test_get_session_context_last_query_matches(self):
        mgr = RAGConversationManager()
        mgr.update_after_response("sess-lq", "first query", "r1")
        mgr.update_after_response("sess-lq", "second query", "r2")
        ctx = mgr.get_session_context("sess-lq")
        assert ctx["last_query"] == "second query"

    def test_clear_session_removes_from_memory(self):
        mgr = RAGConversationManager()
        mgr._get_or_create_session("sess-del")
        assert "sess-del" in mgr._sessions
        mgr.clear_session("sess-del")
        assert "sess-del" not in mgr._sessions

    def test_clear_session_nonexistent_no_crash(self):
        mgr = RAGConversationManager()
        mgr.clear_session("does-not-exist")  # must not raise

    def test_clear_session_with_db_none_no_crash(self):
        mgr = RAGConversationManager(db_manager=None)
        mgr._get_or_create_session("sess-db-del")
        mgr.clear_session("sess-db-del")
        assert "sess-db-del" not in mgr._sessions

    def test_eviction_when_over_max_sessions(self):
        mgr = RAGConversationManager()
        # Fill up MAX_SESSIONS + 1 sessions to trigger eviction
        for i in range(RAGConversationManager.MAX_SESSIONS + 1):
            mgr._get_or_create_session(f"sess-evict-{i}")
        # After eviction, count must be <= MAX_SESSIONS
        assert len(mgr._sessions) <= RAGConversationManager.MAX_SESSIONS

    def test_enhance_query_with_summary(self):
        mgr = RAGConversationManager()
        session = ConversationSession(session_id="enh-summ")
        session.summary_text = "Patient has type 2 diabetes."
        enhanced = mgr._enhance_query(session, "What medication is recommended?")
        assert "Patient has type 2 diabetes." in enhanced
        assert "What medication is recommended?" in enhanced

    def test_enhance_query_with_topics_when_no_summary(self):
        mgr = RAGConversationManager()
        session = ConversationSession(session_id="enh-topics")
        session.summary_text = ""
        session.key_topics = ["diabetes", "insulin"]
        enhanced = mgr._enhance_query(session, "What are the side effects?")
        assert "diabetes" in enhanced
        assert "What are the side effects?" in enhanced

    def test_enhance_query_returns_original_when_no_context(self):
        mgr = RAGConversationManager()
        session = ConversationSession(session_id="enh-empty")
        session.summary_text = ""
        session.key_topics = []
        original = "What is the dosage?"
        enhanced = mgr._enhance_query(session, original)
        assert enhanced == original

    def test_enhance_query_summary_takes_precedence_over_topics(self):
        mgr = RAGConversationManager()
        session = ConversationSession(session_id="enh-prio")
        session.summary_text = "Summary text here."
        session.key_topics = ["topic1", "topic2"]
        enhanced = mgr._enhance_query(session, "follow-up?")
        assert "Summary text here." in enhanced
        # Topics section should NOT appear when summary is present
        assert "Regarding:" not in enhanced

    def test_load_session_from_db_returns_none_when_no_db(self):
        mgr = RAGConversationManager(db_manager=None)
        result = mgr._load_session_from_db("any-session")
        assert result is None

    def test_persist_session_no_crash_when_no_db(self):
        mgr = RAGConversationManager(db_manager=None)
        mgr._get_or_create_session("persist-sess")
        mgr._persist_session("persist-sess")  # must not raise

    def test_persist_session_no_crash_for_missing_session(self):
        mgr = RAGConversationManager(db_manager=None)
        mgr._persist_session("nonexistent-session")  # must not raise


# ---------------------------------------------------------------------------
# TestGetConversationManager
# ---------------------------------------------------------------------------

class TestGetConversationManager:
    """Tests for the get_conversation_manager / reset_conversation_manager helpers."""

    def test_returns_rag_conversation_manager(self):
        mgr = get_conversation_manager()
        assert isinstance(mgr, RAGConversationManager)

    def test_singleton_same_instance(self):
        mgr1 = get_conversation_manager()
        mgr2 = get_conversation_manager()
        assert mgr1 is mgr2

    def test_reset_creates_fresh_instance(self):
        mgr1 = get_conversation_manager()
        reset_conversation_manager()
        mgr2 = get_conversation_manager()
        assert mgr1 is not mgr2

    def test_reset_clears_module_level_manager(self):
        get_conversation_manager()
        reset_conversation_manager()
        assert _cm_module._manager is None

    def test_get_after_reset_is_not_none(self):
        reset_conversation_manager()
        mgr = get_conversation_manager()
        assert mgr is not None

    def test_accepts_optional_deps_on_first_call(self):
        mock_detector = MagicMock()
        mgr = get_conversation_manager(followup_detector=mock_detector)
        assert isinstance(mgr, RAGConversationManager)

    def test_subsequent_call_ignores_new_deps(self):
        """Once created, a second call returns the existing instance unchanged."""
        mgr1 = get_conversation_manager()
        mock_detector = MagicMock()
        mgr2 = get_conversation_manager(followup_detector=mock_detector)
        assert mgr1 is mgr2

    def test_reset_conversation_manager_is_callable(self):
        assert callable(reset_conversation_manager)

    def test_get_conversation_manager_is_callable(self):
        assert callable(get_conversation_manager)
