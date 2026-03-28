"""Unit tests for rag.entity_classifier — ML-based entity classification."""

import unittest
from unittest.mock import Mock, patch, MagicMock

from rag.graph_data_provider import EntityType
from rag.entity_classifier import (
    ClassificationResult,
    MLEntityClassifier,
    get_entity_classifier,
    classify_entity,
)
import rag.entity_classifier as entity_classifier_module


class TestClassificationResult(unittest.TestCase):

    def test_basic_creation(self):
        result = ClassificationResult(
            entity_text="aspirin",
            predicted_type=EntityType.MEDICATION,
            confidence=0.9,
        )
        assert result.entity_text == "aspirin"
        assert result.predicted_type == EntityType.MEDICATION
        assert result.confidence == 0.9

    def test_defaults(self):
        result = ClassificationResult(
            entity_text="test",
            predicted_type=EntityType.UNKNOWN,
            confidence=0.5,
        )
        assert result.alternative_types == []
        assert result.context_used == ""

    def test_alternative_types(self):
        alts = [(EntityType.CONDITION, 0.7), (EntityType.SYMPTOM, 0.3)]
        result = ClassificationResult(
            entity_text="pain",
            predicted_type=EntityType.SYMPTOM,
            confidence=0.8,
            alternative_types=alts,
        )
        assert len(result.alternative_types) == 2
        assert result.alternative_types[0][0] == EntityType.CONDITION


class TestCheckAbbreviation(unittest.TestCase):

    def setUp(self):
        self.classifier = MLEntityClassifier()

    def test_known_condition_abbreviation(self):
        assert self.classifier._check_abbreviation("htn") == EntityType.CONDITION

    def test_known_lab_abbreviation(self):
        assert self.classifier._check_abbreviation("cbc") == EntityType.LAB_TEST

    def test_known_procedure_abbreviation(self):
        assert self.classifier._check_abbreviation("mri") == EntityType.PROCEDURE

    def test_case_insensitive(self):
        assert self.classifier._check_abbreviation("HTN") == EntityType.CONDITION

    def test_strips_whitespace(self):
        assert self.classifier._check_abbreviation("  copd  ") == EntityType.CONDITION

    def test_unknown_abbreviation_returns_none(self):
        assert self.classifier._check_abbreviation("xyz") is None


class TestGetKeywordScore(unittest.TestCase):

    def setUp(self):
        self.classifier = MLEntityClassifier()

    def test_no_keywords_for_unknown_type(self):
        score = self.classifier._get_keyword_score("aspirin", EntityType.UNKNOWN)
        assert score == 0.0

    def test_medication_keywords_match(self):
        score = self.classifier._get_keyword_score(
            "aspirin 100mg tablet oral dose", EntityType.MEDICATION
        )
        assert score > 0.0

    def test_no_match_returns_zero(self):
        score = self.classifier._get_keyword_score(
            "something completely unrelated", EntityType.MEDICATION
        )
        assert score == 0.0

    def test_score_capped_at_one(self):
        text = " ".join(MLEntityClassifier.TYPE_KEYWORDS[EntityType.MEDICATION])
        score = self.classifier._get_keyword_score(text, EntityType.MEDICATION)
        assert score <= 1.0


class TestCosineSimilarity(unittest.TestCase):

    def setUp(self):
        self.classifier = MLEntityClassifier()

    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        sim = self.classifier._cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        sim = self.classifier._cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert abs(sim) < 1e-6

    def test_empty_vectors(self):
        assert self.classifier._cosine_similarity([], []) == 0.0

    def test_mismatched_lengths(self):
        assert self.classifier._cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_norm_vector(self):
        assert self.classifier._cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


class TestClassify(unittest.TestCase):

    def setUp(self):
        self.classifier = MLEntityClassifier()

    def test_abbreviation_returns_high_confidence(self):
        result = self.classifier.classify("HTN")
        assert result.predicted_type == EntityType.CONDITION
        assert result.confidence == 0.95

    def test_abbreviation_context_truncated(self):
        long_context = "a" * 200
        result = self.classifier.classify("cbc", context=long_context)
        assert len(result.context_used) <= 100

    def test_keyword_based_classification(self):
        result = self.classifier.classify(
            "metformin", context="prescribed medication tablet 500mg dose daily oral"
        )
        assert result.predicted_type == EntityType.MEDICATION

    def test_confidence_capped_at_095(self):
        result = self.classifier.classify("htn")
        assert result.confidence <= 0.95

    def test_fallback_on_no_match(self):
        result = self.classifier.classify("xyzzy")
        assert result.confidence == 0.3

    def test_embedding_combined_scoring(self):
        mock_emb = Mock()
        mock_emb.generate_embedding.return_value = [1.0, 0.0, 0.0]
        classifier = MLEntityClassifier(embedding_manager=mock_emb)
        classifier._type_prototypes = {EntityType.MEDICATION: [1.0, 0.0, 0.0]}
        classifier._prototypes_loaded = True

        result = classifier.classify("aspirin")
        assert result.predicted_type == EntityType.MEDICATION
        assert result.confidence > 0.0


class TestClassifyBatch(unittest.TestCase):

    def setUp(self):
        self.classifier = MLEntityClassifier()

    def test_batch_returns_correct_count(self):
        entities = [("htn", ""), ("cbc", ""), ("mri", "")]
        results = self.classifier.classify_batch(entities)
        assert len(results) == 3

    def test_batch_preserves_order(self):
        entities = [("htn", ""), ("cbc", "")]
        results = self.classifier.classify_batch(entities)
        assert results[0].predicted_type == EntityType.CONDITION
        assert results[1].predicted_type == EntityType.LAB_TEST


class TestGetTypeConfidence(unittest.TestCase):

    def setUp(self):
        self.classifier = MLEntityClassifier()

    def test_matching_type_returns_confidence(self):
        conf = self.classifier.get_type_confidence("htn", EntityType.CONDITION)
        assert conf == 0.95

    def test_non_matching_type_returns_zero(self):
        conf = self.classifier.get_type_confidence("htn", EntityType.MEDICATION)
        assert conf == 0.0


class TestSingleton(unittest.TestCase):

    def tearDown(self):
        entity_classifier_module._classifier = None

    def test_get_entity_classifier_creates_instance(self):
        c = get_entity_classifier()
        assert isinstance(c, MLEntityClassifier)

    def test_get_entity_classifier_returns_same_instance(self):
        c1 = get_entity_classifier()
        c2 = get_entity_classifier()
        assert c1 is c2

    def test_classify_entity_convenience(self):
        result = classify_entity("htn")
        assert result.predicted_type == EntityType.CONDITION


if __name__ == "__main__":
    unittest.main()
