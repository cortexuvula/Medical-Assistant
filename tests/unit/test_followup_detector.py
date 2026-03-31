"""
Tests for src/rag/followup_detector.py

Covers QueryIntent enum, FollowupResult.to_dict(), SemanticFollowupDetector
class constants, and all private methods (_compute_similarity,
_detect_coreference, _check_topic_overlap, _check_followup_patterns,
_has_clear_subject, _calculate_confidence, _determine_intent), plus
detect() integration, singleton, and the convenience function.
No network, no Tkinter, no embeddings from external services.
"""

import sys
import math
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import rag.followup_detector as fd_module
from rag.followup_detector import (
    QueryIntent,
    FollowupResult,
    SemanticFollowupDetector,
    get_followup_detector,
    detect_followup,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    fd_module._detector = None
    yield
    fd_module._detector = None


def _det() -> SemanticFollowupDetector:
    """Create a detector with no embedding manager."""
    return SemanticFollowupDetector(embedding_manager=None)


# ===========================================================================
# QueryIntent enum
# ===========================================================================

class TestQueryIntent:
    def test_new_topic_value(self):
        assert QueryIntent.NEW_TOPIC.value == "new_topic"

    def test_followup_value(self):
        assert QueryIntent.FOLLOWUP.value == "followup"

    def test_clarification_value(self):
        assert QueryIntent.CLARIFICATION.value == "clarification"

    def test_drill_down_value(self):
        assert QueryIntent.DRILL_DOWN.value == "drill_down"

    def test_comparison_value(self):
        assert QueryIntent.COMPARISON.value == "comparison"

    def test_related_value(self):
        assert QueryIntent.RELATED.value == "related"

    def test_total_members(self):
        assert len(list(QueryIntent)) == 6

    def test_is_str_enum(self):
        assert QueryIntent.NEW_TOPIC == "new_topic"


# ===========================================================================
# FollowupResult.to_dict
# ===========================================================================

class TestFollowupResultToDict:
    def _make(self, **kwargs) -> FollowupResult:
        defaults = dict(
            is_followup=True,
            confidence=0.75,
            intent=QueryIntent.FOLLOWUP,
            semantic_similarity=0.8,
            coreference_detected=True,
            topic_overlap_score=0.5,
            explanation="Test explanation",
        )
        defaults.update(kwargs)
        return FollowupResult(**defaults)

    def test_returns_dict(self):
        assert isinstance(self._make().to_dict(), dict)

    def test_is_followup_key_present(self):
        d = self._make(is_followup=True).to_dict()
        assert d["is_followup"] is True

    def test_confidence_key_present(self):
        d = self._make(confidence=0.9).to_dict()
        assert d["confidence"] == pytest.approx(0.9)

    def test_intent_serialized_as_string(self):
        d = self._make(intent=QueryIntent.CLARIFICATION).to_dict()
        assert d["intent"] == "clarification"

    def test_semantic_similarity_key_present(self):
        d = self._make(semantic_similarity=0.7).to_dict()
        assert d["semantic_similarity"] == pytest.approx(0.7)

    def test_coreference_detected_key_present(self):
        d = self._make(coreference_detected=False).to_dict()
        assert d["coreference_detected"] is False

    def test_topic_overlap_score_key_present(self):
        d = self._make(topic_overlap_score=0.4).to_dict()
        assert d["topic_overlap_score"] == pytest.approx(0.4)

    def test_explanation_key_present(self):
        d = self._make(explanation="My explanation").to_dict()
        assert d["explanation"] == "My explanation"

    def test_all_six_keys_present(self):
        d = self._make().to_dict()
        expected_keys = {
            "is_followup", "confidence", "intent",
            "semantic_similarity", "coreference_detected",
            "topic_overlap_score", "explanation"
        }
        assert expected_keys <= set(d.keys())


# ===========================================================================
# Class constants
# ===========================================================================

class TestClassConstants:
    def test_similarity_threshold(self):
        assert SemanticFollowupDetector.SIMILARITY_THRESHOLD == pytest.approx(0.65)

    def test_high_similarity_threshold(self):
        assert SemanticFollowupDetector.HIGH_SIMILARITY_THRESHOLD == pytest.approx(0.8)

    def test_min_confidence(self):
        assert SemanticFollowupDetector.MIN_CONFIDENCE == pytest.approx(0.5)

    def test_weight_sum_is_one(self):
        d = SemanticFollowupDetector
        total = d.WEIGHT_SEMANTIC + d.WEIGHT_COREFERENCE + d.WEIGHT_TOPIC_OVERLAP + d.WEIGHT_PATTERN
        assert abs(total - 1.0) < 1e-9

    def test_context_refs_is_frozenset(self):
        assert isinstance(SemanticFollowupDetector.CONTEXT_REFS, frozenset)

    def test_context_refs_contains_it(self):
        assert "it" in SemanticFollowupDetector.CONTEXT_REFS

    def test_context_refs_contains_this(self):
        assert "this" in SemanticFollowupDetector.CONTEXT_REFS

    def test_context_refs_contains_the_patient(self):
        assert "the patient" in SemanticFollowupDetector.CONTEXT_REFS

    def test_followup_patterns_is_list(self):
        assert isinstance(SemanticFollowupDetector.FOLLOWUP_PATTERNS, list)

    def test_followup_patterns_non_empty(self):
        assert len(SemanticFollowupDetector.FOLLOWUP_PATTERNS) > 0

    def test_question_starters_contains_what(self):
        assert "what" in SemanticFollowupDetector.QUESTION_STARTERS

    def test_question_starters_contains_how(self):
        assert "how" in SemanticFollowupDetector.QUESTION_STARTERS


# ===========================================================================
# _compute_similarity
# ===========================================================================

class TestComputeSimilarity:
    def setup_method(self):
        self.det = _det()

    def test_identical_vectors_returns_one(self):
        v = [1.0, 0.0, 0.0]
        result = self.det._compute_similarity(v, v)
        assert abs(result - 1.0) < 1e-6

    def test_orthogonal_vectors_returns_zero(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        result = self.det._compute_similarity(v1, v2)
        assert abs(result) < 1e-9

    def test_zero_vector_returns_zero(self):
        v1 = [0.0, 0.0]
        v2 = [1.0, 0.0]
        result = self.det._compute_similarity(v1, v2)
        assert result == 0.0

    def test_known_similarity(self):
        v1 = [1.0, 1.0]
        v2 = [1.0, 0.0]
        # cos(45°) = 1/sqrt(2) ≈ 0.7071
        result = self.det._compute_similarity(v1, v2)
        assert abs(result - math.sqrt(2) / 2) < 1e-6

    def test_returns_float(self):
        result = self.det._compute_similarity([1.0, 0.0], [0.5, 0.5])
        assert isinstance(result, float)

    def test_result_clamped_to_zero_to_one(self):
        # Should always return in [0, 1]
        v1 = [0.5, 0.5]
        v2 = [0.5, 0.5]
        result = self.det._compute_similarity(v1, v2)
        assert 0.0 <= result <= 1.0

    def test_same_direction_returns_high_value(self):
        v1 = [0.6, 0.8]
        v2 = [0.6, 0.8]
        result = self.det._compute_similarity(v1, v2)
        assert result > 0.95


# ===========================================================================
# _detect_coreference
# ===========================================================================

class TestDetectCoreference:
    def setup_method(self):
        self.det = _det()

    def test_it_pronoun_detected(self):
        assert self.det._detect_coreference("What does it do?") is True

    def test_this_pronoun_detected(self):
        assert self.det._detect_coreference("Is this effective?") is True

    def test_that_pronoun_detected(self):
        assert self.det._detect_coreference("How does that work?") is True

    def test_they_pronoun_detected(self):
        assert self.det._detect_coreference("Do they interact?") is True

    def test_the_patient_multiword_detected(self):
        assert self.det._detect_coreference("What about the patient?") is True

    def test_the_medication_multiword_detected(self):
        assert self.det._detect_coreference("Can the medication cause issues?") is True

    def test_the_same_pattern_detected(self):
        assert self.det._detect_coreference("Give the same dosage") is True

    def test_that_one_pattern_detected(self):
        assert self.det._detect_coreference("Use that one instead") is True

    def test_clear_query_not_detected(self):
        # No pronouns or patterns
        result = self.det._detect_coreference("What is the standard treatment for hypertension?")
        assert result is False

    def test_diabetes_treatment_query_not_detected(self):
        result = self.det._detect_coreference("What medications treat type 2 diabetes?")
        assert result is False

    def test_returns_bool(self):
        result = self.det._detect_coreference("What is aspirin?")
        assert isinstance(result, bool)


# ===========================================================================
# _check_topic_overlap
# ===========================================================================

class TestCheckTopicOverlap:
    def setup_method(self):
        self.det = _det()

    def test_no_previous_topics_returns_zero(self):
        result = self.det._check_topic_overlap("diabetes treatment", [])
        assert result == pytest.approx(0.0)

    def test_all_topics_mentioned_returns_one(self):
        result = self.det._check_topic_overlap(
            "diabetes hypertension treatment",
            ["diabetes", "hypertension"]
        )
        assert result == pytest.approx(1.0)

    def test_half_topics_mentioned_returns_half(self):
        result = self.det._check_topic_overlap(
            "diabetes treatment options",
            ["diabetes", "hypertension"]
        )
        assert result == pytest.approx(0.5)

    def test_no_topics_mentioned_returns_zero(self):
        result = self.det._check_topic_overlap(
            "what is the dosage",
            ["diabetes", "hypertension"]
        )
        assert result == pytest.approx(0.0)

    def test_multiword_topic_mentioned(self):
        result = self.det._check_topic_overlap(
            "heart failure treatment options",
            ["heart failure"]
        )
        assert result == pytest.approx(1.0)

    def test_multiword_topic_not_mentioned(self):
        result = self.det._check_topic_overlap(
            "diabetes management",
            ["heart failure"]
        )
        assert result == pytest.approx(0.0)

    def test_returns_float(self):
        result = self.det._check_topic_overlap("test", ["topic"])
        assert isinstance(result, float)

    def test_result_in_zero_to_one(self):
        result = self.det._check_topic_overlap("topic1 topic2", ["topic1"])
        assert 0.0 <= result <= 1.0


# ===========================================================================
# _check_followup_patterns
# ===========================================================================

class TestCheckFollowupPatterns:
    def setup_method(self):
        self.det = _det()

    def test_what_about_returns_related(self):
        result = self.det._check_followup_patterns("What about the dosage?")
        assert result == QueryIntent.RELATED

    def test_how_about_returns_related(self):
        result = self.det._check_followup_patterns("How about alternatives?")
        assert result == QueryIntent.RELATED

    def test_also_returns_related(self):
        result = self.det._check_followup_patterns("Also, what are the side effects?")
        assert result == QueryIntent.RELATED

    def test_and_what_returns_followup(self):
        result = self.det._check_followup_patterns("And what are the risks?")
        assert result == QueryIntent.FOLLOWUP

    def test_what_else_returns_drill_down(self):
        result = self.det._check_followup_patterns("What else should I know?")
        assert result == QueryIntent.DRILL_DOWN

    def test_tell_me_more_returns_drill_down(self):
        result = self.det._check_followup_patterns("Tell me more about this.")
        assert result == QueryIntent.DRILL_DOWN

    def test_more_about_returns_drill_down(self):
        result = self.det._check_followup_patterns("More about the treatment?")
        assert result == QueryIntent.DRILL_DOWN

    def test_explain_more_returns_clarification(self):
        result = self.det._check_followup_patterns("Explain more about this.")
        assert result == QueryIntent.CLARIFICATION

    def test_why_is_returns_clarification(self):
        result = self.det._check_followup_patterns("Why is this the first-line treatment?")
        assert result == QueryIntent.CLARIFICATION

    def test_compared_to_returns_comparison(self):
        result = self.det._check_followup_patterns("Compared to lisinopril, which is better?")
        assert result == QueryIntent.COMPARISON

    def test_versus_returns_comparison(self):
        result = self.det._check_followup_patterns("Versus metoprolol, what are differences?")
        assert result == QueryIntent.COMPARISON

    def test_side_effects_query_returns_drill_down(self):
        result = self.det._check_followup_patterns("What are the side effects of aspirin?")
        assert result == QueryIntent.DRILL_DOWN

    def test_new_topic_returns_none(self):
        result = self.det._check_followup_patterns("What is hypertension?")
        assert result is None

    def test_plain_question_returns_none(self):
        result = self.det._check_followup_patterns("Describe heart failure management.")
        assert result is None


# ===========================================================================
# _calculate_confidence
# ===========================================================================

class TestCalculateConfidence:
    def setup_method(self):
        self.det = _det()

    def _signals(self, **kwargs):
        base = {
            'semantic_similarity': 0.0,
            'coreference': False,
            'topic_overlap': 0.0,
            'pattern_match': None,
        }
        base.update(kwargs)
        return base

    def test_all_zero_returns_zero(self):
        result = self.det._calculate_confidence(self._signals())
        assert result == pytest.approx(0.0)

    def test_coreference_only_gives_weight(self):
        result = self.det._calculate_confidence(self._signals(coreference=True))
        expected = SemanticFollowupDetector.WEIGHT_COREFERENCE
        assert result >= expected

    def test_pattern_match_gives_weight(self):
        result = self.det._calculate_confidence(
            self._signals(pattern_match=QueryIntent.FOLLOWUP)
        )
        expected = SemanticFollowupDetector.WEIGHT_PATTERN
        assert result >= expected

    def test_semantic_similarity_full_gives_weight(self):
        result = self.det._calculate_confidence(self._signals(semantic_similarity=1.0))
        expected = SemanticFollowupDetector.WEIGHT_SEMANTIC
        assert result >= expected

    def test_multiple_signals_boost_applied(self):
        # 3 signals → boost factor 1.2
        no_boost = self.det._calculate_confidence(self._signals(
            semantic_similarity=SemanticFollowupDetector.SIMILARITY_THRESHOLD,
            coreference=True,
        ))
        with_boost = self.det._calculate_confidence(self._signals(
            semantic_similarity=SemanticFollowupDetector.SIMILARITY_THRESHOLD,
            coreference=True,
            topic_overlap=0.5,
            pattern_match=QueryIntent.FOLLOWUP,
        ))
        assert with_boost >= no_boost

    def test_confidence_never_exceeds_one(self):
        result = self.det._calculate_confidence(self._signals(
            semantic_similarity=1.0,
            coreference=True,
            topic_overlap=1.0,
            pattern_match=QueryIntent.FOLLOWUP,
        ))
        assert result <= 1.0

    def test_returns_float(self):
        result = self.det._calculate_confidence(self._signals())
        assert isinstance(result, float)


# ===========================================================================
# _determine_intent
# ===========================================================================

class TestDetermineIntent:
    def setup_method(self):
        self.det = _det()

    def _signals(self, **kwargs):
        base = {
            'semantic_similarity': 0.0,
            'coreference': False,
            'topic_overlap': 0.0,
            'pattern_match': None,
        }
        base.update(kwargs)
        return base

    def test_pattern_match_takes_priority(self):
        result = self.det._determine_intent(
            self._signals(pattern_match=QueryIntent.COMPARISON),
            "vs something",
        )
        assert result == QueryIntent.COMPARISON

    def test_high_similarity_with_clarification_words(self):
        result = self.det._determine_intent(
            self._signals(semantic_similarity=0.9),
            "why is this the standard treatment?",
        )
        assert result == QueryIntent.CLARIFICATION

    def test_high_similarity_no_clarification_is_followup(self):
        result = self.det._determine_intent(
            self._signals(semantic_similarity=0.9),
            "what are the dosages?",
        )
        assert result == QueryIntent.FOLLOWUP

    def test_coreference_with_drill_indicators(self):
        result = self.det._determine_intent(
            self._signals(coreference=True),
            "are there any other options?",
        )
        assert result == QueryIntent.DRILL_DOWN

    def test_coreference_without_drill_is_followup(self):
        result = self.det._determine_intent(
            self._signals(coreference=True),
            "what is it used for?",
        )
        assert result == QueryIntent.FOLLOWUP

    def test_topic_overlap_with_compare_words(self):
        result = self.det._determine_intent(
            self._signals(topic_overlap=0.5),
            "diabetes versus pre-diabetes management",
        )
        assert result == QueryIntent.COMPARISON

    def test_topic_overlap_without_compare_is_related(self):
        result = self.det._determine_intent(
            self._signals(topic_overlap=0.5),
            "diabetes treatment options",
        )
        assert result == QueryIntent.RELATED

    def test_default_no_signals_is_new_topic(self):
        result = self.det._determine_intent(
            self._signals(),
            "what is the capital of France?",
        )
        assert result == QueryIntent.NEW_TOPIC


# ===========================================================================
# detect() integration
# ===========================================================================

class TestDetect:
    def setup_method(self):
        self.det = _det()

    def test_no_previous_context_returns_new_topic(self):
        result = self.det.detect("What is hypertension?")
        assert result.intent == QueryIntent.NEW_TOPIC
        assert result.is_followup is False

    def test_no_previous_context_confidence_high(self):
        result = self.det.detect("What is hypertension?")
        assert result.confidence == pytest.approx(1.0)

    def test_no_previous_context_semantic_similarity_zero(self):
        result = self.det.detect("What is hypertension?")
        assert result.semantic_similarity == pytest.approx(0.0)

    def test_returns_followup_result(self):
        result = self.det.detect("What is hypertension?")
        assert isinstance(result, FollowupResult)

    def test_with_pronoun_detects_coreference(self):
        result = self.det.detect("What does it do?", previous_query="Tell me about aspirin")
        assert result.coreference_detected is True

    def test_with_followup_pattern_sets_related_intent(self):
        result = self.det.detect(
            "What about the side effects?",
            previous_query="Tell me about aspirin"
        )
        # "What about..." matches RELATED pattern; intent reflects this
        assert result.intent == QueryIntent.RELATED

    def test_with_topic_overlap_detects_overlap(self):
        result = self.det.detect(
            "diabetes management options",
            previous_query="diabetes treatment",
            previous_topics=["diabetes"],
        )
        assert result.topic_overlap_score > 0.0

    def test_with_embeddings_computes_similarity(self):
        embedding = [1.0, 0.0, 0.0]
        result = self.det.detect(
            "diabetes treatment",
            previous_query="diabetes",
            current_embedding=embedding,
            previous_embedding=embedding,
        )
        assert result.semantic_similarity == pytest.approx(1.0)

    def test_explanation_is_non_empty_string(self):
        result = self.det.detect("What is aspirin?")
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0


# ===========================================================================
# Singleton and convenience function
# ===========================================================================

class TestSingletonAndConvenience:
    def test_get_detector_returns_instance(self):
        d = get_followup_detector()
        assert isinstance(d, SemanticFollowupDetector)

    def test_get_detector_same_instance_twice(self):
        d1 = get_followup_detector()
        d2 = get_followup_detector()
        assert d1 is d2

    def test_reset_clears_singleton(self):
        d1 = get_followup_detector()
        fd_module._detector = None
        d2 = get_followup_detector()
        assert d1 is not d2

    def test_detect_followup_returns_followup_result(self):
        result = detect_followup("What is hypertension?")
        assert isinstance(result, FollowupResult)

    def test_detect_followup_no_context_is_new_topic(self):
        result = detect_followup("What is aspirin?")
        assert result.intent == QueryIntent.NEW_TOPIC

    def test_detect_followup_with_pronoun_detects_coreference(self):
        result = detect_followup("What does it do?", previous_query="Tell me about aspirin")
        assert result.coreference_detected is True
