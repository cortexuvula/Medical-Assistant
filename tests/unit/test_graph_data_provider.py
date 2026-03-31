"""
Tests for pure-logic classes in src/rag/graph_data_provider.py.

No Neo4j, no network, no external services required.
Covers: EntityType, GraphNode, GraphEdge, RelationshipConfidenceCalculator, GraphData.
"""

import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, "src")

from rag.graph_data_provider import (
    EntityType,
    GraphNode,
    GraphEdge,
    RelationshipConfidenceCalculator,
    GraphData,
)


# ---------------------------------------------------------------------------
# EntityType.from_string – direct matching
# ---------------------------------------------------------------------------

class TestEntityTypeFromStringDirect:
    """Direct (exact) matches, case-insensitive, whitespace-stripped."""

    def test_empty_string_returns_unknown(self):
        assert EntityType.from_string("") == EntityType.UNKNOWN

    def test_medication_lowercase(self):
        assert EntityType.from_string("medication") == EntityType.MEDICATION

    def test_condition_lowercase(self):
        assert EntityType.from_string("condition") == EntityType.CONDITION

    def test_symptom_lowercase(self):
        assert EntityType.from_string("symptom") == EntityType.SYMPTOM

    def test_procedure_lowercase(self):
        assert EntityType.from_string("procedure") == EntityType.PROCEDURE

    def test_lab_test_lowercase(self):
        assert EntityType.from_string("lab_test") == EntityType.LAB_TEST

    def test_anatomy_lowercase(self):
        assert EntityType.from_string("anatomy") == EntityType.ANATOMY

    def test_document_lowercase(self):
        assert EntityType.from_string("document") == EntityType.DOCUMENT

    def test_episode_lowercase(self):
        assert EntityType.from_string("episode") == EntityType.EPISODE

    def test_unknown_lowercase(self):
        assert EntityType.from_string("unknown") == EntityType.UNKNOWN

    def test_entity_lowercase(self):
        assert EntityType.from_string("entity") == EntityType.ENTITY

    def test_medication_uppercase(self):
        assert EntityType.from_string("MEDICATION") == EntityType.MEDICATION

    def test_condition_mixed_case(self):
        assert EntityType.from_string("Condition") == EntityType.CONDITION

    def test_whitespace_stripped_condition(self):
        assert EntityType.from_string("  condition  ") == EntityType.CONDITION

    def test_whitespace_stripped_medication_upper(self):
        assert EntityType.from_string("  MEDICATION  ") == EntityType.MEDICATION

    def test_symptom_uppercase(self):
        assert EntityType.from_string("SYMPTOM") == EntityType.SYMPTOM

    def test_procedure_uppercase(self):
        assert EntityType.from_string("PROCEDURE") == EntityType.PROCEDURE

    def test_lab_test_uppercase(self):
        assert EntityType.from_string("LAB_TEST") == EntityType.LAB_TEST

    def test_anatomy_uppercase(self):
        assert EntityType.from_string("ANATOMY") == EntityType.ANATOMY

    def test_document_uppercase(self):
        assert EntityType.from_string("DOCUMENT") == EntityType.DOCUMENT

    def test_episode_uppercase(self):
        assert EntityType.from_string("EPISODE") == EntityType.EPISODE

    def test_entity_uppercase(self):
        assert EntityType.from_string("ENTITY") == EntityType.ENTITY


# ---------------------------------------------------------------------------
# EntityType.from_string – fuzzy matching
# ---------------------------------------------------------------------------

class TestEntityTypeFromStringFuzzy:
    """Fuzzy key-in-value matches."""

    def test_drug_maps_to_medication(self):
        assert EntityType.from_string("drug") == EntityType.MEDICATION

    def test_medicine_maps_to_medication(self):
        assert EntityType.from_string("medicine") == EntityType.MEDICATION

    def test_pharmaceutical_maps_to_medication(self):
        assert EntityType.from_string("pharmaceutical") == EntityType.MEDICATION

    def test_disease_maps_to_condition(self):
        assert EntityType.from_string("disease") == EntityType.CONDITION

    def test_diagnosis_maps_to_condition(self):
        assert EntityType.from_string("diagnosis") == EntityType.CONDITION

    def test_disorder_maps_to_condition(self):
        assert EntityType.from_string("disorder") == EntityType.CONDITION

    def test_illness_maps_to_condition(self):
        assert EntityType.from_string("illness") == EntityType.CONDITION

    def test_sign_maps_to_symptom(self):
        assert EntityType.from_string("sign") == EntityType.SYMPTOM

    def test_finding_maps_to_symptom(self):
        # "finding" is a key in the fuzzy mapping dict → SYMPTOM
        assert EntityType.from_string("finding") == EntityType.SYMPTOM

    def test_surgery_maps_to_procedure(self):
        assert EntityType.from_string("surgery") == EntityType.PROCEDURE

    def test_operation_maps_to_procedure(self):
        assert EntityType.from_string("operation") == EntityType.PROCEDURE

    def test_treatment_maps_to_procedure(self):
        assert EntityType.from_string("treatment") == EntityType.PROCEDURE

    def test_test_maps_to_lab_test(self):
        assert EntityType.from_string("test") == EntityType.LAB_TEST

    def test_lab_maps_to_lab_test(self):
        assert EntityType.from_string("lab") == EntityType.LAB_TEST

    def test_organ_maps_to_anatomy(self):
        assert EntityType.from_string("organ") == EntityType.ANATOMY

    def test_body_part_maps_to_anatomy(self):
        assert EntityType.from_string("body_part") == EntityType.ANATOMY

    def test_doc_maps_to_document(self):
        assert EntityType.from_string("doc") == EntityType.DOCUMENT

    def test_event_maps_to_episode(self):
        assert EntityType.from_string("event") == EntityType.EPISODE

    def test_completely_random_returns_unknown(self):
        assert EntityType.from_string("completelyrandom") == EntityType.UNKNOWN

    def test_fuzzy_substring_drug_in_longer_word(self):
        # "antidrug" contains "drug" → MEDICATION
        assert EntityType.from_string("antidrug") == EntityType.MEDICATION

    def test_fuzzy_disease_in_longer_word(self):
        # "predisease" contains "disease" → CONDITION
        assert EntityType.from_string("predisease") == EntityType.CONDITION

    def test_completely_unknown_string(self):
        assert EntityType.from_string("xyz123") == EntityType.UNKNOWN

    def test_presentation_maps_to_symptom(self):
        assert EntityType.from_string("presentation") == EntityType.SYMPTOM

    def test_intervention_maps_to_procedure(self):
        assert EntityType.from_string("intervention") == EntityType.PROCEDURE

    def test_laboratory_maps_to_lab_test(self):
        assert EntityType.from_string("laboratory") == EntityType.LAB_TEST

    def test_structure_maps_to_anatomy(self):
        assert EntityType.from_string("structure") == EntityType.ANATOMY

    def test_file_maps_to_document(self):
        assert EntityType.from_string("file") == EntityType.DOCUMENT

    def test_source_maps_to_document(self):
        assert EntityType.from_string("source") == EntityType.DOCUMENT

    def test_episodic_maps_to_episode(self):
        assert EntityType.from_string("episodic") == EntityType.EPISODE

    def test_biomarker_maps_to_lab_test(self):
        assert EntityType.from_string("biomarker") == EntityType.LAB_TEST


