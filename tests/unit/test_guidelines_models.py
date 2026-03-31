"""
Tests for src/rag/guidelines_models.py

Covers all enums (GuidelineSpecialty, GuidelineSource, GuidelineType,
RecommendationClass, EvidenceLevel, ComplianceStatus, SectionType,
GuidelineUploadStatus), dataclasses (GuidelineReference, ComplianceItem,
ComplianceResult, ConditionFinding, ConditionCompliance,
ComplianceAnalysisResult), and Pydantic models (GuidelineMetadata,
GuidelineChunk, GuidelineDocument, GuidelineSearchQuery,
GuidelineSearchResult, GuidelineUploadRequest, GuidelineUploadProgress,
GuidelinesSettings).  No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.guidelines_models import (
    GuidelineSpecialty,
    GuidelineSource,
    GuidelineType,
    RecommendationClass,
    EvidenceLevel,
    ComplianceStatus,
    SectionType,
    GuidelineUploadStatus,
    GuidelineReference,
    ComplianceItem,
    ComplianceResult,
    ConditionFinding,
    ConditionCompliance,
    ComplianceAnalysisResult,
    GuidelineMetadata,
    GuidelineChunk,
    GuidelineDocument,
    GuidelineSearchQuery,
    GuidelineSearchResult,
    GuidelineUploadRequest,
    GuidelineUploadProgress,
    GuidelineListItem,
    GuidelinesSettings,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
)


# ===========================================================================
# GuidelineSpecialty enum
# ===========================================================================

class TestGuidelineSpecialty:
    def test_cardiology_value(self):
        assert GuidelineSpecialty.CARDIOLOGY.value == "cardiology"

    def test_pulmonology_value(self):
        assert GuidelineSpecialty.PULMONOLOGY.value == "pulmonology"

    def test_endocrinology_value(self):
        assert GuidelineSpecialty.ENDOCRINOLOGY.value == "endocrinology"

    def test_general_value(self):
        assert GuidelineSpecialty.GENERAL.value == "general"

    def test_infectious_disease_value(self):
        assert GuidelineSpecialty.INFECTIOUS_DISEASE.value == "infectious_disease"

    def test_total_members(self):
        assert len(list(GuidelineSpecialty)) == 15

    def test_is_str_enum(self):
        assert GuidelineSpecialty.CARDIOLOGY == "cardiology"


# ===========================================================================
# GuidelineSource enum
# ===========================================================================

class TestGuidelineSource:
    def test_aha_value(self):
        assert GuidelineSource.AHA.value == "AHA"

    def test_acc_value(self):
        assert GuidelineSource.ACC.value == "ACC"

    def test_aha_acc_value(self):
        assert GuidelineSource.AHA_ACC.value == "AHA/ACC"

    def test_ada_value(self):
        assert GuidelineSource.ADA.value == "ADA"

    def test_gold_value(self):
        assert GuidelineSource.GOLD.value == "GOLD"

    def test_nice_value(self):
        assert GuidelineSource.NICE.value == "NICE"

    def test_other_value(self):
        assert GuidelineSource.OTHER.value == "OTHER"

    def test_total_members(self):
        assert len(list(GuidelineSource)) == 17


# ===========================================================================
# GuidelineType enum
# ===========================================================================

class TestGuidelineType:
    def test_treatment_protocol_value(self):
        assert GuidelineType.TREATMENT_PROTOCOL.value == "treatment_protocol"

    def test_diagnostic_criteria_value(self):
        assert GuidelineType.DIAGNOSTIC_CRITERIA.value == "diagnostic_criteria"

    def test_screening_recommendation_value(self):
        assert GuidelineType.SCREENING_RECOMMENDATION.value == "screening_recommendation"

    def test_prevention_guideline_value(self):
        assert GuidelineType.PREVENTION_GUIDELINE.value == "prevention_guideline"

    def test_clinical_pathway_value(self):
        assert GuidelineType.CLINICAL_PATHWAY.value == "clinical_pathway"

    def test_total_members(self):
        assert len(list(GuidelineType)) == 7


# ===========================================================================
# RecommendationClass enum
# ===========================================================================

class TestRecommendationClass:
    def test_class_i_value(self):
        assert RecommendationClass.CLASS_I.value == "I"

    def test_class_iia_value(self):
        assert RecommendationClass.CLASS_IIA.value == "IIa"

    def test_class_iib_value(self):
        assert RecommendationClass.CLASS_IIB.value == "IIb"

    def test_class_iii_value(self):
        assert RecommendationClass.CLASS_III.value == "III"

    def test_total_members(self):
        assert len(list(RecommendationClass)) == 4


# ===========================================================================
# EvidenceLevel enum
# ===========================================================================

class TestEvidenceLevel:
    def test_level_a_value(self):
        assert EvidenceLevel.LEVEL_A.value == "A"

    def test_level_b_value(self):
        assert EvidenceLevel.LEVEL_B.value == "B"

    def test_level_br_value(self):
        assert EvidenceLevel.LEVEL_BR.value == "B-R"

    def test_level_bnr_value(self):
        assert EvidenceLevel.LEVEL_BNR.value == "B-NR"

    def test_level_c_value(self):
        assert EvidenceLevel.LEVEL_C.value == "C"

    def test_level_cld_value(self):
        assert EvidenceLevel.LEVEL_CLD.value == "C-LD"

    def test_level_ceo_value(self):
        assert EvidenceLevel.LEVEL_CEO.value == "C-EO"

    def test_total_members(self):
        assert len(list(EvidenceLevel)) == 7


# ===========================================================================
# ComplianceStatus enum
# ===========================================================================

class TestComplianceStatus:
    def test_compliant_value(self):
        assert ComplianceStatus.COMPLIANT.value == "compliant"

    def test_gap_value(self):
        assert ComplianceStatus.GAP.value == "gap"

    def test_warning_value(self):
        assert ComplianceStatus.WARNING.value == "warning"

    def test_not_applicable_value(self):
        assert ComplianceStatus.NOT_APPLICABLE.value == "not_applicable"

    def test_total_members(self):
        assert len(list(ComplianceStatus)) == 4


# ===========================================================================
# SectionType enum
# ===========================================================================

class TestSectionType:
    def test_recommendation_value(self):
        assert SectionType.RECOMMENDATION.value == "recommendation"

    def test_warning_value(self):
        assert SectionType.WARNING.value == "warning"

    def test_evidence_value(self):
        assert SectionType.EVIDENCE.value == "evidence"

    def test_rationale_value(self):
        assert SectionType.RATIONALE.value == "rationale"

    def test_monitoring_value(self):
        assert SectionType.MONITORING.value == "monitoring"

    def test_contraindication_value(self):
        assert SectionType.CONTRAINDICATION.value == "contraindication"

    def test_total_members(self):
        assert len(list(SectionType)) == 6


# ===========================================================================
# GuidelineUploadStatus enum
# ===========================================================================

class TestGuidelineUploadStatus:
    def test_pending_value(self):
        assert GuidelineUploadStatus.PENDING.value == "pending"

    def test_extracting_value(self):
        assert GuidelineUploadStatus.EXTRACTING.value == "extracting"

    def test_completed_value(self):
        assert GuidelineUploadStatus.COMPLETED.value == "completed"

    def test_failed_value(self):
        assert GuidelineUploadStatus.FAILED.value == "failed"

    def test_total_members(self):
        assert len(list(GuidelineUploadStatus)) == 7


# ===========================================================================
# GuidelineReference dataclass
# ===========================================================================

class TestGuidelineReference:
    def _make(self, **kwargs):
        defaults = dict(
            source="AHA/ACC",
            title="Hypertension Guidelines 2024",
            section="Section 8.2",
            recommendation_class="Class I",
            evidence_level="Level A",
        )
        defaults.update(kwargs)
        return GuidelineReference(**defaults)

    def test_required_fields_stored(self):
        ref = self._make()
        assert ref.source == "AHA/ACC"
        assert ref.title == "Hypertension Guidelines 2024"
        assert ref.section == "Section 8.2"
        assert ref.recommendation_class == "Class I"
        assert ref.evidence_level == "Level A"

    def test_year_defaults_none(self):
        assert self._make().year is None

    def test_url_defaults_none(self):
        assert self._make().url is None

    def test_year_can_be_set(self):
        ref = self._make(year=2024)
        assert ref.year == 2024

    def test_url_can_be_set(self):
        ref = self._make(url="https://example.org")
        assert ref.url == "https://example.org"


# ===========================================================================
# ComplianceItem dataclass
# ===========================================================================

class TestComplianceItem:
    def _ref(self):
        return GuidelineReference(
            source="ADA",
            title="Diabetes Guidelines",
            section="Section 5",
            recommendation_class="Class I",
            evidence_level="Level A",
        )

    def test_required_fields(self):
        item = ComplianceItem(
            guideline_ref=self._ref(),
            status="compliant",
            finding="HbA1c was documented",
            suggestion="Continue monitoring",
        )
        assert item.status == "compliant"
        assert "HbA1c" in item.finding

    def test_relevance_score_defaults_zero(self):
        item = ComplianceItem(
            guideline_ref=self._ref(),
            status="gap",
            finding="missing",
            suggestion="add it",
        )
        assert item.relevance_score == pytest.approx(0.0)

    def test_chunk_text_defaults_none(self):
        item = ComplianceItem(
            guideline_ref=self._ref(),
            status="gap",
            finding="missing",
            suggestion="add it",
        )
        assert item.chunk_text is None

    def test_custom_relevance_score(self):
        item = ComplianceItem(
            guideline_ref=self._ref(),
            status="warning",
            finding="borderline",
            suggestion="review",
            relevance_score=0.75,
        )
        assert item.relevance_score == pytest.approx(0.75)


# ===========================================================================
# ComplianceResult dataclass
# ===========================================================================

class TestComplianceResult:
    def test_overall_score_required(self):
        result = ComplianceResult(overall_score=0.85)
        assert result.overall_score == pytest.approx(0.85)

    def test_items_defaults_empty_list(self):
        result = ComplianceResult(overall_score=0.5)
        assert result.items == []

    def test_guidelines_checked_defaults_zero(self):
        result = ComplianceResult(overall_score=0.5)
        assert result.guidelines_checked == 0

    def test_compliant_count_defaults_zero(self):
        result = ComplianceResult(overall_score=0.5)
        assert result.compliant_count == 0

    def test_gap_count_defaults_zero(self):
        result = ComplianceResult(overall_score=0.5)
        assert result.gap_count == 0

    def test_warning_count_defaults_zero(self):
        result = ComplianceResult(overall_score=0.5)
        assert result.warning_count == 0

    def test_processing_time_ms_defaults_zero(self):
        result = ComplianceResult(overall_score=0.5)
        assert result.processing_time_ms == pytest.approx(0.0)

    def test_soap_note_summary_defaults_none(self):
        result = ComplianceResult(overall_score=0.5)
        assert result.soap_note_summary is None

    def test_specialties_analyzed_defaults_empty(self):
        result = ComplianceResult(overall_score=0.5)
        assert result.specialties_analyzed == []

    def test_instances_dont_share_items(self):
        r1 = ComplianceResult(overall_score=0.5)
        r2 = ComplianceResult(overall_score=0.5)
        r1.items.append("x")
        assert r2.items == []


# ===========================================================================
# ConditionFinding dataclass
# ===========================================================================

class TestConditionFinding:
    def test_required_fields(self):
        cf = ConditionFinding(
            status="ALIGNED",
            finding="Blood pressure is well controlled",
            guideline_reference="AHA/ACC HTN Guidelines 2024",
        )
        assert cf.status == "ALIGNED"
        assert "Blood pressure" in cf.finding

    def test_recommendation_defaults_empty_string(self):
        cf = ConditionFinding(status="ALIGNED", finding="ok", guideline_reference="ref")
        assert cf.recommendation == ""

    def test_citation_verified_defaults_false(self):
        cf = ConditionFinding(status="ALIGNED", finding="ok", guideline_reference="ref")
        assert cf.citation_verified is False

    def test_recommendation_can_be_set(self):
        cf = ConditionFinding(
            status="GAP", finding="missing", guideline_reference="ref",
            recommendation="Add ACE inhibitor"
        )
        assert cf.recommendation == "Add ACE inhibitor"


# ===========================================================================
# ConditionCompliance dataclass
# ===========================================================================

class TestConditionCompliance:
    def test_required_fields(self):
        cc = ConditionCompliance(condition="hypertension", status="ALIGNED")
        assert cc.condition == "hypertension"
        assert cc.status == "ALIGNED"

    def test_findings_defaults_empty(self):
        cc = ConditionCompliance(condition="hypertension", status="ALIGNED")
        assert cc.findings == []

    def test_score_defaults_zero(self):
        cc = ConditionCompliance(condition="hypertension", status="ALIGNED")
        assert cc.score == pytest.approx(0.0)

    def test_guidelines_matched_defaults_zero(self):
        cc = ConditionCompliance(condition="hypertension", status="ALIGNED")
        assert cc.guidelines_matched == 0

    def test_instances_dont_share_findings(self):
        c1 = ConditionCompliance(condition="a", status="ALIGNED")
        c2 = ConditionCompliance(condition="b", status="ALIGNED")
        c1.findings.append("finding")
        assert c2.findings == []


# ===========================================================================
# ComplianceAnalysisResult dataclass
# ===========================================================================

class TestComplianceAnalysisResult:
    def test_conditions_defaults_empty(self):
        result = ComplianceAnalysisResult()
        assert result.conditions == []

    def test_overall_score_defaults_zero(self):
        result = ComplianceAnalysisResult()
        assert result.overall_score == pytest.approx(0.0)

    def test_has_sufficient_data_defaults_false(self):
        result = ComplianceAnalysisResult()
        assert result.has_sufficient_data is False

    def test_guidelines_searched_defaults_zero(self):
        result = ComplianceAnalysisResult()
        assert result.guidelines_searched == 0

    def test_disclaimer_is_non_empty_string(self):
        result = ComplianceAnalysisResult()
        assert isinstance(result.disclaimer, str)
        assert len(result.disclaimer) > 0

    def test_disclaimer_mentions_ai(self):
        result = ComplianceAnalysisResult()
        assert "AI" in result.disclaimer or "clinical" in result.disclaimer.lower()

    def test_instances_dont_share_conditions(self):
        r1 = ComplianceAnalysisResult()
        r2 = ComplianceAnalysisResult()
        r1.conditions.append("something")
        assert r2.conditions == []


# ===========================================================================
# GuidelineMetadata Pydantic model
# ===========================================================================

class TestGuidelineMetadata:
    def test_title_defaults_none(self):
        m = GuidelineMetadata()
        assert m.title is None

    def test_specialty_defaults_general(self):
        m = GuidelineMetadata()
        assert m.specialty == GuidelineSpecialty.GENERAL

    def test_source_defaults_other(self):
        m = GuidelineMetadata()
        assert m.source == GuidelineSource.OTHER.value

    def test_version_defaults_none(self):
        m = GuidelineMetadata()
        assert m.version is None

    def test_document_type_defaults_treatment_protocol(self):
        m = GuidelineMetadata()
        assert m.document_type == GuidelineType.TREATMENT_PROTOCOL

    def test_authors_defaults_empty_list(self):
        m = GuidelineMetadata()
        assert m.authors == []

    def test_keywords_defaults_empty_list(self):
        m = GuidelineMetadata()
        assert m.keywords == []

    def test_conditions_covered_defaults_empty_list(self):
        m = GuidelineMetadata()
        assert m.conditions_covered == []

    def test_medications_covered_defaults_empty_list(self):
        m = GuidelineMetadata()
        assert m.medications_covered == []

    def test_superseded_by_defaults_none(self):
        m = GuidelineMetadata()
        assert m.superseded_by is None

    def test_instances_dont_share_authors(self):
        m1 = GuidelineMetadata()
        m2 = GuidelineMetadata()
        m1.authors.append("Dr. Smith")
        assert m2.authors == []


# ===========================================================================
# GuidelineChunk Pydantic model
# ===========================================================================

class TestGuidelineChunk:
    def test_required_fields(self):
        chunk = GuidelineChunk(chunk_index=0, chunk_text="recommendation text", token_count=10)
        assert chunk.chunk_index == 0
        assert chunk.chunk_text == "recommendation text"
        assert chunk.token_count == 10

    def test_section_type_defaults_recommendation(self):
        chunk = GuidelineChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.section_type == SectionType.RECOMMENDATION

    def test_recommendation_class_defaults_none(self):
        chunk = GuidelineChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.recommendation_class is None

    def test_evidence_level_defaults_none(self):
        chunk = GuidelineChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.evidence_level is None

    def test_neon_id_defaults_none(self):
        chunk = GuidelineChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.neon_id is None

    def test_embedding_defaults_none(self):
        chunk = GuidelineChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.embedding is None


# ===========================================================================
# GuidelineDocument Pydantic model
# ===========================================================================

class TestGuidelineDocument:
    def test_guideline_id_auto_generated(self):
        doc = GuidelineDocument(filename="aha_htn.pdf", file_type="pdf")
        assert doc.guideline_id is not None
        assert len(doc.guideline_id) > 0

    def test_two_documents_have_different_ids(self):
        d1 = GuidelineDocument(filename="a.pdf", file_type="pdf")
        d2 = GuidelineDocument(filename="b.pdf", file_type="pdf")
        assert d1.guideline_id != d2.guideline_id

    def test_upload_status_defaults_pending(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert doc.upload_status == GuidelineUploadStatus.PENDING.value

    def test_chunk_count_defaults_zero(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert doc.chunk_count == 0

    def test_neon_synced_defaults_false(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert doc.neon_synced is False

    def test_neo4j_synced_defaults_false(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert doc.neo4j_synced is False

    def test_error_message_defaults_none(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert doc.error_message is None

    def test_superseded_by_defaults_none(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert doc.superseded_by is None

    def test_metadata_is_guideline_metadata(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert isinstance(doc.metadata, GuidelineMetadata)

    def test_chunks_defaults_empty(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert doc.chunks == []

    def test_created_at_is_datetime(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert isinstance(doc.created_at, datetime)

    def test_updated_at_defaults_none(self):
        doc = GuidelineDocument(filename="test.pdf", file_type="pdf")
        assert doc.updated_at is None


# ===========================================================================
# GuidelineSearchQuery Pydantic model
# ===========================================================================

class TestGuidelineSearchQuery:
    def test_query_text_required(self):
        q = GuidelineSearchQuery(query_text="hypertension treatment")
        assert q.query_text == "hypertension treatment"

    def test_specialties_defaults_none(self):
        q = GuidelineSearchQuery(query_text="test")
        assert q.specialties is None

    def test_sources_defaults_none(self):
        q = GuidelineSearchQuery(query_text="test")
        assert q.sources is None

    def test_top_k_defaults_10(self):
        q = GuidelineSearchQuery(query_text="test")
        assert q.top_k == 10

    def test_similarity_threshold_defaults_0_6(self):
        q = GuidelineSearchQuery(query_text="test")
        assert q.similarity_threshold == pytest.approx(0.6)

    def test_include_metadata_defaults_true(self):
        q = GuidelineSearchQuery(query_text="test")
        assert q.include_metadata is True


# ===========================================================================
# GuidelineSearchResult Pydantic model
# ===========================================================================

class TestGuidelineSearchResult:
    def test_required_fields(self):
        r = GuidelineSearchResult(
            guideline_id="g1",
            chunk_index=0,
            chunk_text="recommendation text",
            similarity_score=0.9,
        )
        assert r.guideline_id == "g1"
        assert r.similarity_score == pytest.approx(0.9)

    def test_section_type_defaults_recommendation(self):
        r = GuidelineSearchResult(
            guideline_id="g1", chunk_index=0, chunk_text="text", similarity_score=0.5
        )
        assert r.section_type == SectionType.RECOMMENDATION.value

    def test_is_superseded_defaults_false(self):
        r = GuidelineSearchResult(
            guideline_id="g1", chunk_index=0, chunk_text="text", similarity_score=0.5
        )
        assert r.is_superseded is False

    def test_optional_fields_default_none(self):
        r = GuidelineSearchResult(
            guideline_id="g1", chunk_index=0, chunk_text="text", similarity_score=0.5
        )
        assert r.recommendation_class is None
        assert r.evidence_level is None
        assert r.guideline_title is None


# ===========================================================================
# GuidelineUploadRequest Pydantic model
# ===========================================================================

class TestGuidelineUploadRequest:
    def test_file_paths_required(self):
        req = GuidelineUploadRequest(file_paths=["/tmp/aha.pdf"])
        assert req.file_paths == ["/tmp/aha.pdf"]

    def test_specialty_defaults_general(self):
        req = GuidelineUploadRequest(file_paths=[])
        assert req.specialty == GuidelineSpecialty.GENERAL.value

    def test_source_defaults_other(self):
        req = GuidelineUploadRequest(file_paths=[])
        assert req.source == GuidelineSource.OTHER.value

    def test_document_type_defaults_treatment_protocol(self):
        req = GuidelineUploadRequest(file_paths=[])
        assert req.document_type == GuidelineType.TREATMENT_PROTOCOL.value

    def test_extract_recommendations_defaults_true(self):
        req = GuidelineUploadRequest(file_paths=[])
        assert req.extract_recommendations is True

    def test_build_knowledge_graph_defaults_true(self):
        req = GuidelineUploadRequest(file_paths=[])
        assert req.build_knowledge_graph is True

    def test_keywords_defaults_empty(self):
        req = GuidelineUploadRequest(file_paths=[])
        assert req.keywords == []


# ===========================================================================
# GuidelineUploadProgress Pydantic model
# ===========================================================================

class TestGuidelineUploadProgress:
    def test_required_fields(self):
        prog = GuidelineUploadProgress(
            guideline_id="g1",
            filename="aha.pdf",
            status=GuidelineUploadStatus.EXTRACTING,
        )
        assert prog.guideline_id == "g1"
        assert prog.filename == "aha.pdf"

    def test_progress_percent_defaults_zero(self):
        prog = GuidelineUploadProgress(
            guideline_id="g1", filename="aha.pdf", status=GuidelineUploadStatus.PENDING
        )
        assert prog.progress_percent == pytest.approx(0.0)

    def test_current_step_defaults_empty(self):
        prog = GuidelineUploadProgress(
            guideline_id="g1", filename="aha.pdf", status=GuidelineUploadStatus.PENDING
        )
        assert prog.current_step == ""

    def test_error_message_defaults_none(self):
        prog = GuidelineUploadProgress(
            guideline_id="g1", filename="aha.pdf", status=GuidelineUploadStatus.PENDING
        )
        assert prog.error_message is None


# ===========================================================================
# GuidelinesSettings Pydantic model
# ===========================================================================

class TestGuidelinesSettings:
    def test_guidelines_database_url_defaults_none(self):
        s = GuidelinesSettings()
        assert s.guidelines_database_url is None

    def test_guidelines_pool_size_defaults_8(self):
        s = GuidelinesSettings()
        assert s.guidelines_pool_size == 8

    def test_neo4j_uri_defaults_none(self):
        s = GuidelinesSettings()
        assert s.neo4j_uri is None

    def test_embedding_model_default(self):
        s = GuidelinesSettings()
        assert s.embedding_model == "text-embedding-3-small"

    def test_embedding_dimensions_default(self):
        s = GuidelinesSettings()
        assert s.embedding_dimensions == 1536

    def test_chunk_size_tokens_default(self):
        s = GuidelinesSettings()
        assert s.chunk_size_tokens == 500

    def test_chunk_overlap_tokens_default(self):
        s = GuidelinesSettings()
        assert s.chunk_overlap_tokens == 100

    def test_max_chunks_per_guideline_default(self):
        s = GuidelinesSettings()
        assert s.max_chunks_per_guideline == 500

    def test_default_top_k_default(self):
        s = GuidelinesSettings()
        assert s.default_top_k == 10

    def test_default_similarity_threshold_default(self):
        s = GuidelinesSettings()
        assert s.default_similarity_threshold == pytest.approx(0.6)

    def test_hnsw_ef_search_default(self):
        s = GuidelinesSettings()
        assert s.hnsw_ef_search == 100

    def test_enable_auto_compliance_check_defaults_true(self):
        s = GuidelinesSettings()
        assert s.enable_auto_compliance_check is True

    def test_compliance_delay_ms_default(self):
        s = GuidelinesSettings()
        assert s.compliance_delay_ms == 300

    def test_min_compliance_score_warning_default(self):
        s = GuidelinesSettings()
        assert s.min_compliance_score_warning == pytest.approx(0.7)


# ===========================================================================
# ComplianceCheckRequest Pydantic model
# ===========================================================================

class TestComplianceCheckRequest:
    def test_soap_note_required(self):
        req = ComplianceCheckRequest(soap_note="S: Patient presents with...\nO: BP 140/90...")
        assert "Patient" in req.soap_note

    def test_specialties_defaults_none(self):
        req = ComplianceCheckRequest(soap_note="test")
        assert req.specialties is None

    def test_sources_defaults_none(self):
        req = ComplianceCheckRequest(soap_note="test")
        assert req.sources is None

    def test_max_guidelines_defaults_10(self):
        req = ComplianceCheckRequest(soap_note="test")
        assert req.max_guidelines == 10

    def test_include_all_matches_defaults_false(self):
        req = ComplianceCheckRequest(soap_note="test")
        assert req.include_all_matches is False


# ===========================================================================
# ComplianceCheckResponse Pydantic model
# ===========================================================================

class TestComplianceCheckResponse:
    def _make(self, **kwargs):
        defaults = dict(
            overall_score=0.8,
            compliant_count=5,
            gap_count=2,
            warning_count=1,
            not_applicable_count=0,
            items=[],
            guidelines_checked=8,
            specialties_analyzed=["cardiology"],
            processing_time_ms=350.0,
        )
        defaults.update(kwargs)
        return ComplianceCheckResponse(**defaults)

    def test_overall_score_stored(self):
        assert self._make().overall_score == pytest.approx(0.8)

    def test_compliant_count_stored(self):
        assert self._make().compliant_count == 5

    def test_gap_count_stored(self):
        assert self._make().gap_count == 2

    def test_items_is_list(self):
        assert isinstance(self._make().items, list)

    def test_specialties_analyzed_stored(self):
        r = self._make(specialties_analyzed=["cardiology", "nephrology"])
        assert "cardiology" in r.specialties_analyzed
