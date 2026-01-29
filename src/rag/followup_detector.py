"""
Semantic Follow-up Detection for RAG Conversations.

Provides multi-signal detection of follow-up questions using:
- Semantic similarity (embedding cosine distance)
- Coreference detection (pronouns and incomplete references)
- Topic overlap analysis
- Intent classification
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class QueryIntent(str, Enum):
    """Classification of query intent types."""
    NEW_TOPIC = "new_topic"
    FOLLOWUP = "followup"
    CLARIFICATION = "clarification"
    DRILL_DOWN = "drill_down"
    COMPARISON = "comparison"
    RELATED = "related"


@dataclass
class FollowupResult:
    """Result of follow-up detection analysis."""
    is_followup: bool
    confidence: float  # 0.0-1.0
    intent: QueryIntent
    semantic_similarity: float
    coreference_detected: bool
    topic_overlap_score: float
    explanation: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_followup": self.is_followup,
            "confidence": self.confidence,
            "intent": self.intent.value,
            "semantic_similarity": self.semantic_similarity,
            "coreference_detected": self.coreference_detected,
            "topic_overlap_score": self.topic_overlap_score,
            "explanation": self.explanation,
        }


class SemanticFollowupDetector:
    """Semantic follow-up detection using embeddings and multiple signals."""

    # Thresholds for detection
    SIMILARITY_THRESHOLD = 0.65
    HIGH_SIMILARITY_THRESHOLD = 0.8
    MIN_CONFIDENCE = 0.5

    # Weights for combining signals
    WEIGHT_SEMANTIC = 0.4
    WEIGHT_COREFERENCE = 0.25
    WEIGHT_TOPIC_OVERLAP = 0.2
    WEIGHT_PATTERN = 0.15

    # Pronouns and references that suggest context dependency
    CONTEXT_REFS = frozenset([
        'it', 'this', 'that', 'these', 'those', 'they', 'them', 'its', 'their',
        'he', 'she', 'his', 'her', 'the patient', 'the medication', 'the condition',
        'the treatment', 'the drug', 'the diagnosis', 'the symptom'
    ])

    # Incomplete reference patterns
    INCOMPLETE_REF_PATTERNS = [
        r'\b(the\s+same)\b',
        r'\b(that\s+one)\b',
        r'\b(the\s+other)\b',
        r'\b(another)\b',
        r'\b(which\s+ones?)\b',
    ]

    # Follow-up starter patterns (compiled for efficiency)
    FOLLOWUP_PATTERNS = [
        (re.compile(r'^what\s+about\b', re.IGNORECASE), QueryIntent.RELATED),
        (re.compile(r'^how\s+about\b', re.IGNORECASE), QueryIntent.RELATED),
        (re.compile(r'^and\s+(?:what|how|why)\b', re.IGNORECASE), QueryIntent.FOLLOWUP),
        (re.compile(r'^also\b', re.IGNORECASE), QueryIntent.RELATED),
        (re.compile(r'^what\s+else\b', re.IGNORECASE), QueryIntent.DRILL_DOWN),
        (re.compile(r'^tell\s+me\s+more\b', re.IGNORECASE), QueryIntent.DRILL_DOWN),
        (re.compile(r'^more\s+(?:on|about|details?)\b', re.IGNORECASE), QueryIntent.DRILL_DOWN),
        (re.compile(r'^explain\s+(?:more|further)\b', re.IGNORECASE), QueryIntent.CLARIFICATION),
        (re.compile(r'^why\s+(?:is|are|does|do|would|should)\b', re.IGNORECASE), QueryIntent.CLARIFICATION),
        (re.compile(r'^can\s+you\s+(?:explain|clarify|elaborate)\b', re.IGNORECASE), QueryIntent.CLARIFICATION),
        (re.compile(r'^(?:how|what)\s+(?:about|if)\b', re.IGNORECASE), QueryIntent.RELATED),
        (re.compile(r'^compared?\s+to\b', re.IGNORECASE), QueryIntent.COMPARISON),
        (re.compile(r'^versus\b', re.IGNORECASE), QueryIntent.COMPARISON),
        (re.compile(r'^(?:vs\.?|v\.?)\s+', re.IGNORECASE), QueryIntent.COMPARISON),
        (re.compile(r'^(?:is|are)\s+there\s+(?:any\s+)?(?:other|alternative)s?\b', re.IGNORECASE), QueryIntent.DRILL_DOWN),
        (re.compile(r'^(?:what|which)\s+(?:are\s+)?(?:the\s+)?(?:side\s+effects?|risks?|benefits?|alternatives?)\b', re.IGNORECASE), QueryIntent.DRILL_DOWN),
    ]

    # Question words that may indicate subject-less follow-ups
    QUESTION_STARTERS = frozenset([
        'what', 'how', 'why', 'when', 'where', 'which', 'who', 'whose', 'whom',
        'does', 'do', 'is', 'are', 'can', 'could', 'should', 'would', 'will'
    ])

    def __init__(self, embedding_manager=None):
        """Initialize the follow-up detector.

        Args:
            embedding_manager: Optional embedding manager for semantic similarity.
                             If None, will use non-embedding signals only.
        """
        self._embedding_manager = embedding_manager
        self._compiled_incomplete_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.INCOMPLETE_REF_PATTERNS
        ]

    def detect(
        self,
        current_query: str,
        previous_query: Optional[str] = None,
        previous_topics: Optional[list[str]] = None,
        current_embedding: Optional[list[float]] = None,
        previous_embedding: Optional[list[float]] = None,
    ) -> FollowupResult:
        """Multi-signal follow-up detection.

        Args:
            current_query: The current user query
            previous_query: The previous query in conversation (optional)
            previous_topics: Key topics from the previous query (optional)
            current_embedding: Embedding of current query (optional)
            previous_embedding: Embedding of previous query (optional)

        Returns:
            FollowupResult with detection results
        """
        # No previous context = new topic
        if not previous_query and not previous_topics:
            return FollowupResult(
                is_followup=False,
                confidence=1.0,
                intent=QueryIntent.NEW_TOPIC,
                semantic_similarity=0.0,
                coreference_detected=False,
                topic_overlap_score=0.0,
                explanation="No previous conversation context available"
            )

        # Initialize signals
        signals = {
            'semantic_similarity': 0.0,
            'coreference': False,
            'topic_overlap': 0.0,
            'pattern_match': None,
        }

        explanations = []

        # 1. Compute semantic similarity
        if current_embedding and previous_embedding:
            signals['semantic_similarity'] = self._compute_similarity(
                current_embedding, previous_embedding
            )
            if signals['semantic_similarity'] >= self.HIGH_SIMILARITY_THRESHOLD:
                explanations.append(
                    f"High semantic similarity ({signals['semantic_similarity']:.2f})"
                )
            elif signals['semantic_similarity'] >= self.SIMILARITY_THRESHOLD:
                explanations.append(
                    f"Moderate semantic similarity ({signals['semantic_similarity']:.2f})"
                )

        # 2. Detect coreference (pronouns and incomplete references)
        signals['coreference'] = self._detect_coreference(current_query)
        if signals['coreference']:
            explanations.append("Context-dependent references detected")

        # 3. Check topic overlap
        if previous_topics:
            signals['topic_overlap'] = self._check_topic_overlap(
                current_query, previous_topics
            )
            if signals['topic_overlap'] > 0.5:
                explanations.append(
                    f"Topic overlap detected ({signals['topic_overlap']:.0%})"
                )

        # 4. Check follow-up patterns
        signals['pattern_match'] = self._check_followup_patterns(current_query)
        if signals['pattern_match']:
            explanations.append(f"Follow-up pattern detected: {signals['pattern_match'].value}")

        # 5. Check for short queries (often follow-ups)
        words = current_query.split()
        if len(words) <= 4:
            # Short queries with question words and no clear subject
            first_word = words[0].lower() if words else ""
            if first_word in self.QUESTION_STARTERS:
                if not self._has_clear_subject(current_query, previous_topics or []):
                    signals['coreference'] = True
                    if "Short query" not in str(explanations):
                        explanations.append("Short query likely referencing previous context")

        # 6. Calculate combined confidence
        confidence = self._calculate_confidence(signals)

        # 7. Determine intent
        intent = self._determine_intent(signals, current_query)

        # 8. Make final determination
        is_followup = confidence >= self.MIN_CONFIDENCE

        if not explanations:
            if is_followup:
                explanations.append("Multiple weak signals suggest follow-up")
            else:
                explanations.append("Query appears to be a new topic")

        return FollowupResult(
            is_followup=is_followup,
            confidence=confidence,
            intent=intent,
            semantic_similarity=signals['semantic_similarity'],
            coreference_detected=signals['coreference'],
            topic_overlap_score=signals['topic_overlap'],
            explanation="; ".join(explanations)
        )

    def _compute_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float]
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            # Compute cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # Clamp to [0, 1] range
            return max(0.0, min(1.0, float(similarity)))

        except Exception as e:
            logger.warning(f"Error computing similarity: {e}")
            return 0.0

    def _detect_coreference(self, query: str) -> bool:
        """Detect if query contains context-dependent references.

        Args:
            query: The query to analyze

        Returns:
            True if coreference is detected
        """
        query_lower = query.lower()
        words = set(query_lower.split())

        # Check for pronouns and context references
        for ref in self.CONTEXT_REFS:
            if ' ' in ref:
                # Multi-word reference
                if ref in query_lower:
                    return True
            else:
                # Single word
                if ref in words:
                    return True

        # Check for incomplete reference patterns
        for pattern in self._compiled_incomplete_patterns:
            if pattern.search(query_lower):
                return True

        return False

    def _check_topic_overlap(
        self,
        query: str,
        previous_topics: list[str]
    ) -> float:
        """Check for overlap between query and previous topics.

        Args:
            query: Current query
            previous_topics: Topics from previous query

        Returns:
            Overlap score (0.0 to 1.0)
        """
        if not previous_topics:
            return 0.0

        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Count topics mentioned in query
        topics_mentioned = 0
        for topic in previous_topics:
            topic_lower = topic.lower()
            if ' ' in topic_lower:
                # Multi-word topic
                if topic_lower in query_lower:
                    topics_mentioned += 1
            else:
                # Single word topic
                if topic_lower in query_words:
                    topics_mentioned += 1

        # Calculate overlap ratio
        if previous_topics:
            return topics_mentioned / len(previous_topics)
        return 0.0

    def _check_followup_patterns(self, query: str) -> Optional[QueryIntent]:
        """Check if query matches follow-up patterns.

        Args:
            query: The query to analyze

        Returns:
            QueryIntent if pattern matches, None otherwise
        """
        query_stripped = query.strip()

        for pattern, intent in self.FOLLOWUP_PATTERNS:
            if pattern.search(query_stripped):
                return intent

        return None

    def _has_clear_subject(
        self,
        query: str,
        previous_topics: list[str]
    ) -> bool:
        """Check if query has a clear subject independent of previous context.

        Args:
            query: The query to analyze
            previous_topics: Topics from previous query

        Returns:
            True if query has clear subject
        """
        query_lower = query.lower()

        # If query mentions specific medical terms, it likely has a clear subject
        # This is a simplified check - could be enhanced with NER
        medical_indicators = [
            'medication', 'drug', 'treatment', 'condition', 'disease',
            'symptom', 'diagnosis', 'patient', 'dosage', 'side effect'
        ]

        for indicator in medical_indicators:
            if indicator in query_lower:
                # Check if it's a specific mention, not just "the medication"
                if not re.search(rf'\b(the|this|that)\s+{indicator}\b', query_lower):
                    return True

        # Check for proper nouns (capitalized words not at start)
        words = query.split()
        for i, word in enumerate(words[1:], 1):
            if word[0].isupper() and len(word) > 2:
                return True

        # If previous topics are not mentioned, might be new subject
        if previous_topics:
            topics_mentioned = sum(
                1 for topic in previous_topics
                if topic.lower() in query_lower
            )
            if topics_mentioned == 0:
                # No previous topics mentioned - could be new subject
                # But also could be implicit reference
                return len(words) > 6  # Longer queries more likely to have clear subject

        return False

    def _calculate_confidence(self, signals: dict) -> float:
        """Calculate overall confidence score from signals.

        Args:
            signals: Dictionary of signal values

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Base scores for each signal
        semantic_score = signals['semantic_similarity']
        coreference_score = 1.0 if signals['coreference'] else 0.0
        topic_score = signals['topic_overlap']
        pattern_score = 1.0 if signals['pattern_match'] else 0.0

        # Weighted combination
        confidence = (
            self.WEIGHT_SEMANTIC * semantic_score +
            self.WEIGHT_COREFERENCE * coreference_score +
            self.WEIGHT_TOPIC_OVERLAP * topic_score +
            self.WEIGHT_PATTERN * pattern_score
        )

        # Boost confidence if multiple signals agree
        active_signals = sum([
            semantic_score >= self.SIMILARITY_THRESHOLD,
            signals['coreference'],
            topic_score > 0.3,
            signals['pattern_match'] is not None
        ])

        if active_signals >= 3:
            confidence = min(1.0, confidence * 1.2)
        elif active_signals >= 2:
            confidence = min(1.0, confidence * 1.1)

        return confidence

    def _determine_intent(self, signals: dict, query: str) -> QueryIntent:
        """Determine the intent of the query.

        Args:
            signals: Dictionary of signal values
            query: The original query

        Returns:
            QueryIntent classification
        """
        # Check pattern-matched intent first
        if signals['pattern_match']:
            return signals['pattern_match']

        # High semantic similarity suggests continuation
        if signals['semantic_similarity'] >= self.HIGH_SIMILARITY_THRESHOLD:
            # Check for clarification indicators
            clarification_words = ['why', 'how', 'explain', 'clarify', 'understand']
            if any(word in query.lower() for word in clarification_words):
                return QueryIntent.CLARIFICATION
            return QueryIntent.FOLLOWUP

        # Coreference detected
        if signals['coreference']:
            # Could be drill-down or followup
            drill_indicators = ['else', 'more', 'other', 'another', 'additional']
            if any(indicator in query.lower() for indicator in drill_indicators):
                return QueryIntent.DRILL_DOWN
            return QueryIntent.FOLLOWUP

        # Topic overlap suggests related query
        if signals['topic_overlap'] > 0.3:
            compare_words = ['versus', 'vs', 'compared', 'difference', 'better', 'worse']
            if any(word in query.lower() for word in compare_words):
                return QueryIntent.COMPARISON
            return QueryIntent.RELATED

        # Default to new topic if no strong signals
        return QueryIntent.NEW_TOPIC


# Singleton instance
_detector: Optional[SemanticFollowupDetector] = None


def get_followup_detector(embedding_manager=None) -> SemanticFollowupDetector:
    """Get the global followup detector instance.

    Args:
        embedding_manager: Optional embedding manager for semantic similarity

    Returns:
        SemanticFollowupDetector instance
    """
    global _detector
    if _detector is None:
        _detector = SemanticFollowupDetector(embedding_manager)
    return _detector


def detect_followup(
    current_query: str,
    previous_query: Optional[str] = None,
    previous_topics: Optional[list[str]] = None,
    current_embedding: Optional[list[float]] = None,
    previous_embedding: Optional[list[float]] = None,
) -> FollowupResult:
    """Convenience function for follow-up detection.

    Args:
        current_query: The current user query
        previous_query: The previous query in conversation
        previous_topics: Key topics from the previous query
        current_embedding: Embedding of current query
        previous_embedding: Embedding of previous query

    Returns:
        FollowupResult with detection results
    """
    detector = get_followup_detector()
    return detector.detect(
        current_query,
        previous_query,
        previous_topics,
        current_embedding,
        previous_embedding
    )