# ---------------------------------------------------------------------------
# GraphNode – display_name
# ---------------------------------------------------------------------------

class TestGraphNodeDisplayName:
    """display_name property: truncates only when len(name) > 30."""

    def _make_node(self, name: str) -> GraphNode:
        return GraphNode(id="n1", name=name, entity_type=EntityType.MEDICATION)

    def test_short_name_unchanged(self):
        node = self._make_node("Aspirin")
        assert node.display_name == "Aspirin"

    def test_exactly_30_chars_not_truncated(self):
        name = "A" * 30  # exactly 30, NOT > 30
        node = self._make_node(name)
        assert node.display_name == name
        assert len(node.display_name) == 30

    def test_31_chars_truncated_to_27_plus_ellipsis(self):
        name = "B" * 31
        node = self._make_node(name)
        assert node.display_name == "B" * 27 + "..."
        assert len(node.display_name) == 30

    def test_100_chars_truncated_to_27_plus_ellipsis(self):
        name = "C" * 100
        node = self._make_node(name)
        assert node.display_name == "C" * 27 + "..."

    def test_empty_name_unchanged(self):
        node = self._make_node("")
        assert node.display_name == ""

    def test_29_chars_unchanged(self):
        name = "D" * 29
        node = self._make_node(name)
        assert node.display_name == name

    def test_truncated_name_ends_with_ellipsis(self):
        node = self._make_node("X" * 50)
        assert node.display_name.endswith("...")

    def test_truncated_name_total_length_is_30(self):
        node = self._make_node("Y" * 50)
        assert len(node.display_name) == 30


# ---------------------------------------------------------------------------
# GraphNode – matches_search
# ---------------------------------------------------------------------------

class TestGraphNodeMatchesSearch:
    """matches_search method."""

    def _make_node(self, name="Aspirin", entity_type=EntityType.MEDICATION, properties=None):
        return GraphNode(
            id="n1",
            name=name,
            entity_type=entity_type,
            properties=properties or {},
        )

    def test_query_in_name_case_insensitive(self):
        node = self._make_node(name="Aspirin")
        assert node.matches_search("aspirin") is True

    def test_query_in_name_mixed_case(self):
        node = self._make_node(name="Aspirin")
        assert node.matches_search("ASPIRIN") is True

    def test_partial_query_in_name(self):
        node = self._make_node(name="Aspirin")
        assert node.matches_search("spir") is True

    def test_query_in_entity_type_value(self):
        node = self._make_node(entity_type=EntityType.MEDICATION)
        assert node.matches_search("medication") is True

    def test_query_in_entity_type_partial(self):
        node = self._make_node(entity_type=EntityType.CONDITION)
        assert node.matches_search("condit") is True

    def test_query_in_property_value(self):
        node = self._make_node(properties={"icd_code": "J45.0"})
        assert node.matches_search("J45") is True

    def test_query_not_matching_returns_false(self):
        node = self._make_node(name="Aspirin", entity_type=EntityType.MEDICATION)
        assert node.matches_search("zzznomatch") is False

    def test_empty_query_matches_everything(self):
        # empty query_lower "" is always in any string
        node = self._make_node(name="Anything")
        assert node.matches_search("") is True

    def test_case_insensitive_property_match(self):
        node = self._make_node(properties={"description": "HeartDisease"})
        assert node.matches_search("heartdisease") is True

    def test_no_properties_no_match(self):
        node = self._make_node(name="Aspirin", properties={})
        assert node.matches_search("ibuprofen") is False

    def test_numeric_property_value_match(self):
        node = self._make_node(properties={"dosage": 500})
        assert node.matches_search("500") is True


# ---------------------------------------------------------------------------
# GraphEdge – display_type
# ---------------------------------------------------------------------------

class TestGraphEdgeDisplayType:
    """display_type converts SCREAMING_SNAKE_CASE to Title Case."""

    def _make_edge(self, rel_type: str) -> GraphEdge:
        return GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type=rel_type)

    def test_treats_condition(self):
        assert self._make_edge("TREATS_CONDITION").display_type == "Treats Condition"

    def test_interacts_with(self):
        assert self._make_edge("INTERACTS_WITH").display_type == "Interacts With"

    def test_causes(self):
        assert self._make_edge("CAUSES").display_type == "Causes"

    def test_single_word_uppercased(self):
        assert self._make_edge("TREATS").display_type == "Treats"

    def test_three_word_relationship(self):
        assert self._make_edge("A_B_C").display_type == "A B C"

    def test_lowercase_input_titlecased(self):
        assert self._make_edge("treats_condition").display_type == "Treats Condition"


# ---------------------------------------------------------------------------
# GraphEdge – reliability_score
# ---------------------------------------------------------------------------

