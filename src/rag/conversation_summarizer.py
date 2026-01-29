"""
Conversation Summarization for RAG System.

Provides compression of long conversation threads while preserving
critical medical context for follow-up queries.
"""

import json
from utils.structured_logging import get_logger
from dataclasses import dataclass, field
from typing import Optional

logger = get_logger(__name__)


@dataclass
class ConversationSummary:
    """Summary of a RAG conversation."""
    summary_text: str
    key_topics: list[str]
    key_entities: list[dict]
    exchange_count: int
    token_count: int
    medical_context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary_text": self.summary_text,
            "key_topics": self.key_topics,
            "key_entities": self.key_entities,
            "exchange_count": self.exchange_count,
            "token_count": self.token_count,
            "medical_context": self.medical_context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationSummary":
        """Create from dictionary."""
        return cls(
            summary_text=data.get("summary_text", ""),
            key_topics=data.get("key_topics", []),
            key_entities=data.get("key_entities", []),
            exchange_count=data.get("exchange_count", 0),
            token_count=data.get("token_count", 0),
            medical_context=data.get("medical_context", {}),
        )


class MedicalConversationSummarizer:
    """Summarizes RAG conversations preserving medical context."""

    # Configuration
    MAX_EXCHANGES_BEFORE_SUMMARIZE = 5
    TARGET_SUMMARY_TOKENS = 200
    MAX_TOPICS = 10
    MAX_ENTITIES = 20

    # System prompt for AI summarization
    SUMMARIZATION_SYSTEM_PROMPT = """You are a medical conversation summarizer. Your task is to create concise summaries of medical question-answer exchanges while preserving critical clinical information.

Focus on:
1. Main medical topics discussed
2. Key clinical findings, symptoms, or conditions mentioned
3. Medications, treatments, or procedures discussed
4. Diagnoses considered or confirmed
5. Important patient context (if mentioned)

Output format: A brief narrative summary (2-3 sentences) followed by key points."""

    SUMMARIZATION_PROMPT_TEMPLATE = """Summarize this medical conversation:

{conversation_text}

Requirements:
- Keep the summary under {max_tokens} tokens
- Preserve all mentioned medications, conditions, and procedures
- Note any specific dosages, symptoms, or lab values
- Maintain clinical relevance for follow-up questions

Summary:"""

    def __init__(self, ai_processor=None, ner_extractor=None):
        """Initialize the summarizer.

        Args:
            ai_processor: Optional AI processor for generating summaries.
                         If None, will use rule-based summarization.
            ner_extractor: Optional NER extractor for entity extraction.
        """
        self._ai_processor = ai_processor
        self._ner_extractor = ner_extractor

    def should_summarize(self, exchange_count: int) -> bool:
        """Check if conversation should be summarized.

        Args:
            exchange_count: Number of exchanges in conversation

        Returns:
            True if summarization is recommended
        """
        return exchange_count >= self.MAX_EXCHANGES_BEFORE_SUMMARIZE

    def summarize(
        self,
        exchanges: list[tuple[str, str]],
        existing_summary: Optional[ConversationSummary] = None,
    ) -> ConversationSummary:
        """Generate or update conversation summary.

        Args:
            exchanges: List of (query, response) tuples
            existing_summary: Optional existing summary to update

        Returns:
            ConversationSummary with generated summary
        """
        if not exchanges:
            return ConversationSummary(
                summary_text="",
                key_topics=[],
                key_entities=[],
                exchange_count=0,
                token_count=0
            )

        # Extract entities from all exchanges
        all_entities = self._extract_entities_from_exchanges(exchanges)

        # Extract key topics
        key_topics = self._extract_key_topics(exchanges, all_entities)

        # Generate summary text
        if self._ai_processor:
            summary_text = self._generate_ai_summary(exchanges, existing_summary)
        else:
            summary_text = self._generate_rule_based_summary(
                exchanges, key_topics, all_entities
            )

        # Estimate token count
        token_count = self._estimate_tokens(summary_text)

        # Build medical context
        medical_context = self._build_medical_context(all_entities)

        return ConversationSummary(
            summary_text=summary_text,
            key_topics=key_topics[:self.MAX_TOPICS],
            key_entities=all_entities[:self.MAX_ENTITIES],
            exchange_count=len(exchanges),
            token_count=token_count,
            medical_context=medical_context
        )

    def _extract_entities_from_exchanges(
        self,
        exchanges: list[tuple[str, str]]
    ) -> list[dict]:
        """Extract medical entities from exchanges.

        Args:
            exchanges: List of (query, response) tuples

        Returns:
            List of entity dictionaries
        """
        entities = []
        entity_seen = set()

        for query, response in exchanges:
            # Extract from query
            query_entities = self._extract_entities(query)
            for entity in query_entities:
                key = (entity.get('text', '').lower(), entity.get('entity_type', ''))
                if key not in entity_seen:
                    entity_seen.add(key)
                    entity['source'] = 'query'
                    entities.append(entity)

            # Extract from response (first 500 chars to avoid processing huge responses)
            response_entities = self._extract_entities(response[:500])
            for entity in response_entities:
                key = (entity.get('text', '').lower(), entity.get('entity_type', ''))
                if key not in entity_seen:
                    entity_seen.add(key)
                    entity['source'] = 'response'
                    entities.append(entity)

        return entities

    def _extract_entities(self, text: str) -> list[dict]:
        """Extract medical entities from text.

        Args:
            text: Text to analyze

        Returns:
            List of entity dictionaries
        """
        if self._ner_extractor:
            try:
                entities = self._ner_extractor.extract(text)
                return [e.to_dict() for e in entities]
            except Exception as e:
                logger.warning(f"NER extraction failed: {e}")

        # Fallback: Simple keyword extraction
        return self._simple_entity_extraction(text)

    def _simple_entity_extraction(self, text: str) -> list[dict]:
        """Simple rule-based entity extraction fallback.

        Args:
            text: Text to analyze

        Returns:
            List of entity dictionaries
        """
        import re

        entities = []
        text_lower = text.lower()

        # Common medical terms to look for
        medical_terms = {
            'medication': ['medication', 'drug', 'medicine', 'prescription', 'dose', 'dosage'],
            'condition': ['diabetes', 'hypertension', 'cancer', 'disease', 'disorder', 'syndrome'],
            'symptom': ['pain', 'fever', 'cough', 'nausea', 'fatigue', 'headache'],
            'procedure': ['surgery', 'biopsy', 'scan', 'test', 'exam', 'screening'],
        }

        for entity_type, terms in medical_terms.items():
            for term in terms:
                if term in text_lower:
                    # Find the actual word in context
                    pattern = r'\b' + re.escape(term) + r'\w*\b'
                    matches = re.finditer(pattern, text_lower)
                    for match in matches:
                        entities.append({
                            'text': text[match.start():match.end()],
                            'entity_type': entity_type,
                            'start_pos': match.start(),
                            'end_pos': match.end()
                        })
                        break  # Only first match per term

        return entities

    def _extract_key_topics(
        self,
        exchanges: list[tuple[str, str]],
        entities: list[dict]
    ) -> list[str]:
        """Extract key topics from exchanges.

        Args:
            exchanges: List of (query, response) tuples
            entities: Extracted entities

        Returns:
            List of key topic strings
        """
        import re

        topics = []
        topic_counts = {}

        # Stopwords to exclude
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 'that', 'this',
            'and', 'but', 'or', 'if', 'then', 'so', 'because', 'about',
            'tell', 'me', 'please', 'can', 'you', 'i', 'my', 'your',
        }

        # Extract words from queries (more important for topic detection)
        for query, _ in exchanges:
            words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
            for word in words:
                if word not in stopwords:
                    topic_counts[word] = topic_counts.get(word, 0) + 2  # Weight queries higher

        # Add entity normalized names as topics
        for entity in entities:
            normalized = entity.get('normalized_name') or entity.get('text', '')
            if normalized:
                normalized_lower = normalized.lower()
                topic_counts[normalized_lower] = topic_counts.get(normalized_lower, 0) + 3

        # Sort by count and return top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_topics[:self.MAX_TOPICS]]

    def _generate_ai_summary(
        self,
        exchanges: list[tuple[str, str]],
        existing_summary: Optional[ConversationSummary]
    ) -> str:
        """Generate summary using AI model.

        Args:
            exchanges: List of (query, response) tuples
            existing_summary: Optional existing summary

        Returns:
            Summary text
        """
        try:
            # Build conversation text
            conversation_parts = []
            if existing_summary and existing_summary.summary_text:
                conversation_parts.append(
                    f"Previous context: {existing_summary.summary_text}\n"
                )

            for i, (query, response) in enumerate(exchanges[-5:], 1):  # Last 5 exchanges
                # Truncate long responses
                response_preview = response[:300] + "..." if len(response) > 300 else response
                conversation_parts.append(
                    f"Q{i}: {query}\nA{i}: {response_preview}\n"
                )

            conversation_text = "\n".join(conversation_parts)

            # Generate prompt
            prompt = self.SUMMARIZATION_PROMPT_TEMPLATE.format(
                conversation_text=conversation_text,
                max_tokens=self.TARGET_SUMMARY_TOKENS
            )

            # Call AI processor
            from ai.ai import call_openai
            response = call_openai(
                model="gpt-4o-mini",  # Use smaller model for summarization
                system_message=self.SUMMARIZATION_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=0.3
            )

            if response and hasattr(response, 'text'):
                return response.text.strip()
            elif response:
                return str(response).strip()

        except Exception as e:
            logger.warning(f"AI summarization failed: {e}")

        # Fallback to rule-based
        return self._generate_rule_based_summary(exchanges, [], [])

    def _generate_rule_based_summary(
        self,
        exchanges: list[tuple[str, str]],
        key_topics: list[str],
        entities: list[dict]
    ) -> str:
        """Generate summary using rule-based approach.

        Args:
            exchanges: List of (query, response) tuples
            key_topics: Extracted key topics
            entities: Extracted entities

        Returns:
            Summary text
        """
        parts = []

        # Opening
        exchange_count = len(exchanges)
        parts.append(f"Conversation with {exchange_count} exchanges.")

        # Topics
        if key_topics:
            topic_str = ", ".join(key_topics[:5])
            parts.append(f"Main topics: {topic_str}.")

        # Entities by type
        entity_groups = {}
        for entity in entities:
            entity_type = entity.get('entity_type', 'other')
            if entity_type not in entity_groups:
                entity_groups[entity_type] = []
            name = entity.get('normalized_name') or entity.get('text', '')
            if name and name not in entity_groups[entity_type]:
                entity_groups[entity_type].append(name)

        # Add entity groups to summary
        for entity_type, names in entity_groups.items():
            if names:
                names_str = ", ".join(names[:3])
                parts.append(f"{entity_type.title()}s discussed: {names_str}.")

        # Recent queries summary
        if exchanges:
            recent_queries = [q for q, _ in exchanges[-3:]]
            if recent_queries:
                parts.append(f"Recent questions about: {'; '.join(recent_queries[:2])}.")

        return " ".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 characters per token for English
        return len(text) // 4

    def _build_medical_context(self, entities: list[dict]) -> dict:
        """Build structured medical context from entities.

        Args:
            entities: Extracted entities

        Returns:
            Dictionary of medical context by category
        """
        context = {
            'medications': [],
            'conditions': [],
            'symptoms': [],
            'procedures': [],
            'vital_signs': [],
            'lab_tests': [],
        }

        type_mapping = {
            'medication': 'medications',
            'condition': 'conditions',
            'symptom': 'symptoms',
            'procedure': 'procedures',
            'vital_sign': 'vital_signs',
            'lab_test': 'lab_tests',
        }

        for entity in entities:
            entity_type = entity.get('entity_type', '')
            category = type_mapping.get(entity_type)
            if category:
                name = entity.get('normalized_name') or entity.get('text', '')
                if name and name not in context[category]:
                    context[category].append(name)

        # Remove empty categories
        return {k: v for k, v in context.items() if v}


# Singleton instance
_summarizer: Optional[MedicalConversationSummarizer] = None


def get_conversation_summarizer(
    ai_processor=None,
    ner_extractor=None
) -> MedicalConversationSummarizer:
    """Get the global conversation summarizer instance.

    Args:
        ai_processor: Optional AI processor
        ner_extractor: Optional NER extractor

    Returns:
        MedicalConversationSummarizer instance
    """
    global _summarizer
    if _summarizer is None:
        _summarizer = MedicalConversationSummarizer(ai_processor, ner_extractor)
    return _summarizer


def summarize_conversation(
    exchanges: list[tuple[str, str]],
    existing_summary: Optional[ConversationSummary] = None
) -> ConversationSummary:
    """Convenience function for summarizing conversations.

    Args:
        exchanges: List of (query, response) tuples
        existing_summary: Optional existing summary to update

    Returns:
        ConversationSummary
    """
    summarizer = get_conversation_summarizer()
    return summarizer.summarize(exchanges, existing_summary)
