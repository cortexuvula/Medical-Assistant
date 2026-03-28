"""Unit tests for rag.entity_deduplicator — cross-document entity deduplication."""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from rag.graph_data_provider import EntityType
from rag.entity_deduplicator import (
    EntityCluster,
    EntityDeduplicator,
    get_entity_deduplicator,
    deduplicate_entity,
)
import rag.entity_deduplicator as dedup_module


class TestEntityCluster(unittest.TestCase):

    def test_basic_creation(self):
        cluster = EntityCluster(
            canonical_id="id1",
            canonical_name="hypertension",
            entity_type=EntityType.CONDITION,
        )
        assert cluster.canonical_name == "hypertension"
        assert cluster.entity_type == EntityType.CONDITION

    def test_defaults(self):
        cluster = EntityCluster(
            canonical_id="id1",
            canonical_name="test",
            entity_type=EntityType.UNKNOWN,
        )
        assert cluster.variants == []
        assert cluster.source_documents == []
        assert cluster.mention_count == 1
        assert cluster.confidence == 1.0
        assert cluster.embedding is None

    def test_to_dict_serializes(self):
        cluster = EntityCluster(
            canonical_id="id1",
            canonical_name="aspirin",
            entity_type=EntityType.MEDICATION,
            variants=["Aspirin", "ASA"],
            source_documents=["doc1"],
            mention_count=3,
            confidence=0.9,
        )
        d = cluster.to_dict()
        assert d["canonical_id"] == "id1"
        assert d["entity_type"] == "medication"
        assert d["variants"] == ["Aspirin", "ASA"]
        assert d["mention_count"] == 3
        assert "embedding" not in d  # not serialized

    def test_to_dict_handles_timestamps(self):
        now = datetime(2025, 1, 1, 12, 0, 0)
        cluster = EntityCluster(
            canonical_id="id1",
            canonical_name="test",
            entity_type=EntityType.UNKNOWN,
            first_seen=now,
            last_seen=now,
        )
        d = cluster.to_dict()
        assert d["first_seen"] == now.isoformat()
        assert d["last_seen"] == now.isoformat()