class TestGraphEdgeReliabilityScore:
    """reliability_score property formula verification."""

    def test_default_values_score(self):
        # confidence=1.0, evidence_count=1, no last_seen
        # evidence_factor = min(1.0, 1/3) = 0.3333
        # recency_factor = 0.5
        # score = 1.0 * (0.5 + 0.3 * 0.3333 + 0.2 * 0.5) = 0.5 + 0.1 + 0.1 = 0.7
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X")
        assert edge.reliability_score == pytest.approx(0.7, abs=1e-6)

    def test_evidence_count_3_no_last_seen(self):
        # evidence_factor = min(1.0, 3/3) = 1.0
        # recency_factor = 0.5
        # score = 1.0 * (0.5 + 0.3 * 1.0 + 0.2 * 0.5) = 0.9
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X",
                         evidence_count=3)
        assert edge.reliability_score == pytest.approx(0.9, abs=1e-6)

    def test_evidence_count_6_capped_at_1(self):
        # evidence_factor = min(1.0, 6/3) = 1.0 (capped)
        # same as evidence_count=3 when no last_seen
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X",
                         evidence_count=6)
        assert edge.reliability_score == pytest.approx(0.9, abs=1e-6)

    def test_last_seen_now_recency_factor_1(self):
        # days_old ~ 0, recency_factor = max(0.5, 1.0) = 1.0
        # evidence_factor = 1/3
        # score = 1.0 * (0.5 + 0.3*(1/3) + 0.2*1.0)
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X",
                         last_seen=datetime.now())
        expected = 1.0 * (0.5 + 0.3 * (1 / 3) + 0.2 * 1.0)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-4)

    def test_last_seen_one_year_ago_recency_factor_half(self):
        # days_old ~365, recency_factor = max(0.5, 1.0 - 365/365) = max(0.5, 0.0) = 0.5
        # same as no last_seen
        one_year_ago = datetime.now() - timedelta(days=365)
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X",
                         last_seen=one_year_ago)
        expected = 1.0 * (0.5 + 0.3 * (1 / 3) + 0.2 * 0.5)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-4)

    def test_last_seen_half_year_ago(self):
        # days_old = 182, recency_factor = max(0.5, 1.0 - 182/365) ≈ max(0.5, 0.501)
        half_year_ago = datetime.now() - timedelta(days=182)
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X",
                         last_seen=half_year_ago)
        days_old = (datetime.now() - half_year_ago).days
        recency = max(0.5, 1.0 - days_old / 365)
        expected = 1.0 * (0.5 + 0.3 * (1 / 3) + 0.2 * recency)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-3)

    def test_confidence_half_scales_score(self):
        # confidence=0.5, evidence_count=1, no last_seen → score = 0.5 * 0.7 = 0.35
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X",
                         confidence=0.5)
        expected = 0.5 * (0.5 + 0.3 * (1 / 3) + 0.2 * 0.5)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-6)

    def test_evidence_count_2_no_last_seen(self):
        # evidence_factor = min(1.0, 2/3) = 0.6667
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X",
                         evidence_count=2)
        expected = 1.0 * (0.5 + 0.3 * (2 / 3) + 0.2 * 0.5)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# GraphEdge – to_dict
# ---------------------------------------------------------------------------

