"""
ML-based Entity Classification for Knowledge Graph.

Provides embedding-based entity type classification with context awareness,
replacing simple rule-based type detection with semantic understanding.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from rag.graph_data_provider import EntityType

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of entity type classification."""
    entity_text: str
    predicted_type: EntityType
    confidence: float  # 0.0-1.0
    alternative_types: list[tuple[EntityType, float]] = field(default_factory=list)
    context_used: str = ""  # Surrounding text used for classification


class MLEntityClassifier:
    """ML-based entity classifier using embeddings and keyword patterns.

    Uses a combination of:
    1. Embedding similarity to type prototypes
    2. Keyword/pattern boosting for known medical terms
    3. Context awareness for disambiguation
    """

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    LOW_CONFIDENCE = 0.5

    # Type-specific keyword patterns for boosting
    TYPE_KEYWORDS = {
        EntityType.MEDICATION: [
            "mg", "mcg", "tablet", "capsule", "dose", "dosage", "prescription",
            "drug", "medication", "medicine", "pharmaceutical", "generic",
            "brand", "oral", "injection", "patch", "cream", "ointment",
            "syrup", "suspension", "inhaler", "nebulizer", "iv", "po",
            "prn", "qd", "bid", "tid", "qid", "daily", "twice"
        ],
        EntityType.CONDITION: [
            "disease", "syndrome", "disorder", "itis", "osis", "emia",
            "diagnosis", "diagnosed", "condition", "illness", "pathology",
            "chronic", "acute", "malignant", "benign", "primary", "secondary",
            "history of", "hx of", "known", "confirmed", "suspected"
        ],
        EntityType.PROCEDURE: [
            "surgery", "ectomy", "plasty", "scopy", "otomy", "gram",
            "operation", "procedure", "intervention", "removal", "repair",
            "biopsy", "resection", "excision", "incision", "insertion",
            "performed", "underwent", "scheduled for"
        ],
        EntityType.LAB_TEST: [
            "test", "level", "count", "panel", "ratio", "lab", "laboratory",
            "result", "value", "normal", "abnormal", "elevated", "decreased",
            "positive", "negative", "ordered", "pending", "drawn", "specimen",
            "serum", "plasma", "urine", "culture", "sensitivity"
        ],
        EntityType.ANATOMY: [
            "muscle", "bone", "nerve", "artery", "vein", "organ", "gland",
            "tissue", "joint", "ligament", "tendon", "membrane", "cavity",
            "left", "right", "bilateral", "proximal", "distal", "anterior",
            "posterior", "superior", "inferior", "medial", "lateral"
        ],
        EntityType.SYMPTOM: [
            "pain", "ache", "discomfort", "swelling", "redness", "numbness",
            "tingling", "weakness", "fatigue", "fever", "chills", "nausea",
            "vomiting", "diarrhea", "constipation", "headache", "dizziness",
            "complaint", "presenting", "reports", "denies", "admits to"
        ],
    }

    # Medical abbreviation to type mappings
    ABBREVIATION_TYPES = {
        # Conditions
        "htn": EntityType.CONDITION,
        "dm": EntityType.CONDITION,
        "t2dm": EntityType.CONDITION,
        "chf": EntityType.CONDITION,
        "cad": EntityType.CONDITION,
        "copd": EntityType.CONDITION,
        "ckd": EntityType.CONDITION,
        "esrd": EntityType.CONDITION,
        "mi": EntityType.CONDITION,
        "cva": EntityType.CONDITION,
        "tia": EntityType.CONDITION,
        "afib": EntityType.CONDITION,
        "gerd": EntityType.CONDITION,
        "uti": EntityType.CONDITION,
        "pe": EntityType.CONDITION,
        "dvt": EntityType.CONDITION,

        # Lab tests
        "cbc": EntityType.LAB_TEST,
        "bmp": EntityType.LAB_TEST,
        "cmp": EntityType.LAB_TEST,
        "lfts": EntityType.LAB_TEST,
        "tsh": EntityType.LAB_TEST,
        "hba1c": EntityType.LAB_TEST,
        "pt": EntityType.LAB_TEST,
        "inr": EntityType.LAB_TEST,
        "bnp": EntityType.LAB_TEST,
        "abg": EntityType.LAB_TEST,
        "ua": EntityType.LAB_TEST,
        "gfr": EntityType.LAB_TEST,
        "bun": EntityType.LAB_TEST,
        "crp": EntityType.LAB_TEST,
        "esr": EntityType.LAB_TEST,

        # Procedures
        "mri": EntityType.PROCEDURE,
        "ct": EntityType.PROCEDURE,
        "ekg": EntityType.PROCEDURE,
        "ecg": EntityType.PROCEDURE,
        "echo": EntityType.PROCEDURE,
        "egd": EntityType.PROCEDURE,
        "ercp": EntityType.PROCEDURE,
        "cabg": EntityType.PROCEDURE,
        "turp": EntityType.PROCEDURE,
        "orif": EntityType.PROCEDURE,
    }

    def __init__(self, embedding_manager=None):
        """Initialize the ML entity classifier.

        Args:
            embedding_manager: Optional EmbeddingManager for semantic classification
        """
        self._embedding_manager = embedding_manager
        self._type_prototypes: dict[EntityType, list[float]] = {}
        self._prototypes_loaded = False

    def _get_embedding_manager(self):
        """Get or create embedding manager."""
        if self._embedding_manager is None:
            try:
                from rag.embedding_manager import CachedEmbeddingManager
                self._embedding_manager = CachedEmbeddingManager()
            except Exception as e:
                logger.debug(f"Could not create embedding manager: {e}")
                return None
        return self._embedding_manager

    def _load_prototypes(self):
        """Load type prototype embeddings from file or generate them."""
        if self._prototypes_loaded:
            return

        import json
        from pathlib import Path

        prototypes_path = Path(__file__).parent / "data" / "entity_prototypes.json"

        if prototypes_path.exists():
            try:
                with open(prototypes_path, "r") as f:
                    data = json.load(f)
                    for type_name, embedding in data.items():
                        try:
                            entity_type = EntityType(type_name)
                            self._type_prototypes[entity_type] = embedding
                        except ValueError:
                            logger.debug(f"Unknown entity type in prototypes: {type_name}")
                self._prototypes_loaded = True
                logger.info(f"Loaded {len(self._type_prototypes)} entity type prototypes")
            except Exception as e:
                logger.warning(f"Failed to load entity prototypes: {e}")

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _get_keyword_score(self, text: str, entity_type: EntityType) -> float:
        """Calculate keyword match score for an entity type.

        Args:
            text: Entity text to analyze
            entity_type: Type to check keywords for

        Returns:
            Score between 0.0 and 1.0 based on keyword matches
        """
        keywords = self.TYPE_KEYWORDS.get(entity_type, [])
        if not keywords:
            return 0.0

        text_lower = text.lower()
        context_words = text_lower.split()

        # Count keyword matches
        match_count = 0
        for keyword in keywords:
            if keyword in text_lower:
                match_count += 1

        # Normalize by number of keywords (capped at 1.0)
        return min(1.0, match_count / max(5, len(keywords) * 0.3))

    def _check_abbreviation(self, text: str) -> Optional[EntityType]:
        """Check if text is a known medical abbreviation.

        Args:
            text: Text to check

        Returns:
            EntityType if abbreviation matches, None otherwise
        """
        text_lower = text.lower().strip()
        return self.ABBREVIATION_TYPES.get(text_lower)

    def classify(
        self,
        entity_text: str,
        context: str = "",
        existing_entities: Optional[list[str]] = None
    ) -> ClassificationResult:
        """Classify entity type using multiple signals.

        Uses a combination of:
        1. Direct abbreviation matching
        2. Keyword pattern matching
        3. Embedding similarity (if available)
        4. Context-based disambiguation

        Args:
            entity_text: The entity text to classify
            context: Surrounding text for context
            existing_entities: Other entities in the same document (unused currently)

        Returns:
            ClassificationResult with predicted type and confidence
        """
        # Step 1: Check for known abbreviations
        abbrev_type = self._check_abbreviation(entity_text)
        if abbrev_type:
            return ClassificationResult(
                entity_text=entity_text,
                predicted_type=abbrev_type,
                confidence=0.95,  # High confidence for known abbreviations
                alternative_types=[],
                context_used=context[:100] if context else ""
            )

        # Step 2: Calculate keyword scores for each type
        scores: dict[EntityType, float] = {}

        # Combine entity text and context for analysis
        analysis_text = f"{context} {entity_text}" if context else entity_text

        for entity_type in EntityType:
            if entity_type in [EntityType.UNKNOWN, EntityType.ENTITY, EntityType.DOCUMENT, EntityType.EPISODE]:
                continue

            keyword_score = self._get_keyword_score(analysis_text, entity_type)
            scores[entity_type] = keyword_score

        # Step 3: Try embedding-based classification if prototypes available
        self._load_prototypes()
        embedding_manager = self._get_embedding_manager()

        if embedding_manager and self._type_prototypes:
            try:
                # Generate embedding for entity + context
                combined_text = f"{entity_text}: {context[:200]}" if context else entity_text
                entity_embedding = embedding_manager.generate_embedding(combined_text)

                # Calculate similarity to each type prototype
                for entity_type, prototype in self._type_prototypes.items():
                    similarity = self._cosine_similarity(entity_embedding, prototype)
                    # Combine with keyword score (60% embedding, 40% keyword)
                    if entity_type in scores:
                        scores[entity_type] = 0.6 * similarity + 0.4 * scores[entity_type]
                    else:
                        scores[entity_type] = similarity

            except Exception as e:
                logger.debug(f"Embedding classification failed: {e}")

        # Step 4: Get top predictions
        sorted_types = sorted(scores.items(), key=lambda x: -x[1])

        if not sorted_types or sorted_types[0][1] < 0.1:
            # No good match, use rule-based fallback
            fallback_type = EntityType.from_string(entity_text)
            return ClassificationResult(
                entity_text=entity_text,
                predicted_type=fallback_type,
                confidence=0.3,  # Low confidence for fallback
                alternative_types=[],
                context_used=context[:100] if context else ""
            )

        best_type, best_score = sorted_types[0]
        alternatives = [(t, s) for t, s in sorted_types[1:3] if s > 0.1]

        return ClassificationResult(
            entity_text=entity_text,
            predicted_type=best_type,
            confidence=min(0.95, best_score),  # Cap at 0.95
            alternative_types=alternatives,
            context_used=context[:100] if context else ""
        )

    def classify_batch(
        self,
        entities: list[tuple[str, str]],  # (entity_text, context) pairs
    ) -> list[ClassificationResult]:
        """Classify multiple entities efficiently.

        Args:
            entities: List of (entity_text, context) tuples

        Returns:
            List of ClassificationResult for each entity
        """
        results = []
        for entity_text, context in entities:
            result = self.classify(entity_text, context)
            results.append(result)
        return results

    def get_type_confidence(
        self,
        entity_text: str,
        expected_type: EntityType,
        context: str = ""
    ) -> float:
        """Get confidence score that entity is of expected type.

        Useful for validating existing classifications.

        Args:
            entity_text: Entity text
            expected_type: The type to check against
            context: Surrounding context

        Returns:
            Confidence score 0.0-1.0
        """
        result = self.classify(entity_text, context)

        if result.predicted_type == expected_type:
            return result.confidence

        # Check if expected type is in alternatives
        for alt_type, alt_conf in result.alternative_types:
            if alt_type == expected_type:
                return alt_conf

        return 0.0


# Singleton instance
_classifier: Optional[MLEntityClassifier] = None


def get_entity_classifier() -> MLEntityClassifier:
    """Get the global entity classifier instance.

    Returns:
        MLEntityClassifier instance
    """
    global _classifier
    if _classifier is None:
        _classifier = MLEntityClassifier()
    return _classifier


def classify_entity(entity_text: str, context: str = "") -> ClassificationResult:
    """Convenience function to classify a single entity.

    Args:
        entity_text: Entity text to classify
        context: Optional surrounding context

    Returns:
        ClassificationResult
    """
    classifier = get_entity_classifier()
    return classifier.classify(entity_text, context)
