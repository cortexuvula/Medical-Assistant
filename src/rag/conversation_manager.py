"""
RAG Conversation Manager.

Manages conversation state with persistence, follow-up detection,
summarization, and entity extraction integration.
"""

import json
from utils.structured_logging import get_logger
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = get_logger(__name__)


@dataclass
class ConversationExchange:
    """A single exchange in a conversation."""
    exchange_index: int
    query_text: str
    response_summary: str = ""
    query_embedding: Optional[list[float]] = None
    extracted_entities: list[dict] = field(default_factory=list)
    is_followup: bool = False
    followup_confidence: float = 0.0
    intent_type: str = "new_topic"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "exchange_index": self.exchange_index,
            "query_text": self.query_text,
            "response_summary": self.response_summary,
            "extracted_entities": self.extracted_entities,
            "is_followup": self.is_followup,
            "followup_confidence": self.followup_confidence,
            "intent_type": self.intent_type,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ConversationSession:
    """A conversation session with multiple exchanges."""
    session_id: str
    exchanges: list[ConversationExchange] = field(default_factory=list)
    summary_text: str = ""
    key_topics: list[str] = field(default_factory=list)
    key_entities: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity_at: datetime = field(default_factory=datetime.now)

    @property
    def exchange_count(self) -> int:
        """Get the number of exchanges."""
        return len(self.exchanges)

    @property
    def last_query(self) -> Optional[str]:
        """Get the last query text."""
        if self.exchanges:
            return self.exchanges[-1].query_text
        return None

    @property
    def last_embedding(self) -> Optional[list[float]]:
        """Get the last query embedding."""
        if self.exchanges:
            return self.exchanges[-1].query_embedding
        return None

    @property
    def topics(self) -> list[str]:
        """Get key topics (from summary or recent exchanges)."""
        if self.key_topics:
            return self.key_topics
        # Fallback: extract from recent exchanges
        topics = set()
        for exchange in self.exchanges[-3:]:
            for entity in exchange.extracted_entities:
                normalized = entity.get('normalized_name') or entity.get('text', '')
                if normalized:
                    topics.add(normalized.lower())
        return list(topics)

    def add_exchange(
        self,
        query: str,
        response: str,
        embedding: Optional[list[float]] = None,
        entities: Optional[list[dict]] = None,
        is_followup: bool = False,
        followup_confidence: float = 0.0,
        intent_type: str = "new_topic"
    ):
        """Add a new exchange to the session."""
        exchange = ConversationExchange(
            exchange_index=len(self.exchanges),
            query_text=query,
            response_summary=response[:200] if response else "",  # Store summary only
            query_embedding=embedding,
            extracted_entities=entities or [],
            is_followup=is_followup,
            followup_confidence=followup_confidence,
            intent_type=intent_type,
        )
        self.exchanges.append(exchange)
        self.last_activity_at = datetime.now()

    def compress_exchanges(self, keep_recent: int = 2):
        """Compress older exchanges, keeping only recent ones.

        Args:
            keep_recent: Number of recent exchanges to keep in full
        """
        if len(self.exchanges) <= keep_recent:
            return

        # Keep only the most recent exchanges
        self.exchanges = self.exchanges[-keep_recent:]

        # Re-index
        for i, exchange in enumerate(self.exchanges):
            exchange.exchange_index = i

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "exchanges": [e.to_dict() for e in self.exchanges],
            "summary_text": self.summary_text,
            "key_topics": self.key_topics,
            "key_entities": self.key_entities,
            "created_at": self.created_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
        }