class TestGraphEdgeToDict:
    """to_dict serialisation."""

    def _make_edge(self, **kwargs) -> GraphEdge:
        defaults = dict(id="e1", source_id="n1", target_id="n2",
                        relationship_type="TREATS")
        defaults.update(kwargs)
        return GraphEdge(**defaults)

    def test_required_keys_present(self):
        d = self._make_edge().to_dict()
        for key in ("id", "source_id", "target_id", "relationship_type",
                    "fact", "confidence", "evidence_count",
                    "reliability_score", "evidence_type"):
            assert key in d

    def test_id_value(self):
        assert self._make_edge().to_dict()["id"] == "e1"

    def test_source_id_value(self):
        assert self._make_edge().to_dict()["source_id"] == "n1"

    def test_target_id_value(self):
        assert self._make_edge().to_dict()["target_id"] == "n2"

    def test_relationship_type_value(self):
        assert self._make_edge().to_dict()["relationship_type"] == "TREATS"

    def test_first_seen_none_when_not_set(self):
        assert self._make_edge().to_dict()["first_seen"] is None

    def test_last_seen_none_when_not_set(self):
        assert self._make_edge().to_dict()["last_seen"] is None

    def test_first_seen_iso_string_when_set(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        d = self._make_edge(first_seen=dt).to_dict()
        assert d["first_seen"] == dt.isoformat()

    def test_last_seen_iso_string_when_set(self):
        dt = datetime(2024, 6, 1, 8, 0, 0)
        d = self._make_edge(last_seen=dt).to_dict()
        assert d["last_seen"] == dt.isoformat()

    def test_reliability_score_is_float(self):
        d = self._make_edge().to_dict()
        assert isinstance(d["reliability_score"], float)

    def test_confidence_in_dict(self):
        d = self._make_edge(confidence=0.8).to_dict()
        assert d["confidence"] == pytest.approx(0.8)

    def test_evidence_count_in_dict(self):
        d = self._make_edge(evidence_count=5).to_dict()
        assert d["evidence_count"] == 5

    def test_evidence_type_in_dict(self):
        d = self._make_edge(evidence_type="explicit").to_dict()
        assert d["evidence_type"] == "explicit"

    def test_fact_in_dict(self):
        d = self._make_edge(fact="Drug reduces fever").to_dict()
        assert d["fact"] == "Drug reduces fever"


# ---------------------------------------------------------------------------
# RelationshipConfidenceCalculator – calculate_confidence
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    """RelationshipConfidenceCalculator.calculate_confidence."""

    def setup_method(self):
        self.calc = RelationshipConfidenceCalculator()

    def test_explicit_base_confidence(self):
        # non-HIGH_EVIDENCE type, 0 evidence, empty text → base 0.95
        result = self.calc.calculate_confidence("relates_to", "", "explicit", 0)
        assert result == pytest.approx(0.95, abs=1e-9)

    def test_inferred_base_confidence(self):
        result = self.calc.calculate_confidence("relates_to", "", "inferred", 0)
        assert result == pytest.approx(0.70, abs=1e-9)

    def test_aggregated_base_confidence(self):
        result = self.calc.calculate_confidence("relates_to", "", "aggregated", 0)
        assert result == pytest.approx(0.85, abs=1e-9)

    def test_user_validated_base_confidence(self):
        result = self.calc.calculate_confidence("relates_to", "", "user_validated", 0)
        assert result == pytest.approx(0.99, abs=1e-9)

    def test_unknown_method_base_confidence(self):
        result = self.calc.calculate_confidence("relates_to", "", "unknown_method", 0)
        assert result == pytest.approx(0.5, abs=1e-9)

    def test_evidence_boost_added(self):
        # 2 evidence → boost = min(0.2, 2*0.05) = 0.10
        base = self.calc.calculate_confidence("relates_to", "", "inferred", 2)
        assert base == pytest.approx(0.70 + 0.10, abs=1e-9)

    def test_evidence_boost_capped_at_0_2(self):
        # 10 evidence → min(0.2, 10*0.05=0.5) = 0.2
        result = self.calc.calculate_confidence("relates_to", "", "inferred", 10)
        assert result == pytest.approx(0.70 + 0.2, abs=1e-9)

    def test_high_evidence_type_with_0_evidence_penalty(self):
        # "treats" is HIGH_EVIDENCE, evidence_count=0 → base *= 0.9
        # 0.95 * 0.9 = 0.855
        result = self.calc.calculate_confidence("treats", "", "explicit", 0)
        assert result == pytest.approx(0.95 * 0.9, abs=1e-9)

    def test_high_evidence_type_with_2_evidence_type_boost(self):
        # evidence_count=2 → evidence_boost=0.10, type_boost=0.10
        # no text_quality → 0.95 + 0.10 + 0.10 = 1.15, capped at 1.0
        result = self.calc.calculate_confidence("treats", "", "explicit", 2)
        assert result == pytest.approx(1.0, abs=1e-9)

    def test_text_quality_added_for_short_text(self):
        # 100-char text → text_quality = min(0.1, 100/1000) = 0.1
        text = "x" * 100
        result = self.calc.calculate_confidence("relates_to", text, "inferred", 0)
        assert result == pytest.approx(0.70 + 0.1, abs=1e-9)

    def test_text_quality_capped_at_0_1(self):
        # 2000-char text → min(0.1, 2000/1000) = 0.1
        text = "x" * 2000
        result = self.calc.calculate_confidence("relates_to", text, "inferred", 0)
        assert result == pytest.approx(0.70 + 0.1, abs=1e-9)

    def test_empty_text_no_quality_boost(self):
        result = self.calc.calculate_confidence("relates_to", "", "inferred", 0)
        assert result == pytest.approx(0.70, abs=1e-9)

    def test_result_capped_at_1(self):
        # user_validated (0.99) + evidence boost + type boost would exceed 1
        result = self.calc.calculate_confidence("treats", "x" * 500, "user_validated", 5)
        assert result <= 1.0

    def test_causes_is_high_evidence_type_penalty(self):
        # "causes" in HIGH_EVIDENCE_TYPES
        result = self.calc.calculate_confidence("causes", "", "explicit", 0)
        assert result == pytest.approx(0.95 * 0.9, abs=1e-9)

    def test_interacts_with_is_high_evidence_type(self):
        result_0 = self.calc.calculate_confidence("interacts_with", "", "explicit", 0)
        assert result_0 == pytest.approx(0.95 * 0.9, abs=1e-9)

    def test_increases_risk_high_evidence_penalty(self):
        result = self.calc.calculate_confidence("increases_risk", "", "inferred", 0)
        assert result == pytest.approx(0.70 * 0.9, abs=1e-9)

    def test_decreases_risk_high_evidence_penalty(self):
        result = self.calc.calculate_confidence("decreases_risk", "", "inferred", 0)
        assert result == pytest.approx(0.70 * 0.9, abs=1e-9)

    def test_contraindicated_high_evidence_penalty(self):
        result = self.calc.calculate_confidence("contraindicated", "", "inferred", 0)
        assert result == pytest.approx(0.70 * 0.9, abs=1e-9)

    def test_high_evidence_type_1_evidence_no_boost_no_penalty(self):
        # existing_evidence_count=1 → not 0, not >= 2 → no type adjustment
        result = self.calc.calculate_confidence("treats", "", "explicit", 1)
        # base stays 0.95, evidence_boost = 0.05, type_boost = 0
        assert result == pytest.approx(0.95 + 0.05, abs=1e-9)


# ---------------------------------------------------------------------------
# RelationshipConfidenceCalculator – merge_confidence
# ---------------------------------------------------------------------------

class TestMergeConfidence:
    """RelationshipConfidenceCalculator.merge_confidence."""

    def setup_method(self):
        self.calc = RelationshipConfidenceCalculator()

    def test_existing_count_0_returns_new_confidence(self):
        # weighted = (existing * 0 + new) / 1 = new; boost = 0
        result = self.calc.merge_confidence(0.8, 0.6, 0)
        assert result == pytest.approx(0.6, abs=1e-9)

    def test_existing_count_1_weighted_average_plus_boost(self):
        # weighted = (0.8 + 0.6) / 2 = 0.7; boost = min(0.15, 0.05*1) = 0.05
        result = self.calc.merge_confidence(0.8, 0.6, 1)
        assert result == pytest.approx(0.75, abs=1e-9)

    def test_corroboration_boost_capped_at_0_15(self):
        # existing_count=10 → boost = min(0.15, 0.5) = 0.15
        result = self.calc.merge_confidence(0.5, 0.5, 10)
        weighted = (0.5 * 10 + 0.5) / 11
        assert result == pytest.approx(min(1.0, weighted + 0.15), abs=1e-9)

    def test_result_capped_at_1(self):
        result = self.calc.merge_confidence(1.0, 1.0, 5)
        assert result <= 1.0

    def test_existing_count_2(self):
        # weighted = (0.9 * 2 + 0.8) / 3 = (1.8 + 0.8) / 3 = 2.6/3 ≈ 0.8667
        # boost = min(0.15, 0.05 * 2) = 0.10
        result = self.calc.merge_confidence(0.9, 0.8, 2)
        weighted = (0.9 * 2 + 0.8) / 3
        assert result == pytest.approx(min(1.0, weighted + 0.10), abs=1e-9)

    def test_existing_count_3_boost_0_15(self):
        # boost = min(0.15, 0.05 * 3) = 0.15
        result = self.calc.merge_confidence(0.6, 0.6, 3)
        weighted = (0.6 * 3 + 0.6) / 4
        assert result == pytest.approx(min(1.0, weighted + 0.15), abs=1e-9)

    def test_low_confidences_no_cap(self):
        result = self.calc.merge_confidence(0.3, 0.2, 1)
        weighted = (0.3 + 0.2) / 2
        assert result == pytest.approx(weighted + 0.05, abs=1e-9)


# ---------------------------------------------------------------------------
# RelationshipConfidenceCalculator – should_merge_relationships
# ---------------------------------------------------------------------------

class TestShouldMergeRelationships:
    """should_merge_relationships."""

    def setup_method(self):
        self.calc = RelationshipConfidenceCalculator()

    def _make_edge(self, eid, src, tgt, rtype):
        return GraphEdge(id=eid, source_id=src, target_id=tgt, relationship_type=rtype)

    def test_same_source_target_type_returns_true(self):
        e1 = self._make_edge("e1", "n1", "n2", "TREATS")
        e2 = self._make_edge("e2", "n1", "n2", "TREATS")
        assert self.calc.should_merge_relationships(e1, e2) is True

    def test_different_source_returns_false(self):
        e1 = self._make_edge("e1", "n1", "n2", "TREATS")
        e2 = self._make_edge("e2", "nX", "n2", "TREATS")
        assert self.calc.should_merge_relationships(e1, e2) is False

    def test_different_target_returns_false(self):
        e1 = self._make_edge("e1", "n1", "n2", "TREATS")
        e2 = self._make_edge("e2", "n1", "nX", "TREATS")
        assert self.calc.should_merge_relationships(e1, e2) is False

    def test_different_type_returns_false(self):
        e1 = self._make_edge("e1", "n1", "n2", "TREATS")
        e2 = self._make_edge("e2", "n1", "n2", "CAUSES")
        assert self.calc.should_merge_relationships(e1, e2) is False

    def test_all_different_returns_false(self):
        e1 = self._make_edge("e1", "n1", "n2", "TREATS")
        e2 = self._make_edge("e2", "n3", "n4", "CAUSES")
        assert self.calc.should_merge_relationships(e1, e2) is False


# ---------------------------------------------------------------------------
# RelationshipConfidenceCalculator – merge_edges
# ---------------------------------------------------------------------------

class TestMergeEdges:
    """merge_edges mutates edge1 and returns it."""

    def setup_method(self):
        self.calc = RelationshipConfidenceCalculator()

    def _make_edge(self, eid="e1", src="n1", tgt="n2", rtype="TREATS",
                   confidence=1.0, evidence_count=1, source_documents=None,
                   first_seen=None, last_seen=None, fact="", evidence_type="inferred"):
        return GraphEdge(
            id=eid, source_id=src, target_id=tgt, relationship_type=rtype,
            confidence=confidence, evidence_count=evidence_count,
            source_documents=source_documents or [],
            first_seen=first_seen, last_seen=last_seen,
            fact=fact, evidence_type=evidence_type,
        )

    def test_returns_edge1(self):
        e1 = self._make_edge()
        e2 = self._make_edge(eid="e2")
        result = self.calc.merge_edges(e1, e2)
        assert result is e1

    def test_evidence_count_incremented(self):
        e1 = self._make_edge(evidence_count=2)
        e2 = self._make_edge(eid="e2", evidence_count=3)
        self.calc.merge_edges(e1, e2)
        assert e1.evidence_count == 5

    def test_evidence_type_set_to_aggregated(self):
        e1 = self._make_edge(evidence_type="explicit")
        e2 = self._make_edge(eid="e2", evidence_type="inferred")
        self.calc.merge_edges(e1, e2)
        assert e1.evidence_type == "aggregated"

    def test_source_documents_merged_no_duplicates(self):
        e1 = self._make_edge(source_documents=["doc1", "doc2"])
        e2 = self._make_edge(eid="e2", source_documents=["doc2", "doc3"])
        self.calc.merge_edges(e1, e2)
        assert "doc1" in e1.source_documents
        assert "doc2" in e1.source_documents
        assert "doc3" in e1.source_documents
        assert e1.source_documents.count("doc2") == 1

    def test_first_seen_takes_earlier(self):
        earlier = datetime(2023, 1, 1)
        later = datetime(2023, 6, 1)
        e1 = self._make_edge(first_seen=later)
        e2 = self._make_edge(eid="e2", first_seen=earlier)
        self.calc.merge_edges(e1, e2)
        assert e1.first_seen == earlier

    def test_last_seen_takes_later(self):
        earlier = datetime(2023, 1, 1)
        later = datetime(2023, 6, 1)
        e1 = self._make_edge(last_seen=earlier)
        e2 = self._make_edge(eid="e2", last_seen=later)
        self.calc.merge_edges(e1, e2)
        assert e1.last_seen == later

    def test_first_seen_none_in_e1_uses_e2_first_seen(self):
        dt = datetime(2023, 3, 15)
        e1 = self._make_edge(first_seen=None)
        e2 = self._make_edge(eid="e2", first_seen=dt)
        self.calc.merge_edges(e1, e2)
        assert e1.first_seen == dt

    def test_last_seen_none_in_e1_uses_e2_last_seen(self):
        dt = datetime(2023, 3, 15)
        e1 = self._make_edge(last_seen=None)
        e2 = self._make_edge(eid="e2", last_seen=dt)
        self.calc.merge_edges(e1, e2)
        assert e1.last_seen == dt

    def test_facts_merged_with_separator_when_different(self):
        e1 = self._make_edge(fact="Aspirin reduces fever")
        e2 = self._make_edge(eid="e2", fact="Aspirin relieves pain")
        self.calc.merge_edges(e1, e2)
        assert e1.fact == "Aspirin reduces fever; Aspirin relieves pain"

    def test_fact_unchanged_when_same(self):
        e1 = self._make_edge(fact="same fact")
        e2 = self._make_edge(eid="e2", fact="same fact")
        self.calc.merge_edges(e1, e2)
        assert e1.fact == "same fact"

    def test_e2_fact_used_when_e1_fact_empty(self):
        e1 = self._make_edge(fact="")
        e2 = self._make_edge(eid="e2", fact="new fact")
        self.calc.merge_edges(e1, e2)
        assert e1.fact == "new fact"

    def test_fact_unchanged_when_e2_fact_empty(self):
        e1 = self._make_edge(fact="original fact")
        e2 = self._make_edge(eid="e2", fact="")
        self.calc.merge_edges(e1, e2)
        assert e1.fact == "original fact"

    def test_confidence_updated_via_merge_formula(self):
        e1 = self._make_edge(confidence=0.8, evidence_count=2)
        e2 = self._make_edge(eid="e2", confidence=0.6, evidence_count=1)
        # merge_confidence(0.8, 0.6, 2): weighted=(0.8*2+0.6)/3=2.2/3≈0.733; boost=0.10
        self.calc.merge_edges(e1, e2)
        expected_conf = self.calc.merge_confidence(0.8, 0.6, 2)
        # Re-compute independently to avoid mutation order issues
        assert e1.confidence == pytest.approx(expected_conf, abs=1e-9)

    def test_first_seen_not_updated_when_e2_first_seen_later(self):
        earlier = datetime(2023, 1, 1)
        later = datetime(2023, 6, 1)
        e1 = self._make_edge(first_seen=earlier)
        e2 = self._make_edge(eid="e2", first_seen=later)
        self.calc.merge_edges(e1, e2)
        assert e1.first_seen == earlier  # keeps earlier

    def test_last_seen_not_updated_when_e2_last_seen_earlier(self):
        earlier = datetime(2023, 1, 1)
        later = datetime(2023, 6, 1)
        e1 = self._make_edge(last_seen=later)
        e2 = self._make_edge(eid="e2", last_seen=earlier)
        self.calc.merge_edges(e1, e2)
        assert e1.last_seen == later  # keeps later


# ---------------------------------------------------------------------------
# GraphData – properties and methods
# ---------------------------------------------------------------------------

class TestGraphDataProperties:
    """node_count, edge_count."""

    def test_node_count_empty(self):
        assert GraphData().node_count == 0

    def test_edge_count_empty(self):
        assert GraphData().edge_count == 0

    def test_node_count(self):
        n1 = GraphNode(id="n1", name="A", entity_type=EntityType.MEDICATION)
        n2 = GraphNode(id="n2", name="B", entity_type=EntityType.SYMPTOM)
        assert GraphData(nodes=[n1, n2]).node_count == 2

    def test_edge_count(self):
        e1 = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="X")
        e2 = GraphEdge(id="e2", source_id="n2", target_id="n1", relationship_type="Y")
        assert GraphData(edges=[e1, e2]).edge_count == 2


