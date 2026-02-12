"""
Unit tests for ComplianceAgent.

Tests cover:
- Condition extraction from SOAP notes
- Per-condition guideline retrieval
- Compliance status determination (ALIGNED, GAP, REVIEW)
- Compliance score calculation
- Citation verification
- Structured data parsing
- Fallback parsing from free text
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from ai.agents.compliance import ComplianceAgent, DISCLAIMER
from ai.agents.models import AgentConfig, AgentTask, AgentResponse
from ai.agents.ai_caller import MockAICaller


@pytest.fixture
def compliance_agent(mock_ai_caller):
    """Create a ComplianceAgent with mock AI caller."""
    return ComplianceAgent(ai_caller=mock_ai_caller)


@pytest.fixture
def sample_soap_note():
    """Sample SOAP note for compliance testing."""
    return """S: 55-year-old male with Type 2 diabetes and hypertension.
Complains of increased thirst and frequent urination.
O: BP 148/92 mmHg, HR 82 bpm, BMI 31.
Fasting glucose: 185 mg/dL, HbA1c: 8.2%
A: 1. Type 2 Diabetes Mellitus, uncontrolled (E11.65)
   2. Essential Hypertension (I10)
   3. Obesity (E66.9)
P: 1. Increase metformin to 1000mg BID
   2. Start lisinopril 10mg daily
   3. Dietary counseling
   4. Follow-up in 4 weeks"""


@pytest.fixture
def sample_json_response():
    """Sample structured JSON response from LLM."""
    return json.dumps({
        "conditions": [
            {
                "condition": "Type 2 Diabetes Mellitus",
                "findings": [
                    {
                        "status": "ALIGNED",
                        "finding": "Metformin first-line therapy appropriately initiated",
                        "guideline_reference": "ADA Standards 2024: Metformin is recommended as first-line therapy",
                        "recommendation": ""
                    },
                    {
                        "status": "GAP",
                        "finding": "Statin therapy not documented for diabetic patient",
                        "guideline_reference": "ADA Standards 2024: Moderate-intensity statin recommended for all diabetic patients 40-75",
                        "recommendation": "Initiate moderate-intensity statin per ADA guidelines"
                    }
                ]
            },
            {
                "condition": "Essential Hypertension",
                "findings": [
                    {
                        "status": "REVIEW",
                        "finding": "BP target not achieved, lisinopril just started",
                        "guideline_reference": "AHA/ACC 2024: Target BP < 130/80 for diabetic patients",
                        "recommendation": "Re-evaluate BP control at 4-week follow-up"
                    }
                ]
            }
        ]
    })


@pytest.fixture
def sample_legacy_text_response():
    """Sample legacy free-text response (fallback parsing)."""
    return """
1. COMPLIANCE SUMMARY
   Overall, the SOAP note demonstrates partial adherence to clinical guidelines.

2. DETAILED COMPLIANCE FINDINGS

[ALIGNED] ADA Standards 2024 - Metformin first-line therapy appropriately initiated
- Recommendation: Continue as first-line agent
- Evidence: Class I, Level A

[GAP] AHA/ACC Hypertension 2024, Section 8.2 - BP target not achieved
- Recommendation: Consider adding second antihypertensive agent
- Evidence: Class I, Level B

[GAP] ADA Standards 2024 - Statin therapy not documented for diabetic patient
- Recommendation: Initiate moderate-intensity statin per ADA guidelines
- Evidence: Class I, Level A

