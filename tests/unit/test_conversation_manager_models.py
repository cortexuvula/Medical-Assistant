"""
Tests for ConversationExchange and ConversationSession dataclasses
in src/rag/conversation_manager.py

Covers ConversationExchange (fields, defaults, to_dict),
ConversationSession (fields, defaults, exchange_count, last_query,
last_embedding, topics, add_exchange, compress_exchanges, to_dict).
No network, no Tkinter, no database.
"""

import sys
import pytest
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.conversation_manager import ConversationExchange, ConversationSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exchange(index=0, query="test query", response="test response",
              embedding=None, is_followup=False) -> ConversationExchange:
    return ConversationExchange(
        exchange_index=index,
        query_text=query,
        response_summary=response,
        query_embedding=embedding,
        is_followup=is_followup,
    )


def _session(session_id="test-session") -> ConversationSession:
    return ConversationSession(session_id=session_id)


# ===========================================================================
# ConversationExchange — fields and defaults
# ===========================================================================

class TestConversationExchangeFields:
    def test_exchange_index_stored(self):
        e = ConversationExchange(exchange_index=3, query_text="q")
        assert e.exchange_index == 3

    def test_query_text_stored(self):
        e = ConversationExchange(exchange_index=0, query_text="what is diabetes?")
        assert e.query_text == "what is diabetes?"

    def test_default_response_summary_empty(self):
        e = ConversationExchange(exchange_index=0, query_text="q")
        assert e.response_summary == ""

    def test_default_query_embedding_none(self):
        e = ConversationExchange(exchange_index=0, query_text="q")
        assert e.query_embedding is None

    def test_default_extracted_entities_empty_list(self):
        e = ConversationExchange(exchange_index=0, query_text="q")
        assert e.extracted_entities == []

    def test_default_is_followup_false(self):
        e = ConversationExchange(exchange_index=0, query_text="q")
        assert e.is_followup is False

    def test_default_followup_confidence_zero(self):
        e = ConversationExchange(exchange_index=0, query_text="q")
        assert e.followup_confidence == pytest.approx(0.0)

    def test_default_intent_type_new_topic(self):
        e = ConversationExchange(exchange_index=0, query_text="q")
        assert e.intent_type == "new_topic"

    def test_created_at_is_datetime(self):
        e = ConversationExchange(exchange_index=0, query_text="q")
        assert isinstance(e.created_at, datetime)

    def test_instances_dont_share_entities(self):
        e1 = ConversationExchange(exchange_index=0, query_text="q")
        e2 = ConversationExchange(exchange_index=1, query_text="q")
        e1.extracted_entities.append({"text": "diabetes"})
        assert e2.extracted_entities == []


# ===========================================================================
# ConversationExchange — to_dict
# ===========================================================================

class TestConversationExchangeToDict:
    def test_returns_dict(self):
        e = _exchange()
        assert isinstance(e.to_dict(), dict)

    def test_has_all_keys(self):
        d = _exchange().to_dict()
        for key in ["exchange_index", "query_text", "response_summary",
                    "extracted_entities", "is_followup", "followup_confidence",
                    "intent_type", "created_at"]:
            assert key in d

    def test_values_match(self):
        e = ConversationExchange(
            exchange_index=2, query_text="q", response_summary="r",
            is_followup=True, followup_confidence=0.8, intent_type="followup"
        )
        d = e.to_dict()
        assert d["exchange_index"] == 2
        assert d["query_text"] == "q"
        assert d["response_summary"] == "r"
        assert d["is_followup"] is True
        assert d["followup_confidence"] == pytest.approx(0.8)
        assert d["intent_type"] == "followup"

    def test_created_at_is_iso_string(self):
        d = _exchange().to_dict()
        # Should be parseable
        datetime.fromisoformat(d["created_at"])

    def test_embedding_not_included(self):
        e = ConversationExchange(exchange_index=0, query_text="q",
                                  query_embedding=[0.1, 0.2, 0.3])
        d = e.to_dict()
        assert "query_embedding" not in d


# ===========================================================================
# ConversationSession — fields and defaults
# ===========================================================================