class TestGraphDataGetNode:
    """get_node."""

    def setup_method(self):
        self.n1 = GraphNode(id="n1", name="Aspirin", entity_type=EntityType.MEDICATION)
        self.n2 = GraphNode(id="n2", name="Fever", entity_type=EntityType.SYMPTOM)
        self.data = GraphData(nodes=[self.n1, self.n2])

    def test_get_existing_node(self):
        assert self.data.get_node("n1") is self.n1

    def test_get_another_existing_node(self):
        assert self.data.get_node("n2") is self.n2

    def test_get_nonexistent_node_returns_none(self):
        assert self.data.get_node("n99") is None

    def test_get_node_empty_graph(self):
        assert GraphData().get_node("n1") is None


class TestGraphDataGetEdgesForNode:
    """get_edges_for_node."""

    def setup_method(self):
        self.n1 = GraphNode(id="n1", name="A", entity_type=EntityType.MEDICATION)
        self.n2 = GraphNode(id="n2", name="B", entity_type=EntityType.SYMPTOM)
        self.n3 = GraphNode(id="n3", name="C", entity_type=EntityType.CONDITION)
        self.e1 = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="TREATS")
        self.e2 = GraphEdge(id="e2", source_id="n3", target_id="n1", relationship_type="CAUSES")
        self.e3 = GraphEdge(id="e3", source_id="n2", target_id="n3", relationship_type="LINKED")
        self.data = GraphData(nodes=[self.n1, self.n2, self.n3],
                              edges=[self.e1, self.e2, self.e3])

    def test_edges_where_node_is_source(self):
        edges = self.data.get_edges_for_node("n1")
        assert self.e1 in edges

    def test_edges_where_node_is_target(self):
        edges = self.data.get_edges_for_node("n1")
        assert self.e2 in edges

    def test_unrelated_edge_not_included(self):
        edges = self.data.get_edges_for_node("n1")
        assert self.e3 not in edges

    def test_no_edges_for_isolated_node(self):
        n_iso = GraphNode(id="nIso", name="Iso", entity_type=EntityType.UNKNOWN)
        data = GraphData(nodes=[n_iso], edges=[])
        assert data.get_edges_for_node("nIso") == []

    def test_nonexistent_node_id_returns_empty(self):
        assert self.data.get_edges_for_node("n999") == []


