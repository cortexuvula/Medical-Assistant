"""
RAG Feedback Manager.

Manages user feedback (upvote/downvote) and relevance score adjustments
for search results.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of user feedback."""
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    FLAG = "flag"


@dataclass
class RelevanceBoost:
    """Relevance boost calculated from feedback."""
    document_id: str
    chunk_index: int
    boost_factor: float  # -MAX_BOOST to +MAX_BOOST
    confidence: float    # 0.0-1.0 based on feedback count
    upvotes: int
    downvotes: int
    flags: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "boost_factor": self.boost_factor,
            "confidence": self.confidence,
            "upvotes": self.upvotes,
            "downvotes": self.downvotes,
            "flags": self.flags,
        }


@dataclass
class FeedbackRecord:
    """A single feedback record."""
    id: int
    document_id: str
    chunk_index: int
    feedback_type: FeedbackType
    feedback_reason: Optional[str]
    original_score: float
    query_text: str
    session_id: str
    created_at: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "feedback_type": self.feedback_type.value,
            "feedback_reason": self.feedback_reason,
            "original_score": self.original_score,
            "query_text": self.query_text,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
        }


class RAGFeedbackManager:
    """Manages user feedback and relevance adjustments."""

    # Configuration
    MAX_BOOST = 0.3           # Maximum boost factor (+/-)
    MIN_FEEDBACK_FOR_BOOST = 3  # Minimum feedback count for full confidence
    FLAG_PENALTY = 0.5        # Penalty multiplier for flagged content
    CONFIDENCE_DECAY = 0.9    # Decay factor for older feedback (per week)

    def __init__(self, db_manager=None):
        """Initialize the feedback manager.

        Args:
            db_manager: Database manager for persistence
        """
        self._db = db_manager
        self._boost_cache: dict[tuple[str, int], RelevanceBoost] = {}

    def record_feedback(
        self,
        document_id: str,
        chunk_index: int,
        feedback_type: FeedbackType,
        query_text: str,
        session_id: str,
        original_score: float,
        feedback_reason: Optional[str] = None,
    ) -> bool:
        """Record user feedback on a search result.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document
            feedback_type: Type of feedback (upvote/downvote/flag)
            query_text: The query that produced this result
            session_id: Session identifier
            original_score: Original relevance score
            feedback_reason: Optional reason for feedback

        Returns:
            True if feedback was recorded successfully
        """
        if not self._db:
            logger.warning("No database manager - feedback not persisted")
            return False

        try:
            # Insert feedback record
            self._db.execute(
                """INSERT INTO rag_result_feedback
                   (result_document_id, result_chunk_index, feedback_type,
                    feedback_reason, original_score, query_text, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    document_id,
                    chunk_index,
                    feedback_type.value,
                    feedback_reason,
                    original_score,
                    query_text,
                    session_id,
                )
            )

            # Update aggregates
            self._update_aggregates(document_id, chunk_index)

            # Invalidate cache for this chunk
            cache_key = (document_id, chunk_index)
            if cache_key in self._boost_cache:
                del self._boost_cache[cache_key]

            logger.info(
                f"Recorded {feedback_type.value} feedback for {document_id}:{chunk_index}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            return False

    def _update_aggregates(self, document_id: str, chunk_index: int):
        """Update aggregate feedback counts and boost factor.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document
        """
        try:
            # Count feedback by type
            row = self._db.fetchone(
                """SELECT
                     SUM(CASE WHEN feedback_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                     SUM(CASE WHEN feedback_type = 'downvote' THEN 1 ELSE 0 END) as downvotes,
                     SUM(CASE WHEN feedback_type = 'flag' THEN 1 ELSE 0 END) as flags
                   FROM rag_result_feedback
                   WHERE result_document_id = ? AND result_chunk_index = ?""",
                (document_id, chunk_index)
            )

            if not row:
                return

            upvotes = row[0] or 0
            downvotes = row[1] or 0
            flags = row[2] or 0

            # Calculate boost factor
            boost_factor = self._calculate_boost(upvotes, downvotes, flags)

            # Upsert aggregates
            self._db.execute(
                """INSERT INTO rag_feedback_aggregates
                   (document_id, chunk_index, upvote_count, downvote_count,
                    relevance_boost, last_calculated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(document_id, chunk_index) DO UPDATE SET
                     upvote_count = excluded.upvote_count,
                     downvote_count = excluded.downvote_count,
                     relevance_boost = excluded.relevance_boost,
                     last_calculated_at = excluded.last_calculated_at""",
                (document_id, chunk_index, upvotes, downvotes, boost_factor)
            )

        except Exception as e:
            logger.warning(f"Failed to update aggregates: {e}")

    def _calculate_boost(
        self,
        upvotes: int,
        downvotes: int,
        flags: int
    ) -> float:
        """Calculate relevance boost factor from feedback counts.

        Uses a Wilson score-like approach for confidence-weighted boosting.

        Args:
            upvotes: Number of upvotes
            downvotes: Number of downvotes
            flags: Number of flags

        Returns:
            Boost factor between -MAX_BOOST and +MAX_BOOST
        """
        total = upvotes + downvotes
        if total == 0:
            return 0.0

        # Apply flag penalty
        flag_penalty = 1.0 - (flags * self.FLAG_PENALTY / max(total, 1))
        flag_penalty = max(0.0, flag_penalty)

        # Calculate net score (-1 to +1)
        net_score = (upvotes - downvotes) / total

        # Apply confidence based on sample size
        # More feedback = higher confidence
        confidence = min(1.0, total / self.MIN_FEEDBACK_FOR_BOOST)

        # Calculate final boost
        boost = net_score * self.MAX_BOOST * confidence * flag_penalty

        # Clamp to bounds
        return max(-self.MAX_BOOST, min(self.MAX_BOOST, boost))

    def get_boost(
        self,
        document_id: str,
        chunk_index: int
    ) -> RelevanceBoost:
        """Get current relevance boost for a chunk.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document

        Returns:
            RelevanceBoost with current boost factor
        """
        cache_key = (document_id, chunk_index)

        # Check cache first
        if cache_key in self._boost_cache:
            return self._boost_cache[cache_key]

        # Default boost (no feedback)
        default_boost = RelevanceBoost(
            document_id=document_id,
            chunk_index=chunk_index,
            boost_factor=0.0,
            confidence=0.0,
            upvotes=0,
            downvotes=0,
            flags=0,
        )

        if not self._db:
            return default_boost

        try:
            # Query aggregates
            row = self._db.fetchone(
                """SELECT upvote_count, downvote_count, relevance_boost
                   FROM rag_feedback_aggregates
                   WHERE document_id = ? AND chunk_index = ?""",
                (document_id, chunk_index)
            )

            if not row:
                return default_boost

            upvotes = row[0] or 0
            downvotes = row[1] or 0
            boost_factor = row[2] or 0.0

            # Query flag count separately
            flag_row = self._db.fetchone(
                """SELECT COUNT(*) FROM rag_result_feedback
                   WHERE result_document_id = ? AND result_chunk_index = ?
                   AND feedback_type = 'flag'""",
                (document_id, chunk_index)
            )
            flags = flag_row[0] if flag_row else 0

            # Calculate confidence
            total = upvotes + downvotes
            confidence = min(1.0, total / self.MIN_FEEDBACK_FOR_BOOST) if total > 0 else 0.0

            boost = RelevanceBoost(
                document_id=document_id,
                chunk_index=chunk_index,
                boost_factor=boost_factor,
                confidence=confidence,
                upvotes=upvotes,
                downvotes=downvotes,
                flags=flags,
            )

            # Cache the result
            self._boost_cache[cache_key] = boost

            return boost

        except Exception as e:
            logger.warning(f"Failed to get boost: {e}")
            return default_boost

    def apply_boosts(self, results: list) -> list:
        """Apply feedback boosts to search results.

        Modifies the combined_score of each result based on feedback.

        Args:
            results: List of search results (must have document_id,
                    chunk_index, and combined_score attributes)

        Returns:
            Results sorted by adjusted combined_score
        """
        if not results:
            return results

        for result in results:
            # Get document_id and chunk_index from result
            doc_id = getattr(result, 'document_id', None)
            chunk_idx = getattr(result, 'chunk_index', 0)

            if doc_id is None:
                continue

            # Get boost for this chunk
            boost = self.get_boost(doc_id, chunk_idx)

            # Apply boost to score
            current_score = getattr(result, 'combined_score', 0.0)
            adjusted_score = current_score + (boost.boost_factor * boost.confidence)

            # Update the result's score
            if hasattr(result, 'combined_score'):
                result.combined_score = adjusted_score
            elif hasattr(result, '__setitem__'):
                result['combined_score'] = adjusted_score

            # Add boost info for transparency
            if hasattr(result, 'feedback_boost'):
                result.feedback_boost = boost.boost_factor
            elif hasattr(result, '__setitem__'):
                result['feedback_boost'] = boost.boost_factor

        # Sort by adjusted score
        return sorted(
            results,
            key=lambda x: getattr(x, 'combined_score', x.get('combined_score', 0) if isinstance(x, dict) else 0),
            reverse=True
        )

    def get_feedback_stats(
        self,
        document_id: Optional[str] = None
    ) -> dict:
        """Get feedback statistics.

        Args:
            document_id: Optional document to filter by

        Returns:
            Dictionary with feedback statistics
        """
        if not self._db:
            return {"total_feedback": 0, "upvotes": 0, "downvotes": 0, "flags": 0}

        try:
            if document_id:
                row = self._db.fetchone(
                    """SELECT
                         COUNT(*) as total,
                         SUM(CASE WHEN feedback_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                         SUM(CASE WHEN feedback_type = 'downvote' THEN 1 ELSE 0 END) as downvotes,
                         SUM(CASE WHEN feedback_type = 'flag' THEN 1 ELSE 0 END) as flags
                       FROM rag_result_feedback
                       WHERE result_document_id = ?""",
                    (document_id,)
                )
            else:
                row = self._db.fetchone(
                    """SELECT
                         COUNT(*) as total,
                         SUM(CASE WHEN feedback_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                         SUM(CASE WHEN feedback_type = 'downvote' THEN 1 ELSE 0 END) as downvotes,
                         SUM(CASE WHEN feedback_type = 'flag' THEN 1 ELSE 0 END) as flags
                       FROM rag_result_feedback"""
                )

            if row:
                return {
                    "total_feedback": row[0] or 0,
                    "upvotes": row[1] or 0,
                    "downvotes": row[2] or 0,
                    "flags": row[3] or 0,
                }

        except Exception as e:
            logger.warning(f"Failed to get feedback stats: {e}")

        return {"total_feedback": 0, "upvotes": 0, "downvotes": 0, "flags": 0}

    def clear_cache(self):
        """Clear the boost cache."""
        self._boost_cache.clear()

    def remove_feedback(
        self,
        document_id: str,
        chunk_index: int,
        session_id: str
    ) -> bool:
        """Remove feedback from a specific session.

        Useful for allowing users to change their feedback.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document
            session_id: Session that submitted the feedback

        Returns:
            True if feedback was removed
        """
        if not self._db:
            return False

        try:
            self._db.execute(
                """DELETE FROM rag_result_feedback
                   WHERE result_document_id = ? AND result_chunk_index = ?
                   AND session_id = ?""",
                (document_id, chunk_index, session_id)
            )

            # Update aggregates
            self._update_aggregates(document_id, chunk_index)

            # Invalidate cache
            cache_key = (document_id, chunk_index)
            if cache_key in self._boost_cache:
                del self._boost_cache[cache_key]

            return True

        except Exception as e:
            logger.warning(f"Failed to remove feedback: {e}")
            return False


# Singleton instance
_feedback_manager: Optional[RAGFeedbackManager] = None


def get_feedback_manager(db_manager=None) -> RAGFeedbackManager:
    """Get the global feedback manager instance.

    Args:
        db_manager: Database manager for persistence

    Returns:
        RAGFeedbackManager instance
    """
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = RAGFeedbackManager(db_manager)
    return _feedback_manager


def reset_feedback_manager():
    """Reset the global feedback manager instance."""
    global _feedback_manager
    _feedback_manager = None