class TestConversationSessionFields:
    def test_session_id_stored(self):
        s = ConversationSession(session_id="my-session")
        assert s.session_id == "my-session"

    def test_default_exchanges_empty(self):
        s = _session()
        assert s.exchanges == []

    def test_default_summary_text_empty(self):
        s = _session()
        assert s.summary_text == ""

    def test_default_key_topics_empty(self):
        s = _session()
        assert s.key_topics == []

    def test_default_key_entities_empty(self):
        s = _session()
        assert s.key_entities == []

    def test_created_at_is_datetime(self):
        s = _session()
        assert isinstance(s.created_at, datetime)

    def test_last_activity_at_is_datetime(self):
        s = _session()
        assert isinstance(s.last_activity_at, datetime)

    def test_instances_dont_share_exchanges(self):
        s1 = _session("s1")
        s2 = _session("s2")
        s1.exchanges.append(_exchange())
        assert s2.exchanges == []


# ===========================================================================
# ConversationSession — exchange_count property
# ===========================================================================

class TestConversationSessionExchangeCount:
    def test_empty_session_count_zero(self):
        assert _session().exchange_count == 0

    def test_one_exchange_count_one(self):
        s = _session()
        s.exchanges.append(_exchange())
        assert s.exchange_count == 1

    def test_multiple_exchanges_counted(self):
        s = _session()
        for i in range(5):
            s.exchanges.append(_exchange(i))
        assert s.exchange_count == 5


# ===========================================================================
# ConversationSession — last_query property
# ===========================================================================

class TestConversationSessionLastQuery:
    def test_empty_session_returns_none(self):
        assert _session().last_query is None

    def test_single_exchange_returns_its_query(self):
        s = _session()
        s.exchanges.append(_exchange(query="first question"))
        assert s.last_query == "first question"

    def test_multiple_exchanges_returns_last(self):
        s = _session()
        s.exchanges.append(_exchange(0, "first"))
        s.exchanges.append(_exchange(1, "second"))
        s.exchanges.append(_exchange(2, "third"))
        assert s.last_query == "third"


# ===========================================================================
# ConversationSession — last_embedding property
# ===========================================================================

class TestConversationSessionLastEmbedding:
    def test_empty_session_returns_none(self):
        assert _session().last_embedding is None

    def test_exchange_with_embedding(self):
        s = _session()
        s.exchanges.append(_exchange(embedding=[0.1, 0.2]))
        assert s.last_embedding == [0.1, 0.2]

    def test_exchange_without_embedding(self):
        s = _session()
        s.exchanges.append(_exchange(embedding=None))
        assert s.last_embedding is None

    def test_returns_last_exchange_embedding(self):
        s = _session()
        s.exchanges.append(_exchange(0, embedding=[1.0]))
        s.exchanges.append(_exchange(1, embedding=[2.0]))
        assert s.last_embedding == [2.0]


# ===========================================================================
# ConversationSession — topics property
# ===========================================================================

class TestConversationSessionTopics:
    def test_empty_session_returns_empty_list(self):
        assert _session().topics == []

    def test_returns_key_topics_if_set(self):
        s = _session()
        s.key_topics = ["diabetes", "hypertension"]
        topics = s.topics
        assert "diabetes" in topics
        assert "hypertension" in topics

    def test_falls_back_to_entities_when_no_key_topics(self):
        s = _session()
        e = _exchange()
        e.extracted_entities = [{"text": "diabetes", "entity_type": "condition"}]
        s.exchanges.append(e)
        topics = s.topics
        assert "diabetes" in topics

    def test_normalized_name_preferred(self):
        s = _session()
        e = _exchange()
        e.extracted_entities = [{"text": "asa", "normalized_name": "aspirin"}]
        s.exchanges.append(e)
        topics = s.topics
        assert "aspirin" in topics

    def test_topics_are_lowercase(self):
        s = _session()
        e = _exchange()
        e.extracted_entities = [{"text": "Diabetes", "entity_type": "condition"}]
        s.exchanges.append(e)
        for topic in s.topics:
            assert topic == topic.lower()


# ===========================================================================
# ConversationSession — add_exchange
# ===========================================================================