class RAGConversationManager:
    """Manages conversation state with persistence."""

    MAX_SESSIONS = 100  # Maximum sessions to keep in memory
    MAX_EXCHANGES_BEFORE_SUMMARIZE = 5

    def __init__(
        self,
        followup_detector=None,
        summarizer=None,
        entity_extractor=None,
        db_manager=None,
        embedding_manager=None
    ):
        """Initialize the conversation manager.

        Args:
            followup_detector: SemanticFollowupDetector instance
            summarizer: MedicalConversationSummarizer instance
            entity_extractor: MedicalNERExtractor instance
            db_manager: Database manager for persistence
            embedding_manager: Embedding manager for query embeddings
        """
        self._detector = followup_detector
        self._summarizer = summarizer
        self._ner = entity_extractor
        self._db = db_manager
        self._embedding_manager = embedding_manager
        self._sessions: dict[str, ConversationSession] = {}

    def _get_or_create_session(self, session_id: str) -> ConversationSession:
        """Get existing session or create new one.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession instance
        """
        if session_id not in self._sessions:
            # Try to load from database
            session = self._load_session_from_db(session_id)
            if session is None:
                session = ConversationSession(session_id=session_id)
            self._sessions[session_id] = session

            # Evict old sessions if too many
            self._evict_old_sessions()

        return self._sessions[session_id]

    def _evict_old_sessions(self):
        """Evict oldest sessions if we have too many."""
        if len(self._sessions) > self.MAX_SESSIONS:
            # Sort by last activity and remove oldest
            sorted_sessions = sorted(
                self._sessions.items(),
                key=lambda x: x[1].last_activity_at
            )
            sessions_to_remove = len(self._sessions) - self.MAX_SESSIONS + 10
            for session_id, _ in sorted_sessions[:sessions_to_remove]:
                del self._sessions[session_id]

    def _load_session_from_db(self, session_id: str) -> Optional[ConversationSession]:
        """Load session from database.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession if found, None otherwise
        """
        if not self._db:
            return None

        try:
            # Load session record
            row = self._db.fetchone(
                """SELECT session_id, summary_text, key_topics_json, key_entities_json,
                          created_at, last_activity_at
                   FROM rag_conversation_sessions WHERE session_id = ?""",
                (session_id,)
            )

            if not row:
                return None

            session = ConversationSession(
                session_id=row[0],
                summary_text=row[1] or "",
                key_topics=json.loads(row[2]) if row[2] else [],
                key_entities=json.loads(row[3]) if row[3] else [],
            )

            # Load exchanges
            exchange_rows = self._db.fetchall(
                """SELECT exchange_index, query_text, response_summary,
                          extracted_entities_json, is_followup, followup_confidence,
                          intent_type, created_at
                   FROM rag_conversation_exchanges
                   WHERE session_id = ?
                   ORDER BY exchange_index""",
                (session_id,)
            )

            for erow in exchange_rows:
                exchange = ConversationExchange(
                    exchange_index=erow[0],
                    query_text=erow[1],
                    response_summary=erow[2] or "",
                    extracted_entities=json.loads(erow[3]) if erow[3] else [],
                    is_followup=bool(erow[4]),
                    followup_confidence=erow[5] or 0.0,
                    intent_type=erow[6] or "new_topic",
                )
                session.exchanges.append(exchange)

            return session

        except Exception as e:
            logger.warning(f"Failed to load session from database: {e}")
            return None

    def _persist_session(self, session_id: str):
        """Persist session to database.

        Args:
            session_id: Session identifier
        """
        if not self._db:
            return

        session = self._sessions.get(session_id)
        if not session:
            return

        try:
            # Upsert session record
            self._db.execute(
                """INSERT INTO rag_conversation_sessions
                   (session_id, exchange_count, summary_text, key_topics_json,
                    key_entities_json, last_activity_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     exchange_count = excluded.exchange_count,
                     summary_text = excluded.summary_text,
                     key_topics_json = excluded.key_topics_json,
                     key_entities_json = excluded.key_entities_json,
                     last_activity_at = excluded.last_activity_at""",
                (
                    session_id,
                    session.exchange_count,
                    session.summary_text,
                    json.dumps(session.key_topics),
                    json.dumps(session.key_entities),
                    session.last_activity_at.isoformat(),
                )
            )

            # Insert/update latest exchange
            if session.exchanges:
                latest = session.exchanges[-1]
                self._db.execute(
                    """INSERT INTO rag_conversation_exchanges
                       (session_id, exchange_index, query_text, response_summary,
                        extracted_entities_json, is_followup, followup_confidence,
                        intent_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(session_id, exchange_index) DO UPDATE SET
                         query_text = excluded.query_text,
                         response_summary = excluded.response_summary,
                         extracted_entities_json = excluded.extracted_entities_json,
                         is_followup = excluded.is_followup,
                         followup_confidence = excluded.followup_confidence,
                         intent_type = excluded.intent_type""",
                    (
                        session_id,
                        latest.exchange_index,
                        latest.query_text,
                        latest.response_summary,
                        json.dumps(latest.extracted_entities),
                        latest.is_followup,
                        latest.followup_confidence,
                        latest.intent_type,
                    )
                )

        except Exception as e:
            logger.warning(f"Failed to persist session: {e}")

    def process_query(
        self,
        session_id: str,
        query: str,
        query_embedding: Optional[list[float]] = None,
    ) -> tuple[str, bool, float, str]:
        """Process query with context.

        Args:
            session_id: Session identifier
            query: User's query
            query_embedding: Optional embedding of the query

        Returns:
            Tuple of (enhanced_query, is_followup, confidence, intent_type)
        """
        session = self._get_or_create_session(session_id)

        # Detect follow-up
        is_followup = False
        confidence = 0.0
        intent_type = "new_topic"

        if self._detector and session.exchanges:
            result = self._detector.detect(
                current_query=query,
                previous_query=session.last_query,
                previous_topics=session.topics,
                current_embedding=query_embedding,
                previous_embedding=session.last_embedding,
            )
            is_followup = result.is_followup
            confidence = result.confidence
            intent_type = result.intent.value

            logger.debug(
                f"Follow-up detection: is_followup={is_followup}, "
                f"confidence={confidence:.2f}, intent={intent_type}"
            )

        # Enhance query if follow-up
        enhanced_query = query
        if is_followup:
            enhanced_query = self._enhance_query(session, query)

        return enhanced_query, is_followup, confidence, intent_type

    def _enhance_query(self, session: ConversationSession, query: str) -> str:
        """Enhance a follow-up query with context.

        Args:
            session: Current conversation session
            query: Original query

        Returns:
            Enhanced query with context
        """
        context_parts = []

        # Add summary if available
        if session.summary_text:
            context_parts.append(f"Context: {session.summary_text}")
        # Otherwise, add recent topics
        elif session.topics:
            topic_str = ", ".join(session.topics[:5])
            context_parts.append(f"Regarding: {topic_str}")

        # Add the query
        if context_parts:
            enhanced = f"{' '.join(context_parts)}\n\nQuestion: {query}"
            logger.info(f"Enhanced query with context (original: {len(query)} chars, enhanced: {len(enhanced)} chars)")
            return enhanced

        return query

    def update_after_response(
        self,
        session_id: str,
        query: str,
        response: str,
        embedding: Optional[list[float]] = None,
        is_followup: bool = False,
        followup_confidence: float = 0.0,
        intent_type: str = "new_topic"
    ):
        """Update session after response.

        Args:
            session_id: Session identifier
            query: User's query
            response: System's response
            embedding: Optional query embedding
            is_followup: Whether this was detected as follow-up
            followup_confidence: Confidence of follow-up detection
            intent_type: Intent classification
        """
        session = self._get_or_create_session(session_id)

        # Extract entities from query
        entities = []
        if self._ner:
            try:
                extracted = self._ner.extract(query)
                entities = [e.to_dict() for e in extracted]
            except Exception as e:
                logger.warning(f"Entity extraction failed: {e}")

        # Add exchange to session
        session.add_exchange(
            query=query,
            response=response,
            embedding=embedding,
            entities=entities,
            is_followup=is_followup,
            followup_confidence=followup_confidence,
            intent_type=intent_type,
        )

        # Check if summarization is needed
        if self._summarizer and self._summarizer.should_summarize(session.exchange_count):
            self._summarize_session(session)

        # Persist to database
        self._persist_session(session_id)

    def _summarize_session(self, session: ConversationSession):
        """Summarize and compress a session.

        Args:
            session: Session to summarize
        """
        try:
            # Prepare exchanges for summarization
            exchanges = [
                (e.query_text, e.response_summary)
                for e in session.exchanges
            ]

            # Get existing summary if any
            from rag.conversation_summarizer import ConversationSummary
            existing_summary = None
            if session.summary_text:
                existing_summary = ConversationSummary(
                    summary_text=session.summary_text,
                    key_topics=session.key_topics,
                    key_entities=session.key_entities,
                    exchange_count=len(exchanges),
                    token_count=0,
                )

            # Generate new summary
            summary = self._summarizer.summarize(exchanges, existing_summary)

            # Update session
            session.summary_text = summary.summary_text
            session.key_topics = summary.key_topics
            session.key_entities = summary.key_entities

            # Compress exchanges
            session.compress_exchanges(keep_recent=2)

            logger.info(
                f"Session {session.session_id} summarized: "
                f"{summary.exchange_count} exchanges -> {len(session.exchanges)} kept"
            )

        except Exception as e:
            logger.warning(f"Session summarization failed: {e}")

    def get_session_context(self, session_id: str) -> dict:
        """Get context for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session context
        """
        session = self._get_or_create_session(session_id)

        return {
            "session_id": session_id,
            "exchange_count": session.exchange_count,
            "summary": session.summary_text,
            "topics": session.topics,
            "entities": session.key_entities,
            "last_query": session.last_query,
        }

    def clear_session(self, session_id: str):
        """Clear a session.

        Args:
            session_id: Session identifier
        """
        if session_id in self._sessions:
            del self._sessions[session_id]

        if self._db:
            try:
                self._db.execute(
                    "DELETE FROM rag_conversation_exchanges WHERE session_id = ?",
                    (session_id,)
                )
                self._db.execute(
                    "DELETE FROM rag_conversation_sessions WHERE session_id = ?",
                    (session_id,)
                )
            except Exception as e:
                logger.warning(f"Failed to clear session from database: {e}")


# Singleton instance
_manager: Optional[RAGConversationManager] = None


def get_conversation_manager(
    followup_detector=None,
    summarizer=None,
    entity_extractor=None,
    db_manager=None,
    embedding_manager=None
) -> RAGConversationManager:
    """Get the global conversation manager instance.

    Args:
        followup_detector: SemanticFollowupDetector instance
        summarizer: MedicalConversationSummarizer instance
        entity_extractor: MedicalNERExtractor instance
        db_manager: Database manager for persistence
        embedding_manager: Embedding manager for query embeddings

    Returns:
        RAGConversationManager instance
    """
    global _manager
    if _manager is None:
        _manager = RAGConversationManager(
            followup_detector=followup_detector,
            summarizer=summarizer,
            entity_extractor=entity_extractor,
            db_manager=db_manager,
            embedding_manager=embedding_manager,
        )
    return _manager


def reset_conversation_manager():
    """Reset the global conversation manager instance."""
    global _manager
    _manager = None
