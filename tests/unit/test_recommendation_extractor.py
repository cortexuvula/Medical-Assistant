"""
Tests for src/rag/recommendation_extractor.py

Covers ExtractionResult dataclass defaults, RecommendationExtractor
private methods (_extract_recommendation_class, _extract_evidence_level,
_extract_section_type), the main extract() method (confidence calculation,
all field combinations), and extract_batch().
Pure regex/string logic — no network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.recommendation_extractor import (
    ExtractionResult,
    RecommendationExtractor,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _extractor() -> RecommendationExtractor:
    return RecommendationExtractor()


# ===========================================================================
# ExtractionResult dataclass
# ===========================================================================

class TestExtractionResult:
    def test_section_type_defaults_recommendation(self):
        r = ExtractionResult()
        assert r.section_type == "recommendation"

    def test_recommendation_class_defaults_none(self):
        r = ExtractionResult()
        assert r.recommendation_class is None

    def test_evidence_level_defaults_none(self):
        r = ExtractionResult()
        assert r.evidence_level is None

    def test_confidence_defaults_zero(self):
        r = ExtractionResult()
        assert r.confidence == pytest.approx(0.0)

    def test_custom_values_accepted(self):
        r = ExtractionResult(
            section_type="warning",
            recommendation_class="I",
            evidence_level="A",
            confidence=0.8,
        )
        assert r.section_type == "warning"
        assert r.recommendation_class == "I"
        assert r.evidence_level == "A"
        assert r.confidence == pytest.approx(0.8)


# ===========================================================================
# _extract_recommendation_class
# ===========================================================================

class TestExtractRecommendationClass:
    def setup_method(self):
        self.ext = _extractor()

    def test_class_i(self):
        assert self.ext._extract_recommendation_class("Class I recommendation") == "I"

    def test_class_iia(self):
        assert self.ext._extract_recommendation_class("Class IIa evidence") == "IIa"

    def test_class_iib(self):
        assert self.ext._extract_recommendation_class("Class IIb weak evidence") == "IIb"

    def test_class_iii(self):
        assert self.ext._extract_recommendation_class("Class III no benefit") == "III"

    def test_cor_iia(self):
        assert self.ext._extract_recommendation_class("COR IIa is suggested") == "IIa"

    def test_cor_i(self):
        assert self.ext._extract_recommendation_class("COR I is recommended") == "I"

    def test_case_insensitive(self):
        assert self.ext._extract_recommendation_class("class iia is suggested") == "IIa"

    def test_class_of_recommendation_format(self):
        result = self.ext._extract_recommendation_class(
            "Class of Recommendation: I for primary prevention"
        )
        assert result == "I"

    def test_standalone_with_strong(self):
        result = self.ext._extract_recommendation_class("I (Strong) recommendation")
        assert result == "I"

    def test_standalone_iia_moderate(self):
        result = self.ext._extract_recommendation_class("IIa (Moderate) recommendation")
        assert result == "IIa"

    def test_standalone_iib_weak(self):
        result = self.ext._extract_recommendation_class("IIb (Weak) indication")
        assert result == "IIb"

    def test_standalone_iii_no_benefit(self):
        result = self.ext._extract_recommendation_class("III (No Benefit) for this")
        assert result == "III"

    def test_empty_string_returns_none(self):
        assert self.ext._extract_recommendation_class("") is None

    def test_no_class_returns_none(self):
        assert self.ext._extract_recommendation_class("Standard care is indicated") is None

    def test_returns_string_when_found(self):
        result = self.ext._extract_recommendation_class("Class IIa is suggested")
        assert isinstance(result, str)


# ===========================================================================
# _extract_evidence_level
# ===========================================================================

class TestExtractEvidenceLevel:
    def setup_method(self):
        self.ext = _extractor()

    def test_level_a(self):
        assert self.ext._extract_evidence_level("Level A evidence from multiple RCTs") == "A"

    def test_level_b(self):
        assert self.ext._extract_evidence_level("Level B from a single RCT") == "B"

    def test_level_b_r(self):
        assert self.ext._extract_evidence_level("Level B-R randomized study") == "B-R"

    def test_level_b_nr(self):
        assert self.ext._extract_evidence_level("Level B-NR non-randomized study") == "B-NR"

    def test_level_c(self):
        assert self.ext._extract_evidence_level("Level C consensus opinion") == "C"

    def test_level_c_ld(self):
        assert self.ext._extract_evidence_level("Level C-LD limited data available") == "C-LD"

    def test_level_c_eo(self):
        assert self.ext._extract_evidence_level("Level C-EO expert opinion only") == "C-EO"

    def test_loe_format(self):
        assert self.ext._extract_evidence_level("LOE A is supported") == "A"

    def test_level_of_evidence_colon_format(self):
        result = self.ext._extract_evidence_level("Level of Evidence: A from meta-analyses")
        assert result == "A"

    def test_parenthetical_level_format(self):
        result = self.ext._extract_evidence_level("is recommended (Level A)")
        assert result == "A"

    def test_case_insensitive(self):
        result = self.ext._extract_evidence_level("level a evidence")
        assert result == "A"

    def test_empty_string_returns_none(self):
        assert self.ext._extract_evidence_level("") is None

    def test_no_evidence_returns_none(self):
        assert self.ext._extract_evidence_level("Treatment is recommended for all patients") is None

    def test_returns_uppercase(self):
        result = self.ext._extract_evidence_level("LOE B-R supports this")
        assert result == result.upper()


# ===========================================================================
# _extract_section_type
# ===========================================================================

class TestExtractSectionType:
    def setup_method(self):
        self.ext = _extractor()

    def test_warning_keyword(self):
        assert self.ext._extract_section_type("WARNING: Do not use in pregnancy") == "warning"

    def test_caution_keyword(self):
        assert self.ext._extract_section_type("CAUTION: Monitor renal function") == "warning"

    def test_black_box_keyword(self):
        assert self.ext._extract_section_type("BLACK BOX WARNING applies here") == "warning"

    def test_contraindication_keyword(self):
        assert self.ext._extract_section_type("CONTRAINDICATION: heart failure") == "contraindication"

    def test_contraindicated_keyword(self):
        assert self.ext._extract_section_type("Drug is CONTRAINDICATED in renal failure") == "contraindication"

    def test_do_not_keyword(self):
        assert self.ext._extract_section_type("DO NOT use in pregnancy") == "contraindication"

    def test_monitor_keyword(self):
        assert self.ext._extract_section_type("MONITOR potassium levels weekly") == "monitoring"

    def test_monitoring_keyword(self):
        assert self.ext._extract_section_type("MONITORING required for first 3 months") == "monitoring"

    def test_follow_up_keyword(self):
        assert self.ext._extract_section_type("FOLLOW-UP at 3 months is recommended") == "monitoring"

    def test_evidence_keyword(self):
        assert self.ext._extract_section_type("EVIDENCE from three large RCTs") == "evidence"

    def test_rct_keyword(self):
        assert self.ext._extract_section_type("Based on a large RCT with 5000 patients") == "evidence"

    def test_meta_analysis_keyword(self):
        assert self.ext._extract_section_type("META-ANALYSIS confirms benefit") == "evidence"

    def test_rationale_keyword(self):
        assert self.ext._extract_section_type("RATIONALE: This recommendation is based on") == "rationale"

    def test_background_keyword(self):
        assert self.ext._extract_section_type("BACKGROUND section describes the condition") == "rationale"

    def test_default_returns_recommendation(self):
        assert self.ext._extract_section_type("ACE inhibitors are recommended for all patients") == "recommendation"

    def test_empty_string_returns_recommendation(self):
        assert self.ext._extract_section_type("") == "recommendation"

    def test_case_insensitive(self):
        assert self.ext._extract_section_type("warning: do not use") == "warning"


# ===========================================================================
# extract() — main method
# ===========================================================================

class TestExtract:
    def setup_method(self):
        self.ext = _extractor()

    def test_empty_string_returns_default_result(self):
        result = self.ext.extract("")
        assert isinstance(result, ExtractionResult)
        assert result.section_type == "recommendation"
        assert result.recommendation_class is None
        assert result.evidence_level is None
        assert result.confidence == pytest.approx(0.0)

    def test_returns_extraction_result(self):
        result = self.ext.extract("Class I recommendation")
        assert isinstance(result, ExtractionResult)

    def test_class_found_adds_0_4_confidence(self):
        result = self.ext.extract("Class I is recommended")
        assert result.confidence == pytest.approx(0.4)
        assert result.recommendation_class == "I"

    def test_evidence_found_adds_0_4_confidence(self):
        result = self.ext.extract("Level A from multiple trials")
        assert result.confidence == pytest.approx(0.4)
        assert result.evidence_level == "A"

    def test_non_recommendation_section_adds_0_2_confidence(self):
        result = self.ext.extract("WARNING: Do not use in pregnancy")
        assert result.confidence == pytest.approx(0.2)
        assert result.section_type == "warning"

    def test_class_and_evidence_gives_0_8(self):
        result = self.ext.extract("Class I recommendation. Level A from multiple RCTs.")
        assert result.confidence == pytest.approx(0.8)

    def test_all_three_gives_1_0(self):
        result = self.ext.extract(
            "WARNING: Class IIa is suggested with Level B-R evidence"
        )
        assert result.confidence == pytest.approx(1.0)

    def test_class_extracted_correctly(self):
        result = self.ext.extract("Class IIb may be considered. Level C-LD.")
        assert result.recommendation_class == "IIb"

    def test_evidence_extracted_correctly(self):
        result = self.ext.extract("Class IIb may be considered. Level C-LD.")
        assert result.evidence_level == "C-LD"

    def test_section_type_warning(self):
        result = self.ext.extract("WARNING: Avoid in severe hepatic impairment.")
        assert result.section_type == "warning"

    def test_section_type_defaults_recommendation(self):
        result = self.ext.extract("This therapy is strongly recommended for all eligible patients.")
        assert result.section_type == "recommendation"

    def test_no_matches_zero_confidence(self):
        result = self.ext.extract("The patient was seen in clinic today.")
        assert result.confidence == pytest.approx(0.0)

    def test_confidence_is_float(self):
        result = self.ext.extract("Class I recommendation")
        assert isinstance(result.confidence, float)


# ===========================================================================
# extract_batch()
# ===========================================================================

class TestExtractBatch:
    def setup_method(self):
        self.ext = _extractor()

    def test_empty_list_returns_empty_list(self):
        assert self.ext.extract_batch([]) == []

    def test_returns_list(self):
        result = self.ext.extract_batch(["text"])
        assert isinstance(result, list)

    def test_one_chunk_returns_one_result(self):
        result = self.ext.extract_batch(["Class I recommendation"])
        assert len(result) == 1

    def test_multiple_chunks_returns_same_count(self):
        chunks = [
            "Class I recommendation Level A",
            "WARNING: Do not use",
            "Level B-R supports this",
        ]
        result = self.ext.extract_batch(chunks)
        assert len(result) == 3

    def test_batch_results_match_individual(self):
        chunks = ["Class I recommendation", "Level A from RCTs"]
        batch_results = self.ext.extract_batch(chunks)
        for chunk, batch_result in zip(chunks, batch_results):
            individual = self.ext.extract(chunk)
            assert batch_result.recommendation_class == individual.recommendation_class
            assert batch_result.evidence_level == individual.evidence_level
            assert batch_result.confidence == individual.confidence

    def test_each_result_is_extraction_result(self):
        results = self.ext.extract_batch(["text one", "text two"])
        for r in results:
            assert isinstance(r, ExtractionResult)