class TestConversationSessionAddExchange:
    def test_adds_to_exchanges_list(self):
        s = _session()
        s.add_exchange("question", "answer")
        assert s.exchange_count == 1

    def test_exchange_has_correct_query(self):
        s = _session()
        s.add_exchange("my question", "my answer")
        assert s.exchanges[0].query_text == "my question"

    def test_response_truncated_to_200_chars(self):
        s = _session()
        long_response = "x" * 300
        s.add_exchange("q", long_response)
        assert len(s.exchanges[0].response_summary) <= 200

    def test_short_response_not_truncated(self):
        s = _session()
        s.add_exchange("q", "short answer")
        assert s.exchanges[0].response_summary == "short answer"

    def test_exchange_index_increments(self):
        s = _session()
        s.add_exchange("q1", "a1")
        s.add_exchange("q2", "a2")
        assert s.exchanges[0].exchange_index == 0
        assert s.exchanges[1].exchange_index == 1

    def test_embedding_stored(self):
        s = _session()
        s.add_exchange("q", "a", embedding=[0.1, 0.2])
        assert s.exchanges[0].query_embedding == [0.1, 0.2]

    def test_entities_stored(self):
        s = _session()
        entities = [{"text": "diabetes"}]
        s.add_exchange("q", "a", entities=entities)
        assert s.exchanges[0].extracted_entities == entities

    def test_is_followup_stored(self):
        s = _session()
        s.add_exchange("q", "a", is_followup=True, followup_confidence=0.9)
        assert s.exchanges[0].is_followup is True
        assert s.exchanges[0].followup_confidence == pytest.approx(0.9)

    def test_intent_type_stored(self):
        s = _session()
        s.add_exchange("q", "a", intent_type="followup")
        assert s.exchanges[0].intent_type == "followup"

    def test_last_activity_updated(self):
        s = _session()
        before = s.last_activity_at
        s.add_exchange("q", "a")
        assert s.last_activity_at >= before


# ===========================================================================
# ConversationSession — compress_exchanges
# ===========================================================================

class TestConversationSessionCompress:
    def test_no_op_when_at_or_below_keep_recent(self):
        s = _session()
        s.add_exchange("q1", "a1")
        s.add_exchange("q2", "a2")
        s.compress_exchanges(keep_recent=2)
        assert s.exchange_count == 2

    def test_keeps_only_recent(self):
        s = _session()
        for i in range(5):
            s.add_exchange(f"q{i}", f"a{i}")
        s.compress_exchanges(keep_recent=2)
        assert s.exchange_count == 2

    def test_keeps_most_recent_queries(self):
        s = _session()
        for i in range(5):
            s.add_exchange(f"query {i}", f"answer {i}")
        s.compress_exchanges(keep_recent=2)
        assert s.exchanges[-1].query_text == "query 4"
        assert s.exchanges[-2].query_text == "query 3"

    def test_re_indexes_after_compress(self):
        s = _session()
        for i in range(5):
            s.add_exchange(f"q{i}", f"a{i}")
        s.compress_exchanges(keep_recent=2)
        for i, exchange in enumerate(s.exchanges):
            assert exchange.exchange_index == i

    def test_empty_session_compress_no_error(self):
        s = _session()
        s.compress_exchanges(keep_recent=3)  # Should not raise
        assert s.exchange_count == 0


# ===========================================================================
# ConversationSession — to_dict
# ===========================================================================

class TestConversationSessionToDict:
    def test_returns_dict(self):
        s = _session()
        assert isinstance(s.to_dict(), dict)

    def test_has_all_keys(self):
        d = _session().to_dict()
        for key in ["session_id", "exchanges", "summary_text", "key_topics",
                    "key_entities", "created_at", "last_activity_at"]:
            assert key in d

    def test_session_id_matches(self):
        s = ConversationSession(session_id="my-session-123")
        assert s.to_dict()["session_id"] == "my-session-123"

    def test_exchanges_serialized_as_list(self):
        s = _session()
        s.add_exchange("q", "a")
        d = s.to_dict()
        assert isinstance(d["exchanges"], list)
        assert len(d["exchanges"]) == 1

    def test_created_at_is_iso_string(self):
        d = _session().to_dict()
        datetime.fromisoformat(d["created_at"])

    def test_last_activity_at_is_iso_string(self):
        d = _session().to_dict()
        datetime.fromisoformat(d["last_activity_at"])

    def test_key_topics_serialized(self):
        s = _session()
        s.key_topics = ["diabetes", "hypertension"]
        d = s.to_dict()
        assert d["key_topics"] == ["diabetes", "hypertension"]