[REVIEW] ADA 2024 - HbA1c above target (>7%)
- Recommendation: Consider treatment intensification
- Note: Some flexibility allowed based on patient factors
"""


class TestComplianceAnalysis:
    """Tests for compliance analysis execution."""

    def test_basic_compliance_analysis(self, compliance_agent, mock_ai_caller, sample_soap_note, sample_json_response):
        """Test basic compliance analysis execution."""
        # First call: NER fallback extraction
        extraction_json = json.dumps({
            "conditions": [{"condition": "Type 2 Diabetes", "medications": ["metformin"]}]
        })
        mock_ai_caller.default_response = extraction_json

        task = AgentTask(
            task_description="Check SOAP note compliance",
            input_data={"soap_note": sample_soap_note}
        )

        # Patch NER availability and guidelines
        with patch('ai.agents.compliance.NER_AVAILABLE', False):
            with patch('ai.agents.compliance.GUIDELINES_AVAILABLE', True):
                with patch('ai.agents.compliance.get_guidelines_retriever') as mock_ret:
                    retriever = Mock()
                    retriever.get_guidelines_for_conditions.return_value = {
                        "Type 2 Diabetes": [Mock(
                            guideline_id="g1", chunk_index=0,
                            chunk_text="Metformin is recommended",
                            guideline_source="ADA", guideline_title="Standards 2024",
                            guideline_version="2024", recommendation_class="I",
                            evidence_level="A", similarity_score=0.9
                        )]
                    }
                    mock_ret.return_value = retriever

                    # Override responses: first call = extraction, second = analysis
                    call_count = [0]
                    def side_effect(**kwargs):
                        call_count[0] += 1
                        if call_count[0] == 1:
                            return extraction_json
                        return sample_json_response
                    mock_ai_caller.call = side_effect

                    response = compliance_agent.execute(task)

        assert response.success is True
        assert "compliant_count" in response.metadata
        assert "gap_count" in response.metadata
        assert "warning_count" in response.metadata
        assert "has_sufficient_data" in response.metadata

    def test_compliance_with_specialties(self, compliance_agent, mock_ai_caller, sample_soap_note, sample_json_response):
        """Test compliance analysis with specialty filter."""
        extraction_json = json.dumps({
            "conditions": [{"condition": "Hypertension", "medications": ["lisinopril"]}]
        })

        call_count = [0]
        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return extraction_json
            return sample_json_response
        mock_ai_caller.call = side_effect

        task = AgentTask(
            task_description="Check compliance",
            input_data={
                "soap_note": sample_soap_note,
                "specialties": ["cardiology", "endocrinology"]
            }
        )

        with patch('ai.agents.compliance.NER_AVAILABLE', False):
            with patch('ai.agents.compliance.GUIDELINES_AVAILABLE', True):
                with patch('ai.agents.compliance.get_guidelines_retriever') as mock_ret:
                    retriever = Mock()
                    retriever.get_guidelines_for_conditions.return_value = {
                        "Hypertension": [Mock(
                            guideline_id="g1", chunk_index=0,
                            chunk_text="BP target guidelines",
                            guideline_source="AHA", guideline_title="HTN 2024",
                            guideline_version="2024", recommendation_class="I",
                            evidence_level="A", similarity_score=0.8
                        )]
                    }
                    mock_ret.return_value = retriever
                    response = compliance_agent.execute(task)

        assert response.success is True
        assert "cardiology" in response.metadata.get("specialties_analyzed", [])

    def test_compliance_without_soap_note(self, compliance_agent, mock_ai_caller):
        """Test compliance analysis without SOAP note."""
        task = AgentTask(
            task_description="Check compliance",
            input_data={}
        )

        response = compliance_agent.execute(task)

        assert response.success is False
        assert "No SOAP note provided" in response.error


class TestFallbackParsing:
    """Tests for fallback text parsing when JSON parsing fails."""

    def test_fallback_parse_aligned(self, compliance_agent, sample_legacy_text_response):
        """Test fallback parsing extracts ALIGNED items."""
        result = compliance_agent._fallback_parse(sample_legacy_text_response, [])
        aligned = sum(
            1 for cc in result.conditions
            for f in cc.findings
            if (f.status if hasattr(f, 'status') else f['status']) == 'ALIGNED'
        )
        assert aligned >= 1

    def test_fallback_parse_gaps(self, compliance_agent, sample_legacy_text_response):
        """Test fallback parsing extracts GAP items."""
        result = compliance_agent._fallback_parse(sample_legacy_text_response, [])
        gaps = sum(
            1 for cc in result.conditions
            for f in cc.findings
            if (f.status if hasattr(f, 'status') else f['status']) == 'GAP'
        )
        assert gaps >= 2

    def test_fallback_parse_review(self, compliance_agent, sample_legacy_text_response):
        """Test fallback parsing extracts REVIEW items (mapped from WARNING)."""
        result = compliance_agent._fallback_parse(sample_legacy_text_response, [])
        reviews = sum(
            1 for cc in result.conditions
            for f in cc.findings
            if (f.status if hasattr(f, 'status') else f['status']) == 'REVIEW'
        )
        assert reviews >= 1

    def test_fallback_parse_case_insensitive(self, compliance_agent):
        """Test that fallback parsing is case-insensitive."""
        analysis = """
        [aligned] Guideline 1 - Finding
        [ALIGNED] Guideline 2 - Finding
        [Aligned] Guideline 3 - Finding
        """
        result = compliance_agent._fallback_parse(analysis, [])
        aligned = sum(
            1 for cc in result.conditions
            for f in cc.findings
            if (f.status if hasattr(f, 'status') else f['status']) == 'ALIGNED'
        )
        assert aligned == 3


class TestScoreCalculation:
    """Tests for compliance score calculation."""

    def test_perfect_alignment_score(self, compliance_agent):
        """Test score calculation for perfect alignment."""
        from rag.guidelines_models import ComplianceAnalysisResult, ConditionCompliance, ConditionFinding

        result = ComplianceAnalysisResult(
            conditions=[
                ConditionCompliance(
                    condition="HTN",
                    status="ALIGNED",
                    findings=[
                        ConditionFinding(status="ALIGNED", finding="Good", guideline_reference="ref"),
                        ConditionFinding(status="ALIGNED", finding="Good", guideline_reference="ref"),
                    ],
                    guidelines_matched=2,
                )
            ],
            has_sufficient_data=True,
        )

        compliance_agent._compute_scores(result)

        assert result.overall_score == 1.0
        assert result.conditions[0].score == 1.0
        assert result.conditions[0].status == 'ALIGNED'

    def test_zero_score_all_gaps(self, compliance_agent):
        """Test score calculation for all gaps."""
        from rag.guidelines_models import ComplianceAnalysisResult, ConditionCompliance, ConditionFinding

        result = ComplianceAnalysisResult(
            conditions=[
                ConditionCompliance(
                    condition="DM",
                    status="GAP",
                    findings=[
                        ConditionFinding(status="GAP", finding="Missing", guideline_reference="ref"),
                        ConditionFinding(status="GAP", finding="Missing", guideline_reference="ref"),
                    ],
                    guidelines_matched=2,
                )
            ],
            has_sufficient_data=True,
        )

        compliance_agent._compute_scores(result)

        assert result.overall_score == 0.0
        assert result.conditions[0].status == 'GAP'

    def test_no_findings_zero_score(self, compliance_agent):
        """Test score when no findings — should be 0, not 100%."""
        from rag.guidelines_models import ComplianceAnalysisResult, ConditionCompliance

        result = ComplianceAnalysisResult(
            conditions=[
                ConditionCompliance(
                    condition="Unknown",
                    status="REVIEW",
                    findings=[],
                    guidelines_matched=0,
                )
            ],
            has_sufficient_data=True,
        )

        compliance_agent._compute_scores(result)

        assert result.overall_score == 0.0

    def test_mixed_score(self, compliance_agent):
        """Test score with mixed statuses."""
        from rag.guidelines_models import ComplianceAnalysisResult, ConditionCompliance, ConditionFinding

        result = ComplianceAnalysisResult(
            conditions=[
                ConditionCompliance(
                    condition="HTN",
                    status="REVIEW",
                    findings=[
                        ConditionFinding(status="ALIGNED", finding="OK", guideline_reference="ref"),
                        ConditionFinding(status="GAP", finding="Missing", guideline_reference="ref"),
                        ConditionFinding(status="REVIEW", finding="Unclear", guideline_reference="ref"),
                    ],
                    guidelines_matched=3,
                )
            ],
            has_sufficient_data=True,
        )

        compliance_agent._compute_scores(result)

        # aligned=1, gap=1, review=1 => denominator = 1 + 1 + 0.5 = 2.5
        # score = 1 / 2.5 = 0.4
        assert result.overall_score == 0.4
        assert result.conditions[0].status == 'GAP'  # worst finding


class TestCitationVerification:
    """Tests for citation verification against guideline text."""

    def test_verified_citation(self, compliance_agent):
        """Test citation that matches guideline text."""
        guideline_texts = [
            "metformin is recommended as first-line therapy for type 2 diabetes management"
        ]
        ref = "Metformin is recommended as first-line therapy"

        assert compliance_agent._verify_citation(ref, guideline_texts) is True

    def test_unverified_citation(self, compliance_agent):
        """Test citation that doesn't match any guideline text."""
        guideline_texts = [
            "blood pressure targets should be below 130/80"
        ]
        ref = "Aspirin is recommended for all patients over 50"

        assert compliance_agent._verify_citation(ref, guideline_texts) is False

    def test_empty_citation(self, compliance_agent):
        """Test empty citation returns False."""
        assert compliance_agent._verify_citation("", ["some text"]) is False
        assert compliance_agent._verify_citation("short", ["some text"]) is False

    def test_no_guideline_texts(self, compliance_agent):
        """Test empty guideline list returns False."""
        assert compliance_agent._verify_citation("some reference", []) is False


