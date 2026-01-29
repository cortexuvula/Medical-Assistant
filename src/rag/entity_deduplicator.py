"""
Entity Deduplication for Knowledge Graph.

Provides cross-document entity linking and deduplication using
similarity matching (string similarity + embedding similarity).
"""

from utils.structured_logging import get_logger
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from rag.graph_data_provider import EntityType

logger = get_logger(__name__)


@dataclass
class EntityCluster:
    """A cluster of deduplicated entities.

    Represents a canonical entity with all its variants across documents.
    """
    canonical_id: str
    canonical_name: str  # Normalized/preferred name
    entity_type: EntityType
    variants: list[str] = field(default_factory=list)  # All text variants
    source_documents: list[str] = field(default_factory=list)  # Document IDs
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    mention_count: int = 1
    confidence: float = 1.0  # Aggregated confidence
    embedding: Optional[list[float]] = None  # Canonical embedding

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "canonical_id": self.canonical_id,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type.value,
            "variants": self.variants,
            "source_documents": self.source_documents,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "mention_count": self.mention_count,
            "confidence": self.confidence,
        }


class EntityDeduplicator:
    """Deduplicates entities across documents using similarity matching.

    Uses a combination of:
    1. Exact normalized name matching
    2. Fuzzy string matching (Levenshtein)
    3. Embedding similarity matching
    4. Medical abbreviation expansion
    """

    # Similarity threshold for merging (embedding-based)
    EMBEDDING_MERGE_THRESHOLD = 0.85

    # String similarity threshold for fuzzy matching
    FUZZY_THRESHOLD = 0.9

    # Minimum confidence to consider a merge
    MIN_CONFIDENCE_THRESHOLD = 0.5

    # Medical abbreviation expansions for normalization
    ABBREVIATION_EXPANSIONS = {
        # Cardiovascular
        "htn": "hypertension",
        "chf": "congestive heart failure",
        "cad": "coronary artery disease",
        "mi": "myocardial infarction",
        "afib": "atrial fibrillation",
        "a-fib": "atrial fibrillation",
        "dvt": "deep vein thrombosis",
        "pe": "pulmonary embolism",

        # Respiratory
        "copd": "chronic obstructive pulmonary disease",
        "sob": "shortness of breath",
        "uri": "upper respiratory infection",

        # Endocrine
        "dm": "diabetes mellitus",
        "t2dm": "type 2 diabetes mellitus",
        "t1dm": "type 1 diabetes mellitus",
        "dka": "diabetic ketoacidosis",

        # Renal
        "ckd": "chronic kidney disease",
        "esrd": "end stage renal disease",
        "uti": "urinary tract infection",
        "aki": "acute kidney injury",

        # Neurological
        "cva": "cerebrovascular accident",
        "tia": "transient ischemic attack",
        "loc": "loss of consciousness",

        # GI
        "gerd": "gastroesophageal reflux disease",
        "ibs": "irritable bowel syndrome",
        "ibd": "inflammatory bowel disease",
        "gi": "gastrointestinal",

        # Lab tests
        "cbc": "complete blood count",
        "bmp": "basic metabolic panel",
        "cmp": "comprehensive metabolic panel",
        "lfts": "liver function tests",
        "tsh": "thyroid stimulating hormone",
        "hba1c": "hemoglobin a1c",
        "pt": "prothrombin time",
        "inr": "international normalized ratio",
        "bnp": "b-type natriuretic peptide",
        "abg": "arterial blood gas",
        "gfr": "glomerular filtration rate",
        "bun": "blood urea nitrogen",

        # Procedures
        "ekg": "electrocardiogram",
        "ecg": "electrocardiogram",
        "mri": "magnetic resonance imaging",
        "ct": "computed tomography",
        "echo": "echocardiogram",
        "egd": "esophagogastroduodenoscopy",
        "cabg": "coronary artery bypass graft",
    }

    def __init__(self, embedding_manager=None, db_manager=None):
        """Initialize the entity deduplicator.

        Args:
            embedding_manager: Optional EmbeddingManager for similarity matching
            db_manager: Optional database manager for persistence
        """
        self._embedding_manager = embedding_manager
        self._db = db_manager
        self._entity_cache: dict[str, EntityCluster] = {}
        self._embedding_cache: dict[str, list[float]] = {}

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

    def _normalize_name(self, text: str) -> str:
        """Normalize entity name for comparison.

        Args:
            text: Entity text to normalize

        Returns:
            Normalized text (lowercase, expanded abbreviations, clean whitespace)
        """
        # Lowercase and clean whitespace
        normalized = " ".join(text.lower().split())

        # Remove common noise characters
        normalized = re.sub(r'[^\w\s\-\']', '', normalized)

        # Expand abbreviations
        words = normalized.split()
        expanded_words = []
        for word in words:
            expanded = self.ABBREVIATION_EXPANSIONS.get(word, word)
            expanded_words.append(expanded)

        return " ".join(expanded_words)

    def _levenshtein_ratio(self, s1: str, s2: str) -> float:
        """Calculate Levenshtein similarity ratio between two strings.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        if not s1 or not s2:
            return 0.0

        if s1 == s2:
            return 1.0

        len1, len2 = len(s1), len(s2)
        max_len = max(len1, len2)

        # Quick check - if lengths differ too much, can't be similar
        if abs(len1 - len2) > max_len * 0.3:
            return 0.0

        # Calculate Levenshtein distance
        if len1 > len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1

        current_row = range(len1 + 1)
        for i in range(1, len2 + 1):
            previous_row, current_row = current_row, [i] + [0] * len1
            for j in range(1, len1 + 1):
                add, delete, change = (
                    previous_row[j] + 1,
                    current_row[j - 1] + 1,
                    previous_row[j - 1]
                )
                if s1[j - 1] != s2[i - 1]:
                    change += 1
                current_row[j] = min(add, delete, change)

        distance = current_row[len1]
        return 1.0 - (distance / max_len)

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

    def _get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding for text (cached)."""
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        embedding_manager = self._get_embedding_manager()
        if not embedding_manager:
            return None

        try:
            embedding = embedding_manager.generate_embedding(text)
            self._embedding_cache[text] = embedding
            return embedding
        except Exception as e:
            logger.debug(f"Failed to get embedding: {e}")
            return None

    def _update_cluster(
        self,
        cluster: EntityCluster,
        entity_text: str,
        document_id: str,
        confidence: float = 1.0
    ):
        """Update an existing cluster with a new entity mention.

        Args:
            cluster: Cluster to update
            entity_text: New entity text
            document_id: Source document ID
            confidence: Confidence of this entity
        """
        # Add variant if not already present
        if entity_text not in cluster.variants:
            cluster.variants.append(entity_text)

        # Add document if not already present
        if document_id and document_id not in cluster.source_documents:
            cluster.source_documents.append(document_id)

        # Update counts and timestamps
        cluster.mention_count += 1
        cluster.last_seen = datetime.now()

        # Update confidence (weighted average)
        total_mentions = cluster.mention_count
        cluster.confidence = (
            cluster.confidence * (total_mentions - 1) + confidence
        ) / total_mentions

    def deduplicate(
        self,
        entity_text: str,
        entity_type: EntityType,
        document_id: str = "",
        confidence: float = 1.0
    ) -> EntityCluster:
        """Find or create entity cluster for this entity.

        Attempts to match against existing clusters using:
        1. Exact normalized name match
        2. Fuzzy string match
        3. Embedding similarity match

        Args:
            entity_text: Entity text
            entity_type: Type of entity
            document_id: Source document ID
            confidence: Confidence score

        Returns:
            EntityCluster (existing or newly created)
        """
        normalized = self._normalize_name(entity_text)

        # Step 1: Check for exact match by normalized name
        if normalized in self._entity_cache:
            cluster = self._entity_cache[normalized]
            # Only merge if same type
            if cluster.entity_type == entity_type:
                self._update_cluster(cluster, entity_text, document_id, confidence)
                return cluster

        # Step 2: Check for fuzzy string match (same type only)
        for cached_name, cluster in self._entity_cache.items():
            if cluster.entity_type != entity_type:
                continue

            similarity = self._levenshtein_ratio(normalized, cached_name)
            if similarity >= self.FUZZY_THRESHOLD:
                self._update_cluster(cluster, entity_text, document_id, confidence)
                # Also cache under new normalized name
                self._entity_cache[normalized] = cluster
                logger.debug(f"Fuzzy match: '{entity_text}' -> '{cluster.canonical_name}' (sim={similarity:.2f})")
                return cluster

        # Step 3: Check for embedding similarity match (same type only)
        entity_embedding = self._get_embedding(entity_text)
        if entity_embedding:
            best_match = None
            best_similarity = 0.0

            for cached_name, cluster in self._entity_cache.items():
                if cluster.entity_type != entity_type:
                    continue

                cluster_embedding = self._get_embedding(cluster.canonical_name)
                if cluster_embedding:
                    similarity = self._cosine_similarity(entity_embedding, cluster_embedding)
                    if similarity >= self.EMBEDDING_MERGE_THRESHOLD and similarity > best_similarity:
                        best_match = cluster
                        best_similarity = similarity

            if best_match:
                self._update_cluster(best_match, entity_text, document_id, confidence)
                # Also cache under new normalized name
                self._entity_cache[normalized] = best_match
                logger.debug(f"Embedding match: '{entity_text}' -> '{best_match.canonical_name}' (sim={best_similarity:.2f})")
                return best_match

        # Step 4: Create new cluster
        new_cluster = EntityCluster(
            canonical_id=str(uuid4()),
            canonical_name=normalized,
            entity_type=entity_type,
            variants=[entity_text],
            source_documents=[document_id] if document_id else [],
            first_seen=datetime.now(),
            last_seen=datetime.now(),
            mention_count=1,
            confidence=confidence,
            embedding=entity_embedding
        )

        self._entity_cache[normalized] = new_cluster
        logger.debug(f"New cluster: '{entity_text}' -> '{normalized}'")

        return new_cluster

    def merge_clusters(
        self,
        cluster1_id: str,
        cluster2_id: str
    ) -> Optional[EntityCluster]:
        """Manually merge two entity clusters.

        Args:
            cluster1_id: ID of first cluster (will be primary)
            cluster2_id: ID of second cluster (will be merged in)

        Returns:
            Merged cluster or None if clusters not found
        """
        # Find clusters by ID
        cluster1 = None
        cluster2 = None

        for cluster in self._entity_cache.values():
            if cluster.canonical_id == cluster1_id:
                cluster1 = cluster
            elif cluster.canonical_id == cluster2_id:
                cluster2 = cluster

        if not cluster1 or not cluster2:
            logger.warning(f"Could not find clusters for merge: {cluster1_id}, {cluster2_id}")
            return None

        # Merge cluster2 into cluster1
        for variant in cluster2.variants:
            if variant not in cluster1.variants:
                cluster1.variants.append(variant)

        for doc_id in cluster2.source_documents:
            if doc_id not in cluster1.source_documents:
                cluster1.source_documents.append(doc_id)

        cluster1.mention_count += cluster2.mention_count

        # Use earliest first_seen
        if cluster2.first_seen < cluster1.first_seen:
            cluster1.first_seen = cluster2.first_seen

        # Use latest last_seen
        if cluster2.last_seen > cluster1.last_seen:
            cluster1.last_seen = cluster2.last_seen

        # Weighted average confidence
        total = cluster1.mention_count + cluster2.mention_count
        cluster1.confidence = (
            cluster1.confidence * cluster1.mention_count +
            cluster2.confidence * cluster2.mention_count
        ) / total

        # Remove cluster2 from cache
        to_remove = []
        for name, cluster in self._entity_cache.items():
            if cluster.canonical_id == cluster2_id:
                to_remove.append(name)

        for name in to_remove:
            # Point to merged cluster
            self._entity_cache[name] = cluster1

        logger.info(f"Merged cluster '{cluster2.canonical_name}' into '{cluster1.canonical_name}'")
        return cluster1

    def get_cluster(self, entity_text: str) -> Optional[EntityCluster]:
        """Get cluster for an entity text if it exists.

        Args:
            entity_text: Entity text to look up

        Returns:
            EntityCluster if found, None otherwise
        """
        normalized = self._normalize_name(entity_text)
        return self._entity_cache.get(normalized)

    def get_all_clusters(self) -> list[EntityCluster]:
        """Get all unique clusters.

        Returns:
            List of unique EntityCluster objects
        """
        # Use set to deduplicate by ID
        seen_ids = set()
        clusters = []

        for cluster in self._entity_cache.values():
            if cluster.canonical_id not in seen_ids:
                seen_ids.add(cluster.canonical_id)
                clusters.append(cluster)

        return clusters

    def get_clusters_by_type(self, entity_type: EntityType) -> list[EntityCluster]:
        """Get all clusters of a specific type.

        Args:
            entity_type: Type to filter by

        Returns:
            List of EntityCluster objects of the given type
        """
        return [
            c for c in self.get_all_clusters()
            if c.entity_type == entity_type
        ]

    def get_stats(self) -> dict:
        """Get deduplication statistics.

        Returns:
            Dict with cluster counts and statistics
        """
        clusters = self.get_all_clusters()

        type_counts = {}
        total_mentions = 0
        total_variants = 0

        for cluster in clusters:
            type_name = cluster.entity_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
            total_mentions += cluster.mention_count
            total_variants += len(cluster.variants)

        return {
            "total_clusters": len(clusters),
            "total_mentions": total_mentions,
            "total_variants": total_variants,
            "clusters_by_type": type_counts,
            "deduplication_ratio": total_mentions / max(1, len(clusters)),
        }

    def clear_cache(self):
        """Clear all cached clusters."""
        self._entity_cache.clear()
        self._embedding_cache.clear()


# Singleton instance
_deduplicator: Optional[EntityDeduplicator] = None


def get_entity_deduplicator() -> EntityDeduplicator:
    """Get the global entity deduplicator instance.

    Returns:
        EntityDeduplicator instance
    """
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = EntityDeduplicator()
    return _deduplicator


def deduplicate_entity(
    entity_text: str,
    entity_type: EntityType,
    document_id: str = ""
) -> EntityCluster:
    """Convenience function to deduplicate a single entity.

    Args:
        entity_text: Entity text
        entity_type: Type of entity
        document_id: Source document ID

    Returns:
        EntityCluster
    """
    deduplicator = get_entity_deduplicator()
    return deduplicator.deduplicate(entity_text, entity_type, document_id)