class TestNormalizeName(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_lowercase(self):
        assert self.dedup._normalize_name("ASPIRIN") == "aspirin"

    def test_collapse_whitespace(self):
        assert self.dedup._normalize_name("  high   blood   pressure  ") == "high blood pressure"

    def test_expand_abbreviation(self):
        normalized = self.dedup._normalize_name("htn")
        assert normalized == "hypertension"

    def test_expand_multi_word_abbreviation(self):
        normalized = self.dedup._normalize_name("copd")
        assert "chronic obstructive pulmonary disease" in normalized

    def test_removes_noise_characters(self):
        normalized = self.dedup._normalize_name("aspirin (oral)")
        assert "(" not in normalized
        assert ")" not in normalized

    def test_keeps_hyphens_and_apostrophes(self):
        normalized = self.dedup._normalize_name("Crohn's disease")
        assert "'" in normalized
        normalized2 = self.dedup._normalize_name("beta-blocker")
        assert "-" in normalized2


class TestLevenshteinRatio(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_identical_strings(self):
        assert self.dedup._levenshtein_ratio("hello", "hello") == 1.0

    def test_empty_first_string(self):
        assert self.dedup._levenshtein_ratio("", "hello") == 0.0

    def test_empty_second_string(self):
        assert self.dedup._levenshtein_ratio("hello", "") == 0.0

    def test_both_empty(self):
        assert self.dedup._levenshtein_ratio("", "") == 0.0

    def test_similar_strings_high_ratio(self):
        ratio = self.dedup._levenshtein_ratio("aspirin", "aspirn")
        assert ratio > 0.8

    def test_completely_different_strings(self):
        ratio = self.dedup._levenshtein_ratio("abc", "xyz")
        assert ratio < 0.5

    def test_length_shortcut(self):
        ratio = self.dedup._levenshtein_ratio("a", "abcdefghij")
        assert ratio == 0.0


class TestCosineSimilarityDedup(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(self.dedup._cosine_similarity(v, v) - 1.0) < 1e-6

    def test_empty_vectors(self):
        assert self.dedup._cosine_similarity([], []) == 0.0

    def test_mismatched_lengths(self):
        assert self.dedup._cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_norm(self):
        assert self.dedup._cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


class TestDeduplicate(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_creates_new_cluster(self):
        cluster = self.dedup.deduplicate("Aspirin", EntityType.MEDICATION, "doc1")
        assert cluster.canonical_name == "aspirin"
        assert cluster.entity_type == EntityType.MEDICATION
        assert "Aspirin" in cluster.variants
        assert "doc1" in cluster.source_documents

    def test_exact_normalized_match_merges(self):
        c1 = self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        c2 = self.dedup.deduplicate("Aspirin", EntityType.MEDICATION, "doc2")
        assert c1.canonical_id == c2.canonical_id
        assert c2.mention_count == 2
        assert "doc2" in c2.source_documents

    def test_different_type_no_merge(self):
        c1 = self.dedup.deduplicate("test", EntityType.MEDICATION, "doc1")
        c2 = self.dedup.deduplicate("test", EntityType.LAB_TEST, "doc2")
        assert c1.canonical_id != c2.canonical_id

    def test_abbreviation_expansion_merge(self):
        c1 = self.dedup.deduplicate("hypertension", EntityType.CONDITION, "doc1")
        c2 = self.dedup.deduplicate("htn", EntityType.CONDITION, "doc2")
        assert c1.canonical_id == c2.canonical_id

    def test_fuzzy_match_merges(self):
        c1 = self.dedup.deduplicate("hypertension", EntityType.CONDITION, "doc1")
        c2 = self.dedup.deduplicate("hypertensio", EntityType.CONDITION, "doc2")
        ratio = self.dedup._levenshtein_ratio("hypertension", "hypertensio")
        if ratio >= 0.9:
            assert c1.canonical_id == c2.canonical_id

    def test_embedding_match_merges(self):
        mock_emb = Mock()
        mock_emb.generate_embedding.return_value = [1.0, 0.0, 0.0]
        dedup = EntityDeduplicator(embedding_manager=mock_emb)
        c1 = dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        c2 = dedup.deduplicate("acetylsalicylic acid", EntityType.MEDICATION, "doc2")
        # Both get same embedding, so cosine sim = 1.0 >= 0.85
        assert c1.canonical_id == c2.canonical_id

    def test_empty_document_id(self):
        cluster = self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "")
        assert cluster.source_documents == []

    def test_confidence_weighted_average(self):
        self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1", confidence=1.0)
        c2 = self.dedup.deduplicate("Aspirin", EntityType.MEDICATION, "doc2", confidence=0.5)
        assert c2.confidence < 1.0


class TestMergeClusters(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_merge_two_clusters(self):
        c1 = self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        c2 = self.dedup.deduplicate("ibuprofen", EntityType.MEDICATION, "doc2")
        merged = self.dedup.merge_clusters(c1.canonical_id, c2.canonical_id)
        assert merged is not None
        assert "ibuprofen" in merged.variants or "Ibuprofen" in [v.lower() for v in merged.variants]

    def test_merge_nonexistent_cluster_returns_none(self):
        self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        result = self.dedup.merge_clusters("fake-id-1", "fake-id-2")
        assert result is None

    def test_merge_preserves_earliest_first_seen(self):
        c1 = self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        c1.first_seen = datetime(2020, 1, 1)
        c2 = self.dedup.deduplicate("ibuprofen", EntityType.MEDICATION, "doc2")
        c2.first_seen = datetime(2019, 1, 1)
        merged = self.dedup.merge_clusters(c1.canonical_id, c2.canonical_id)
        assert merged.first_seen.year == 2019

    def test_merge_preserves_latest_last_seen(self):
        c1 = self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        c1.last_seen = datetime(2025, 6, 1)
        c2 = self.dedup.deduplicate("ibuprofen", EntityType.MEDICATION, "doc2")
        c2.last_seen = datetime(2025, 1, 1)
        merged = self.dedup.merge_clusters(c1.canonical_id, c2.canonical_id)
        assert merged.last_seen.year == 2025
        assert merged.last_seen.month == 6


class TestGetCluster(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_get_existing_cluster(self):
        self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        cluster = self.dedup.get_cluster("aspirin")
        assert cluster is not None
        assert cluster.canonical_name == "aspirin"

    def test_get_nonexistent_cluster(self):
        assert self.dedup.get_cluster("nonexistent") is None


class TestGetAllClusters(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_empty_deduplicator(self):
        assert self.dedup.get_all_clusters() == []

    def test_returns_unique_clusters(self):
        self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        self.dedup.deduplicate("Aspirin", EntityType.MEDICATION, "doc2")
        clusters = self.dedup.get_all_clusters()
        assert len(clusters) == 1

    def test_returns_multiple_distinct_clusters(self):
        self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        self.dedup.deduplicate("hypertension", EntityType.CONDITION, "doc2")
        clusters = self.dedup.get_all_clusters()
        assert len(clusters) == 2


class TestGetClustersByType(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_filter_by_type(self):
        self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        self.dedup.deduplicate("hypertension", EntityType.CONDITION, "doc2")
        meds = self.dedup.get_clusters_by_type(EntityType.MEDICATION)
        assert len(meds) == 1
        assert meds[0].entity_type == EntityType.MEDICATION


class TestGetStats(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_empty_stats(self):
        stats = self.dedup.get_stats()
        assert stats["total_clusters"] == 0
        assert stats["total_mentions"] == 0

    def test_stats_after_deduplication(self):
        self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        self.dedup.deduplicate("Aspirin", EntityType.MEDICATION, "doc2")
        stats = self.dedup.get_stats()
        assert stats["total_clusters"] == 1
        assert stats["total_mentions"] == 2
        assert stats["deduplication_ratio"] == 2.0


class TestClearCache(unittest.TestCase):

    def setUp(self):
        self.dedup = EntityDeduplicator()

    def test_clear_removes_all_clusters(self):
        self.dedup.deduplicate("aspirin", EntityType.MEDICATION, "doc1")
        self.dedup.clear_cache()
        assert self.dedup.get_all_clusters() == []


class TestSingletonDedup(unittest.TestCase):

    def tearDown(self):
        dedup_module._deduplicator = None

    def test_get_entity_deduplicator_creates_instance(self):
        d = get_entity_deduplicator()
        assert isinstance(d, EntityDeduplicator)

    def test_get_entity_deduplicator_returns_same(self):
        d1 = get_entity_deduplicator()
        d2 = get_entity_deduplicator()
        assert d1 is d2

    def test_deduplicate_entity_convenience(self):
        cluster = deduplicate_entity("aspirin", EntityType.MEDICATION, "doc1")
        assert cluster.canonical_name == "aspirin"


if __name__ == "__main__":
    unittest.main()