class TestJSONParsing:
    """Tests for parsing JSON LLM responses."""

    def test_parse_valid_json(self, compliance_agent, sample_json_response):
        """Test parsing a valid JSON response."""
        result = compliance_agent._parse_analysis_response(
            sample_json_response, {}
        )

        assert len(result.conditions) == 2
        assert result.conditions[0].condition == "Type 2 Diabetes Mellitus"
        assert result.has_sufficient_data is True

    def test_parse_with_markdown_fences(self, compliance_agent):
        """Test parsing JSON wrapped in markdown code fences."""
        response = '```json\n{"conditions": [{"condition": "HTN", "findings": []}]}\n```'

        result = compliance_agent._parse_analysis_response(response, {})

        assert len(result.conditions) == 1

    def test_parse_invalid_json_falls_back(self, compliance_agent):
        """Test that invalid JSON falls back to regex parsing."""
        response = "[ALIGNED] ADA 2024 - Good therapy\n[GAP] AHA 2024 - Missing statin"

        result = compliance_agent._parse_analysis_response(response, {})

        # Should still parse via fallback
        total_findings = sum(len(cc.findings) for cc in result.conditions)
        assert total_findings >= 2


class TestConvenienceMethods:
    """Tests for convenience methods."""

    def test_check_compliance_method(self, compliance_agent, mock_ai_caller, sample_soap_note, sample_json_response):
        """Test the check_compliance convenience method."""
        extraction_json = json.dumps({
            "conditions": [{"condition": "DM", "medications": ["metformin"]}]
        })
        call_count = [0]
        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return extraction_json
            return sample_json_response
        mock_ai_caller.call = side_effect

        with patch('ai.agents.compliance.NER_AVAILABLE', False):
            with patch('ai.agents.compliance.GUIDELINES_AVAILABLE', True):
                with patch('ai.agents.compliance.get_guidelines_retriever') as mock_ret:
                    retriever = Mock()
                    retriever.get_guidelines_for_conditions.return_value = {
                        "DM": [Mock(
                            guideline_id="g1", chunk_index=0,
                            chunk_text="DM guidelines", guideline_source="ADA",
                            guideline_title="Standards", guideline_version="2024",
                            recommendation_class="I", evidence_level="A",
                            similarity_score=0.8
                        )]
                    }
                    mock_ret.return_value = retriever
                    response = compliance_agent.check_compliance(
                        soap_note=sample_soap_note,
                        specialties=["cardiology"],
                        sources=["AHA"]
                    )

        assert response.success is True

    def test_get_compliance_summary_success(self, compliance_agent):
        """Test getting summary from successful response."""
        response = AgentResponse(
            result="Analysis",
            success=True,
            metadata={
                "overall_score": 0.75,
                "has_sufficient_data": True,
                "compliant_count": 3,
                "gap_count": 1,
                "warning_count": 0,
                "conditions_count": 2,
            }
        )

        summary = compliance_agent.get_compliance_summary(response)

        assert "75%" in summary
        assert "3 aligned" in summary
        assert "1 gap" in summary

    def test_get_compliance_summary_failure(self, compliance_agent):
        """Test getting summary from failed response."""
        response = AgentResponse(
            result="",
            success=False,
            error="Analysis failed"
        )

        summary = compliance_agent.get_compliance_summary(response)

        assert "failed" in summary.lower()

    def test_get_compliance_summary_insufficient_data(self, compliance_agent):
        """Test summary when insufficient data."""
        response = AgentResponse(
            result="No guidelines",
            success=True,
            metadata={
                "overall_score": 0.0,
                "has_sufficient_data": False,
                "compliant_count": 0,
                "gap_count": 0,
                "warning_count": 0,
                "conditions_count": 0,
            }
        )

        summary = compliance_agent.get_compliance_summary(response)

        assert "insufficient" in summary.lower()


