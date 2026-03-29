"""
Tests for src/rag/feedback_manager.py

Covers FeedbackType enum; RelevanceBoost.to_dict(); FeedbackRecord.to_dict();
RAGFeedbackManager constants, _calculate_boost() (pure math),
record_feedback() with no db, apply_boosts() (empty/sorted),
get_feedback_stats() with no db, clear_cache().
No network, no Tkinter, no file I/O, no real database.
"""

import sys
import pytest
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.feedback_manager import (
    FeedbackType, RelevanceBoost, FeedbackRecord, RAGFeedbackManager
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manager() -> RAGFeedbackManager:
    return RAGFeedbackManager(db_manager=None)


def _boost(doc_id="doc-1", chunk=0, boost=0.1, conf=0.8, up=3, down=1, flags=0) -> RelevanceBoost:
    return RelevanceBoost(
        document_id=doc_id, chunk_index=chunk,
        boost_factor=boost, confidence=conf,
        upvotes=up, downvotes=down, flags=flags
    )


def _record(feedback_type=FeedbackType.UPVOTE, reason=None) -> FeedbackRecord:
    return FeedbackRecord(
        id=1, document_id="doc-1", chunk_index=0,
        feedback_type=feedback_type, feedback_reason=reason,
        original_score=0.8, query_text="test query",
        session_id="session-abc", created_at=datetime(2026, 3, 28, 12, 0, 0)
    )


class _FakeResult:
    """Minimal result object for apply_boosts testing."""
    def __init__(self, doc_id, chunk, score):
        self.document_id = doc_id
        self.chunk_index = chunk
        self.combined_score = score
        self.feedback_boost = 0.0


# ===========================================================================
# FeedbackType enum
# ===========================================================================

class TestFeedbackType:
    def test_has_upvote(self):
        assert hasattr(FeedbackType, "UPVOTE")

    def test_has_downvote(self):
        assert hasattr(FeedbackType, "DOWNVOTE")

    def test_has_flag(self):
        assert hasattr(FeedbackType, "FLAG")

    def test_three_members(self):
        assert len(list(FeedbackType)) == 3

    def test_upvote_value(self):
        assert FeedbackType.UPVOTE == "upvote"

    def test_downvote_value(self):
        assert FeedbackType.DOWNVOTE == "downvote"

    def test_flag_value(self):
        assert FeedbackType.FLAG == "flag"

    def test_all_values_are_strings(self):
        for member in FeedbackType:
            assert isinstance(member.value, str)


# ===========================================================================
# RelevanceBoost.to_dict
# ===========================================================================

class TestRelevanceBoostToDict:
    def test_returns_dict(self):
        assert isinstance(_boost().to_dict(), dict)

    def test_document_id_present(self):
        d = _boost(doc_id="abc").to_dict()
        assert d["document_id"] == "abc"

    def test_chunk_index_present(self):
        d = _boost(chunk=3).to_dict()
        assert d["chunk_index"] == 3

    def test_boost_factor_present(self):
        d = _boost(boost=0.25).to_dict()
        assert d["boost_factor"] == pytest.approx(0.25)

    def test_confidence_present(self):
        d = _boost(conf=0.5).to_dict()
        assert d["confidence"] == pytest.approx(0.5)

    def test_upvotes_present(self):
        d = _boost(up=7).to_dict()
        assert d["upvotes"] == 7

    def test_downvotes_present(self):
        d = _boost(down=2).to_dict()
        assert d["downvotes"] == 2

    def test_flags_present(self):
        d = _boost(flags=1).to_dict()
        assert d["flags"] == 1

    def test_has_seven_keys(self):
        assert len(_boost().to_dict()) == 7


# ===========================================================================
# FeedbackRecord.to_dict
# ===========================================================================

class TestFeedbackRecordToDict:
    def test_returns_dict(self):
        assert isinstance(_record().to_dict(), dict)

    def test_id_present(self):
        assert _record().to_dict()["id"] == 1

    def test_document_id_present(self):
        assert _record().to_dict()["document_id"] == "doc-1"

    def test_chunk_index_present(self):
        assert _record().to_dict()["chunk_index"] == 0

    def test_feedback_type_is_value_string(self):
        d = _record(feedback_type=FeedbackType.DOWNVOTE).to_dict()
        assert d["feedback_type"] == "downvote"

    def test_feedback_reason_none(self):
        assert _record().to_dict()["feedback_reason"] is None

    def test_feedback_reason_set(self):
        d = _record(reason="not relevant").to_dict()
        assert d["feedback_reason"] == "not relevant"

    def test_original_score_present(self):
        assert _record().to_dict()["original_score"] == pytest.approx(0.8)

    def test_query_text_present(self):
        assert _record().to_dict()["query_text"] == "test query"

    def test_session_id_present(self):
        assert _record().to_dict()["session_id"] == "session-abc"

    def test_created_at_is_isoformat_string(self):
        d = _record().to_dict()
        assert isinstance(d["created_at"], str)
        assert "2026" in d["created_at"]


# ===========================================================================
# RAGFeedbackManager constants
# ===========================================================================

class TestManagerConstants:
    def test_max_boost_positive(self):
        assert RAGFeedbackManager.MAX_BOOST > 0

    def test_min_feedback_for_boost_positive(self):
        assert RAGFeedbackManager.MIN_FEEDBACK_FOR_BOOST > 0

    def test_flag_penalty_between_0_and_1(self):
        assert 0 < RAGFeedbackManager.FLAG_PENALTY <= 1

    def test_confidence_decay_between_0_and_1(self):
        assert 0 < RAGFeedbackManager.CONFIDENCE_DECAY <= 1

    def test_max_boost_is_03(self):
        assert RAGFeedbackManager.MAX_BOOST == pytest.approx(0.3)


# ===========================================================================
# _calculate_boost (pure math)
# ===========================================================================

class TestCalculateBoost:
    def setup_method(self):
        self.mgr = _manager()
        self.MAX = RAGFeedbackManager.MAX_BOOST

    def test_all_zero_returns_zero(self):
        assert self.mgr._calculate_boost(0, 0, 0) == pytest.approx(0.0)

    def test_all_upvotes_returns_max_boost(self):
        # Enough upvotes for full confidence, no downvotes, no flags
        result = self.mgr._calculate_boost(10, 0, 0)
        assert result == pytest.approx(self.MAX)

    def test_all_downvotes_returns_negative_max_boost(self):
        result = self.mgr._calculate_boost(0, 10, 0)
        assert result == pytest.approx(-self.MAX)

    def test_equal_upvotes_downvotes_near_zero(self):
        result = self.mgr._calculate_boost(5, 5, 0)
        assert result == pytest.approx(0.0)

    def test_result_within_bounds(self):
        result = self.mgr._calculate_boost(7, 3, 2)
        assert -self.MAX <= result <= self.MAX

    def test_flags_reduce_boost(self):
        no_flags = self.mgr._calculate_boost(5, 0, 0)
        with_flags = self.mgr._calculate_boost(5, 0, 5)
        assert with_flags <= no_flags

    def test_low_count_lower_confidence(self):
        # 1 upvote has less confidence than 10 upvotes
        low = self.mgr._calculate_boost(1, 0, 0)
        high = self.mgr._calculate_boost(10, 0, 0)
        assert low < high

    def test_returns_float(self):
        assert isinstance(self.mgr._calculate_boost(3, 1, 0), float)


# ===========================================================================
# record_feedback with no db
# ===========================================================================

class TestRecordFeedbackNoDb:
    def test_returns_false_without_db(self):
        mgr = _manager()
        result = mgr.record_feedback(
            document_id="doc-1",
            chunk_index=0,
            feedback_type=FeedbackType.UPVOTE,
            query_text="test",
            session_id="session-1",
            original_score=0.8,
        )
        assert result is False

    def test_no_exception_without_db(self):
        mgr = _manager()
        try:
            mgr.record_feedback("doc", 0, FeedbackType.DOWNVOTE, "q", "s", 0.5)
        except Exception as exc:
            pytest.fail(f"Unexpected exception: {exc}")


# ===========================================================================
# apply_boosts
# ===========================================================================

class TestApplyBoosts:
    def setup_method(self):
        self.mgr = _manager()

    def test_empty_list_returns_empty(self):
        assert self.mgr.apply_boosts([]) == []

    def test_returns_list(self):
        r = _FakeResult("d", 0, 0.5)
        result = self.mgr.apply_boosts([r])
        assert isinstance(result, list)

    def test_sorted_by_combined_score_desc(self):
        r1 = _FakeResult("d", 0, 0.5)
        r2 = _FakeResult("d", 1, 0.9)
        r3 = _FakeResult("d", 2, 0.7)
        sorted_results = self.mgr.apply_boosts([r1, r2, r3])
        scores = [r.combined_score for r in sorted_results]
        assert scores == sorted(scores, reverse=True)

    def test_single_result_returned(self):
        r = _FakeResult("d", 0, 0.8)
        result = self.mgr.apply_boosts([r])
        assert len(result) == 1

    def test_all_results_returned(self):
        results = [_FakeResult("d", i, float(i) / 10) for i in range(5)]
        out = self.mgr.apply_boosts(results)
        assert len(out) == 5


# ===========================================================================
# get_feedback_stats with no db
# ===========================================================================

class TestGetFeedbackStatsNoDb:
    def setup_method(self):
        self.mgr = _manager()

    def test_returns_dict(self):
        assert isinstance(self.mgr.get_feedback_stats(), dict)

    def test_total_feedback_zero(self):
        assert self.mgr.get_feedback_stats()["total_feedback"] == 0

    def test_upvotes_zero(self):
        assert self.mgr.get_feedback_stats()["upvotes"] == 0

    def test_downvotes_zero(self):
        assert self.mgr.get_feedback_stats()["downvotes"] == 0

    def test_flags_zero(self):
        assert self.mgr.get_feedback_stats()["flags"] == 0

    def test_with_document_id_filter_no_db(self):
        result = self.mgr.get_feedback_stats(document_id="doc-1")
        assert result["total_feedback"] == 0


# ===========================================================================
# clear_cache
# ===========================================================================

class TestClearCache:
    def test_clear_cache_no_error(self):
        mgr = _manager()
        mgr.clear_cache()  # Should not raise

    def test_clear_cache_empties_boost_cache(self):
        mgr = _manager()
        mgr._boost_cache[("doc-1", 0)] = _boost()
        mgr.clear_cache()
        assert len(mgr._boost_cache) == 0

    def test_clear_empty_cache_no_error(self):
        mgr = _manager()
        mgr.clear_cache()
        mgr.clear_cache()  # Double-clear is safe