class TestGraphDataGetConnectedNodes:
    """get_connected_nodes."""

    def setup_method(self):
        self.n1 = GraphNode(id="n1", name="Aspirin", entity_type=EntityType.MEDICATION)
        self.n2 = GraphNode(id="n2", name="Fever", entity_type=EntityType.SYMPTOM)
        self.n3 = GraphNode(id="n3", name="Headache", entity_type=EntityType.SYMPTOM)
        self.e1 = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type="TREATS")
        self.e2 = GraphEdge(id="e2", source_id="n3", target_id="n1", relationship_type="TREATED_BY")
        self.data = GraphData(nodes=[self.n1, self.n2, self.n3],
                              edges=[self.e1, self.e2])

    def test_connected_nodes_via_outgoing_edge(self):
        connected = self.data.get_connected_nodes("n1")
        assert self.n2 in connected

    def test_connected_nodes_via_incoming_edge(self):
        connected = self.data.get_connected_nodes("n1")
        assert self.n3 in connected

    def test_node_itself_not_in_connected(self):
        connected = self.data.get_connected_nodes("n1")
        assert self.n1 not in connected

    def test_isolated_node_returns_empty(self):
        n_iso = GraphNode(id="nIso", name="Iso", entity_type=EntityType.UNKNOWN)
        data = GraphData(nodes=[n_iso, self.n1], edges=[self.e1])
        assert data.get_connected_nodes("nIso") == []

    def test_connected_count(self):
        connected = self.data.get_connected_nodes("n1")
        assert len(connected) == 2


class TestGraphDataFilterByType:
    """filter_by_type."""

    def setup_method(self):
        self.med1 = GraphNode(id="m1", name="Aspirin", entity_type=EntityType.MEDICATION)
        self.med2 = GraphNode(id="m2", name="Ibuprofen", entity_type=EntityType.MEDICATION)
        self.symp = GraphNode(id="s1", name="Fever", entity_type=EntityType.SYMPTOM)
        # Edge between two medications
        self.e_med = GraphEdge(id="e1", source_id="m1", target_id="m2", relationship_type="SAME_CLASS")
        # Edge between medication and symptom
        self.e_cross = GraphEdge(id="e2", source_id="m1", target_id="s1", relationship_type="TREATS")
        self.data = GraphData(
            nodes=[self.med1, self.med2, self.symp],
            edges=[self.e_med, self.e_cross],
        )

    def test_filter_returns_only_medication_nodes(self):
        result = self.data.filter_by_type(EntityType.MEDICATION)
        assert len(result.nodes) == 2
        assert all(n.entity_type == EntityType.MEDICATION for n in result.nodes)

    def test_filter_includes_intra_type_edges(self):
        result = self.data.filter_by_type(EntityType.MEDICATION)
        assert self.e_med in result.edges

    def test_filter_excludes_cross_type_edges(self):
        result = self.data.filter_by_type(EntityType.MEDICATION)
        assert self.e_cross not in result.edges

    def test_filter_returns_graphdata_instance(self):
        result = self.data.filter_by_type(EntityType.MEDICATION)
        assert isinstance(result, GraphData)

    def test_filter_no_match_returns_empty_graph(self):
        result = self.data.filter_by_type(EntityType.ANATOMY)
        assert result.node_count == 0
        assert result.edge_count == 0

    def test_filter_by_symptom(self):
        result = self.data.filter_by_type(EntityType.SYMPTOM)
        assert result.node_count == 1
        assert result.nodes[0] is self.symp


class TestGraphDataSearch:
    """search method."""

    def setup_method(self):
        self.n1 = GraphNode(id="n1", name="Aspirin", entity_type=EntityType.MEDICATION)
        self.n2 = GraphNode(id="n2", name="Fever", entity_type=EntityType.SYMPTOM)
        self.n3 = GraphNode(id="n3", name="Hypertension", entity_type=EntityType.CONDITION)
        self.data = GraphData(nodes=[self.n1, self.n2, self.n3])

    def test_empty_query_returns_all_nodes(self):
        result = self.data.search("")
        assert len(result) == 3

    def test_search_by_name(self):
        result = self.data.search("Aspirin")
        assert self.n1 in result
        assert self.n2 not in result

    def test_search_case_insensitive(self):
        result = self.data.search("aspirin")
        assert self.n1 in result

    def test_search_nonexistent_returns_empty(self):
        result = self.data.search("nonexistent_drug_xyz")
        assert result == []

    def test_search_by_entity_type_value(self):
        result = self.data.search("symptom")
        assert self.n2 in result

    def test_search_partial_match(self):
        result = self.data.search("pert")  # matches "Hypertension"
        assert self.n3 in result

    def test_search_empty_graph(self):
        assert GraphData().search("anything") == []

    def test_search_empty_query_empty_graph(self):
        assert GraphData().search("") == []

    def test_search_multiple_matches(self):
        # "e" appears in "Fever", "Aspirin" (no), "Hypertension" yes
        result = self.data.search("e")
        # "Fever" has "e", "Hypertension" has "e", "Aspirin" has no "e"... wait "Aspirin" → no 'e'
        # "Aspirin" → a,s,p,i,r,i,n → no 'e'. "Fever" → f,e,v,e,r → yes. "Hypertension" → yes
        assert self.n2 in result
        assert self.n3 in result