class TestInsufficientData:
    """Tests for insufficient data handling."""

    def test_no_conditions_extracted(self, compliance_agent, mock_ai_caller):
        """Test when no conditions can be extracted from SOAP note."""
        mock_ai_caller.default_response = '{"conditions": []}'

        task = AgentTask(
            task_description="Check compliance",
            input_data={"soap_note": "Patient was seen today. No issues."}
        )

        with patch('ai.agents.compliance.NER_AVAILABLE', False):
            response = compliance_agent.execute(task)

        assert response.success is True
        assert response.metadata["has_sufficient_data"] is False
        assert response.metadata["overall_score"] == 0.0

    def test_no_guidelines_found(self, compliance_agent, mock_ai_caller, sample_soap_note):
        """Test when no matching guidelines are found."""
        extraction_json = json.dumps({
            "conditions": [{"condition": "Rare Disease", "medications": []}]
        })
        mock_ai_caller.default_response = extraction_json

        with patch('ai.agents.compliance.NER_AVAILABLE', False):
            with patch('ai.agents.compliance.GUIDELINES_AVAILABLE', True):
                with patch('ai.agents.compliance.get_guidelines_retriever') as mock_ret:
                    retriever = Mock()
                    retriever.get_guidelines_for_conditions.return_value = {}
                    mock_ret.return_value = retriever

                    task = AgentTask(
                        task_description="Check compliance",
                        input_data={"soap_note": sample_soap_note}
                    )
                    response = compliance_agent.execute(task)

        assert response.success is True
        assert response.metadata["has_sufficient_data"] is False


class TestErrorHandling:
    """Tests for error handling."""

    def test_exception_during_analysis(self, compliance_agent, mock_ai_caller, sample_soap_note):
        """Test handling of exceptions during analysis.

        When NER is unavailable and LLM extraction also fails,
        the agent returns an insufficient-data response (success=True)
        rather than propagating the error.
        """
        mock_ai_caller.call = Mock(side_effect=Exception("API error"))

        task = AgentTask(
            task_description="Check compliance",
            input_data={"soap_note": sample_soap_note}
        )

        with patch('ai.agents.compliance.NER_AVAILABLE', False):
            response = compliance_agent.execute(task)

        # Agent gracefully handles extraction failure as insufficient data
        assert response.success is True
        assert response.metadata["has_sufficient_data"] is False
        assert "Could not extract" in response.result


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_exists(self):
        """Test that default config is properly defined."""
        assert ComplianceAgent.DEFAULT_CONFIG is not None
        assert ComplianceAgent.DEFAULT_CONFIG.name == "ComplianceAgent"

    def test_default_config_low_temperature(self):
        """Test temperature is low for consistent analysis."""
        assert ComplianceAgent.DEFAULT_CONFIG.temperature <= 0.3

    def test_default_config_sufficient_tokens(self):
        """Test max tokens allows for detailed analysis."""
        assert ComplianceAgent.DEFAULT_CONFIG.max_tokens >= 4000

    def test_system_prompt_focuses_on_treatment(self):
        """Test system prompt focuses on treatment alignment, not documentation."""
        prompt = ComplianceAgent.DEFAULT_CONFIG.system_prompt.lower()
        assert "treatment alignment" in prompt
        assert "aligned" in prompt
        assert "gap" in prompt
        assert "review" in prompt