# ---------------------------------------------------------------------------
# TestRelationshipConfidenceEdgeCases
# ---------------------------------------------------------------------------

class TestRelationshipConfidenceEdgeCases:
    """Edge cases for RelationshipConfidenceCalculator.calculate_confidence."""

    def setup_method(self):
        self.calc = RelationshipConfidenceCalculator()

    # -- HIGH_EVIDENCE_TYPES with 0 evidence → 0.9x penalty --

    def test_treats_zero_evidence_penalty(self):
        result = self.calc.calculate_confidence("treats", "", "explicit", 0)
        assert result == pytest.approx(0.95 * 0.9, abs=1e-9)

    def test_causes_zero_evidence_penalty(self):
        result = self.calc.calculate_confidence("causes", "", "explicit", 0)
        assert result == pytest.approx(0.95 * 0.9, abs=1e-9)

    def test_contraindicated_zero_evidence_penalty(self):
        result = self.calc.calculate_confidence("contraindicated", "", "explicit", 0)
        assert result == pytest.approx(0.95 * 0.9, abs=1e-9)

    def test_interacts_with_zero_evidence_penalty(self):
        result = self.calc.calculate_confidence("interacts_with", "", "explicit", 0)
        assert result == pytest.approx(0.95 * 0.9, abs=1e-9)

    def test_increases_risk_zero_evidence_penalty(self):
        result = self.calc.calculate_confidence("increases_risk", "", "explicit", 0)
        assert result == pytest.approx(0.95 * 0.9, abs=1e-9)

    def test_decreases_risk_zero_evidence_penalty(self):
        result = self.calc.calculate_confidence("decreases_risk", "", "explicit", 0)
        assert result == pytest.approx(0.95 * 0.9, abs=1e-9)

    # -- Short text (<50 chars) vs long text quality bonus --

    def test_short_text_small_quality_bonus(self):
        # 30-char text → text_quality = min(0.1, 30/1000) = 0.03
        result = self.calc.calculate_confidence("relates_to", "x" * 30, "inferred", 0)
        assert result == pytest.approx(0.70 + 0.03, abs=1e-9)

    def test_long_text_full_quality_bonus(self):
        # 500-char text → text_quality = min(0.1, 500/1000) = 0.1
        result = self.calc.calculate_confidence("relates_to", "x" * 500, "inferred", 0)
        assert result == pytest.approx(0.70 + 0.1, abs=1e-9)

    def test_50_char_text_quality(self):
        # 50-char text → text_quality = min(0.1, 50/1000) = 0.05
        result = self.calc.calculate_confidence("relates_to", "x" * 50, "inferred", 0)
        assert result == pytest.approx(0.70 + 0.05, abs=1e-9)

    # -- Extraction method base scores --

    def test_explicit_extraction_method_base(self):
        result = self.calc.calculate_confidence("relates_to", "", "explicit", 0)
        assert result == pytest.approx(0.95, abs=1e-9)

    def test_inferred_extraction_method_base(self):
        result = self.calc.calculate_confidence("relates_to", "", "inferred", 0)
        assert result == pytest.approx(0.70, abs=1e-9)

    def test_aggregated_extraction_method_base(self):
        result = self.calc.calculate_confidence("relates_to", "", "aggregated", 0)
        assert result == pytest.approx(0.85, abs=1e-9)

    def test_user_validated_extraction_method_base(self):
        result = self.calc.calculate_confidence("relates_to", "", "user_validated", 0)
        assert result == pytest.approx(0.99, abs=1e-9)

    # -- Unknown method defaults to 0.5 --

    def test_llm_extracted_unknown_method_defaults_to_0_5(self):
        # "llm_extracted" is NOT in BASE_CONFIDENCE → defaults to 0.5
        result = self.calc.calculate_confidence("relates_to", "", "llm_extracted", 0)
        assert result == pytest.approx(0.5, abs=1e-9)

    def test_imported_unknown_method_defaults_to_0_5(self):
        # "imported" is NOT in BASE_CONFIDENCE → defaults to 0.5
        result = self.calc.calculate_confidence("relates_to", "", "imported", 0)
        assert result == pytest.approx(0.5, abs=1e-9)

    def test_random_method_defaults_to_0_5(self):
        result = self.calc.calculate_confidence("relates_to", "", "some_random_method", 0)
        assert result == pytest.approx(0.5, abs=1e-9)

    # -- Combined: high-evidence + unknown method + short text = lowest possible --

    def test_combined_lowest_confidence(self):
        # "treats" (HIGH_EVIDENCE) + unknown method (0.5) + evidence_count=0 → penalty
        # base = 0.5 * 0.9 = 0.45, evidence_boost = 0, type_boost = 0, text_quality = 0
        result = self.calc.calculate_confidence("treats", "", "unknown_method", 0)
        assert result == pytest.approx(0.5 * 0.9, abs=1e-9)

    def test_combined_high_evidence_inferred_short_text(self):
        # "causes" + "inferred" (0.70) + evidence_count=0 → 0.70 * 0.9 = 0.63
        # short text (10 chars) → text_quality = min(0.1, 10/1000) = 0.01
        result = self.calc.calculate_confidence("causes", "x" * 10, "inferred", 0)
        assert result == pytest.approx(0.70 * 0.9 + 0.01, abs=1e-9)

    def test_none_evidence_text_is_empty_string_branch(self):
        # Empty string evidence → text_quality = 0.0
        result = self.calc.calculate_confidence("relates_to", "", "explicit", 0)
        assert result == pytest.approx(0.95, abs=1e-9)

    def test_none_evidence_text_passes_as_empty(self):
        # None evidence text should be handled (falsy check)
        result = self.calc.calculate_confidence("relates_to", None, "explicit", 0)
        assert result == pytest.approx(0.95, abs=1e-9)


# ---------------------------------------------------------------------------
# TestReliabilityScoreIntegration
# ---------------------------------------------------------------------------

class TestReliabilityScoreIntegration:
    """Test GraphEdge.reliability_score with various combinations."""

    def test_evidence_count_10_capped_at_factor_1(self):
        # evidence_factor = min(1.0, 10/3) = 1.0
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2",
                         relationship_type="X", evidence_count=10)
        expected = 1.0 * (0.5 + 0.3 * 1.0 + 0.2 * 0.5)  # no last_seen
        assert edge.reliability_score == pytest.approx(expected, abs=1e-6)

    def test_last_seen_today_full_recency(self):
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2",
                         relationship_type="X", last_seen=datetime.now())
        days_old = (datetime.now() - edge.last_seen).days
        recency = max(0.5, 1.0 - days_old / 365)
        expected = 1.0 * (0.5 + 0.3 * (1 / 3) + 0.2 * recency)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-3)

    def test_last_seen_two_years_ago_low_recency(self):
        two_years_ago = datetime.now() - timedelta(days=730)
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2",
                         relationship_type="X", last_seen=two_years_ago)
        days_old = (datetime.now() - two_years_ago).days
        recency = max(0.5, 1.0 - days_old / 365)
        # days_old ~ 730 → 1.0 - 730/365 = 1.0 - 2.0 = -1.0 → capped at 0.5
        assert recency == pytest.approx(0.5, abs=0.01)
        expected = 1.0 * (0.5 + 0.3 * (1 / 3) + 0.2 * 0.5)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-3)

    def test_last_seen_none_uses_default_recency(self):
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2",
                         relationship_type="X", last_seen=None)
        # Default recency_factor = 0.5
        expected = 1.0 * (0.5 + 0.3 * (1 / 3) + 0.2 * 0.5)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-6)

    def test_formula_components(self):
        # evidence_count=2, confidence=0.8, last_seen=now
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2",
                         relationship_type="X", confidence=0.8,
                         evidence_count=2, last_seen=datetime.now())
        ev_factor = min(1.0, 2 / 3)
        recency = max(0.5, 1.0 - 0 / 365)  # ~1.0
        expected = 0.8 * (0.5 + 0.3 * ev_factor + 0.2 * recency)
        assert edge.reliability_score == pytest.approx(expected, abs=1e-3)

    def test_zero_confidence_gives_zero_reliability(self):
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2",
                         relationship_type="X", confidence=0.0)
        assert edge.reliability_score == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# TestMergeConfidenceEdgeCases
# ---------------------------------------------------------------------------

class TestMergeConfidenceEdgeCases:
    """Edge cases for merge_confidence."""

    def setup_method(self):
        self.calc = RelationshipConfidenceCalculator()

    def test_two_high_confidences_result_higher_than_either(self):
        # existing=0.8, new=0.9, existing_count=1
        # weighted = (0.8 + 0.9) / 2 = 0.85; boost = 0.05
        # result = 0.9 → higher than 0.8
        result = self.calc.merge_confidence(0.8, 0.9, 1)
        assert result > 0.8  # corroboration makes it higher than existing

    def test_result_never_exceeds_1(self):
        result = self.calc.merge_confidence(0.99, 0.99, 10)
        assert result <= 1.0

    def test_result_capped_at_1_high_boost(self):
        result = self.calc.merge_confidence(0.95, 0.95, 5)
        assert result <= 1.0

    def test_merging_many_edges_accumulates_evidence(self):
        # Simulate merging 5 edges one by one
        calc = self.calc
        conf = 0.7
        for count in range(1, 6):
            conf = calc.merge_confidence(conf, 0.7, count)
        # Confidence should be higher than the original 0.7
        assert conf > 0.7
        # And should still be <= 1.0
        assert conf <= 1.0

    def test_two_identical_confidences(self):
        # existing=0.6, new=0.6, existing_count=1
        # weighted = (0.6 + 0.6) / 2 = 0.6; boost = 0.05
        result = self.calc.merge_confidence(0.6, 0.6, 1)
        assert result == pytest.approx(0.6 + 0.05, abs=1e-9)

    def test_low_existing_high_new(self):
        result = self.calc.merge_confidence(0.3, 0.9, 1)
        weighted = (0.3 + 0.9) / 2  # 0.6
        assert result == pytest.approx(weighted + 0.05, abs=1e-9)

    def test_high_existing_low_new(self):
        result = self.calc.merge_confidence(0.9, 0.3, 1)
        weighted = (0.9 + 0.3) / 2  # 0.6
        assert result == pytest.approx(weighted + 0.05, abs=1e-9)

    def test_zero_existing_count(self):
        # Just returns new_confidence (no boost)
        result = self.calc.merge_confidence(0.5, 0.8, 0)
        assert result == pytest.approx(0.8, abs=1e-9)


# ---------------------------------------------------------------------------
# TestEntityTypeFuzzyMatchExtended
# ---------------------------------------------------------------------------

class TestEntityTypeFuzzyMatchExtended:
    """Additional fuzzy matching cases for EntityType.from_string."""

    def test_medications_plural_returns_unknown(self):
        # "medications" → direct match for "medication" fails (extra 's'),
        # fuzzy keys: "drug" not in "medications", "medicine" not in "medications"
        # → returns UNKNOWN
        assert EntityType.from_string("medications") == EntityType.UNKNOWN

    def test_symptoms_plural_contains_sign(self):
        # "symptoms" → direct match fails, but fuzzy: "sign" IS in "symptoms"? No.
        # Actually "sign" is NOT a substring of "symptoms". Let's check actual behavior.
        result = EntityType.from_string("symptoms")
        # Check what actually happens: direct match fails,
        # fuzzy loop: "presentation" in "symptoms"? no. "sign" in "symptoms"? no.
        # "finding" in "symptoms"? no. → UNKNOWN
        assert result == EntityType.UNKNOWN

    def test_drug_maps_to_medication(self):
        assert EntityType.from_string("drug") == EntityType.MEDICATION

    def test_disease_maps_to_condition(self):
        assert EntityType.from_string("disease") == EntityType.CONDITION

    def test_lab_maps_to_lab_test(self):
        assert EntityType.from_string("lab") == EntityType.LAB_TEST

    def test_test_maps_to_lab_test(self):
        assert EntityType.from_string("test") == EntityType.LAB_TEST

    def test_completely_unknown_returns_none_equivalent(self):
        # "xylophone" has none of the fuzzy keys
        assert EntityType.from_string("xylophone") == EntityType.UNKNOWN

    def test_numeric_string_returns_unknown(self):
        assert EntityType.from_string("12345") == EntityType.UNKNOWN

    def test_special_chars_returns_unknown(self):
        assert EntityType.from_string("@#$%") == EntityType.UNKNOWN

    def test_mixed_fuzzy_and_direct(self):
        # "laboratory_test" contains "test" and "lab" → first match wins
        result = EntityType.from_string("laboratory_test")
        assert result == EntityType.LAB_TEST

    def test_organ_damage(self):
        # "organ damage" contains "organ" → ANATOMY
        result = EntityType.from_string("organ damage")
        assert result == EntityType.ANATOMY
