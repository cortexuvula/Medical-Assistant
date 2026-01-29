"""
Unit tests for ComplianceAgent.

Tests cover:
- Guidelines retrieval and matching
- Compliance status determination (COMPLIANT, GAP, WARNING)
- Compliance score calculation
- Structured data extraction from analysis
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import re

from ai.agents.compliance import ComplianceAgent
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
def sample_compliance_analysis():
    """Sample compliance analysis output."""
    return """
1. COMPLIANCE SUMMARY
   Overall, the SOAP note demonstrates partial adherence to clinical guidelines.
   Key compliance areas: Metformin as first-line therapy
   Key gaps: BP not at target, no statin documented

2. DETAILED COMPLIANCE FINDINGS

[COMPLIANT] ADA Standards 2024 - Metformin first-line therapy appropriately initiated
- Recommendation: Continue as first-line agent
- Evidence: Class I, Level A

[GAP] AHA/ACC Hypertension 2024, Section 8.2 - BP target not achieved
- Recommendation: Consider adding second antihypertensive agent
- Evidence: Class I, Level B

[GAP] ADA Standards 2024 - Statin therapy not documented for diabetic patient
- Recommendation: Initiate moderate-intensity statin per ADA guidelines
- Evidence: Class I, Level A

[WARNING] ADA 2024 - HbA1c above target (>7%)
- Recommendation: Consider treatment intensification
- Note: Some flexibility allowed based on patient factors

3. IMPROVEMENT OPPORTUNITIES
   - Add statin therapy
   - Achieve BP target < 130/80
   - Consider GLP-1 agonist for weight management
"""


class TestComplianceAnalysis:
    """Tests for compliance analysis execution."""

    def test_basic_compliance_analysis(self, compliance_agent, mock_ai_caller, sample_soap_note):
        """Test basic compliance analysis execution."""
        mock_ai_caller.default_response = "[COMPLIANT] Test guideline - Finding"

        task = AgentTask(
            task_description="Check SOAP note compliance",
            input_data={"soap_note": sample_soap_note}
        )

        response = compliance_agent.execute(task)

        assert response.success is True
        assert "compliant_count" in response.metadata
        assert "gap_count" in response.metadata
        assert "warning_count" in response.metadata

    def test_compliance_with_specialties(self, compliance_agent, mock_ai_caller, sample_soap_note):
        """Test compliance analysis with specialty filter."""
        mock_ai_caller.default_response = "[COMPLIANT] Cardiology guideline - BP management"

        task = AgentTask(
            task_description="Check compliance",
            input_data={
                "soap_note": sample_soap_note,
                "specialties": ["cardiology", "endocrinology"]
            }
        )

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


class TestComplianceStatusExtraction:
    """Tests for extracting compliance status from analysis."""

    def test_extract_compliant_count(self, compliance_agent, sample_compliance_analysis):
        """Test counting COMPLIANT items."""
        data = compliance_agent._extract_compliance_data(sample_compliance_analysis)

        assert data["compliant_count"] == 1

    def test_extract_gap_count(self, compliance_agent, sample_compliance_analysis):
        """Test counting GAP items."""
        data = compliance_agent._extract_compliance_data(sample_compliance_analysis)

        assert data["gap_count"] == 2

    def test_extract_warning_count(self, compliance_agent, sample_compliance_analysis):
        """Test counting WARNING items."""
        data = compliance_agent._extract_compliance_data(sample_compliance_analysis)

        assert data["warning_count"] == 1

    def test_extract_case_insensitive(self, compliance_agent):
        """Test that status extraction is case-insensitive."""
        analysis = """
        [compliant] Guideline 1 - Finding
        [COMPLIANT] Guideline 2 - Finding
        [Compliant] Guideline 3 - Finding
        """

        data = compliance_agent._extract_compliance_data(analysis)

        assert data["compliant_count"] == 3


class TestComplianceScoreCalculation:
    """Tests for compliance score calculation."""

    def test_perfect_compliance_score(self, compliance_agent):
        """Test score calculation for perfect compliance."""
        analysis = """
        [COMPLIANT] Guideline 1 - Finding
        [COMPLIANT] Guideline 2 - Finding
        [COMPLIANT] Guideline 3 - Finding
        """

        data = compliance_agent._extract_compliance_data(analysis)

        assert data["overall_score"] == 1.0

    def test_partial_compliance_score(self, compliance_agent, sample_compliance_analysis):
        """Test score calculation for partial compliance."""
        data = compliance_agent._extract_compliance_data(sample_compliance_analysis)

        # 1 compliant + 0.5 * 1 warning = 1.5 out of 4 total = 0.375
        assert 0 < data["overall_score"] < 1

    def test_zero_compliance_score(self, compliance_agent):
        """Test score calculation for all gaps."""
        analysis = """
        [GAP] Guideline 1 - Missing
        [GAP] Guideline 2 - Missing
        """

        data = compliance_agent._extract_compliance_data(analysis)

        assert data["overall_score"] == 0.0

    def test_no_items_score(self, compliance_agent):
        """Test score when no compliance items found."""
        analysis = "No specific guidelines applicable."

        data = compliance_agent._extract_compliance_data(analysis)

        # No issues found = fully compliant
        assert data["overall_score"] == 1.0

    def test_warnings_count_as_half(self, compliance_agent):
        """Test that warnings count as 0.5 in score."""
        analysis = """
        [WARNING] Guideline 1 - Review needed
        [WARNING] Guideline 2 - Review needed
        """

        data = compliance_agent._extract_compliance_data(analysis)

        # 2 warnings * 0.5 / 2 total = 0.5
        assert data["overall_score"] == 0.5


class TestComplianceItemExtraction:
    """Tests for extracting individual compliance items."""

    def test_extract_compliance_items(self, compliance_agent, sample_compliance_analysis):
        """Test extraction of compliance items."""
        items = compliance_agent._extract_compliance_items(sample_compliance_analysis)

        assert len(items) >= 4
        assert all("status" in item for item in items)
        assert all("finding" in item for item in items)

    def test_item_status_extraction(self, compliance_agent):
        """Test status is correctly extracted for each item."""
        analysis = """
        [COMPLIANT] ADA 2024 - Metformin prescribed
        [GAP] AHA 2024 - Missing statin
        """

        items = compliance_agent._extract_compliance_items(analysis)

        statuses = [item["status"] for item in items]
        assert "COMPLIANT" in statuses
        assert "GAP" in statuses

    def test_item_guideline_source_extraction(self, compliance_agent):
        """Test guideline source is extracted."""
        analysis = "[COMPLIANT] ADA Standards 2024, Section 9.1 - Appropriate therapy"

        items = compliance_agent._extract_compliance_items(analysis)

        if items:
            assert "ADA" in items[0]["guideline_source"]

    def test_item_recommendation_extraction(self, compliance_agent):
        """Test recommendation extraction."""
        analysis = """
        [GAP] AHA 2024 - BP above target
        - Recommendation: Add second antihypertensive
        - Evidence: Class I, Level B
        """

        items = compliance_agent._extract_compliance_items(analysis)

        if items:
            assert "antihypertensive" in items[0].get("recommendation", "").lower()


class TestPromptBuilding:
    """Tests for compliance prompt building."""

    def test_build_prompt_with_context(self, compliance_agent, sample_soap_note):
        """Test prompt building with additional context."""
        prompt = compliance_agent._build_compliance_prompt(
            soap_note=sample_soap_note,
            guidelines_context="Relevant guidelines: ADA 2024...",
            additional_context="Focus on diabetes management"
        )

        assert sample_soap_note in prompt
        assert "ADA 2024" in prompt
        assert "Focus on diabetes" in prompt

    def test_build_prompt_without_context(self, compliance_agent, sample_soap_note):
        """Test prompt building without additional context."""
        prompt = compliance_agent._build_compliance_prompt(
            soap_note=sample_soap_note,
            guidelines_context="Guidelines...",
            additional_context=None
        )

        assert sample_soap_note in prompt
        assert "Guidelines" in prompt


class TestGuidelinesIntegration:
    """Tests for guidelines retriever integration."""

    def test_guidelines_available(self, compliance_agent, mock_ai_caller, sample_soap_note):
        """Test when guidelines retriever is available."""
        mock_ai_caller.default_response = "[COMPLIANT] Test - Finding"

        with patch('ai.agents.compliance.GUIDELINES_AVAILABLE', True):
            with patch('ai.agents.compliance.get_guidelines_retriever') as mock_retriever:
                retriever_instance = Mock()
                retriever_instance.get_guideline_context.return_value = "## Guideline 1\n## Guideline 2"
                mock_retriever.return_value = retriever_instance

                task = AgentTask(
                    task_description="Check compliance",
                    input_data={"soap_note": sample_soap_note}
                )

                response = compliance_agent.execute(task)

                assert response.success is True
                assert response.metadata["guidelines_checked"] >= 0

    def test_guidelines_unavailable(self, compliance_agent, mock_ai_caller, sample_soap_note):
        """Test when guidelines retriever is not available."""
        mock_ai_caller.default_response = "[COMPLIANT] Basic check - Passed"

        with patch('ai.agents.compliance.GUIDELINES_AVAILABLE', False):
            task = AgentTask(
                task_description="Check compliance",
                input_data={"soap_note": sample_soap_note}
            )

            response = compliance_agent.execute(task)

            # Should still succeed but with limited guidelines
            assert response.success is True
            assert response.metadata["guidelines_available"] is False


class TestConvenienceMethods:
    """Tests for convenience methods."""

    def test_check_compliance_method(self, compliance_agent, mock_ai_caller, sample_soap_note):
        """Test the check_compliance convenience method."""
        mock_ai_caller.default_response = "[COMPLIANT] Test - OK"

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
                "compliant_count": 3,
                "gap_count": 1,
                "warning_count": 0
            }
        )

        summary = compliance_agent.get_compliance_summary(response)

        assert "75%" in summary
        assert "3 compliant" in summary
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

    def test_get_compliance_summary_no_guidelines(self, compliance_agent):
        """Test summary when no guidelines found."""
        response = AgentResponse(
            result="No applicable guidelines",
            success=True,
            metadata={
                "overall_score": 1.0,
                "compliant_count": 0,
                "gap_count": 0,
                "warning_count": 0
            }
        )

        summary = compliance_agent.get_compliance_summary(response)

        assert "No applicable guidelines" in summary


class TestErrorHandling:
    """Tests for error handling."""

    def test_exception_during_analysis(self, compliance_agent, mock_ai_caller, sample_soap_note):
        """Test handling of exceptions during analysis."""
        mock_ai_caller.call = Mock(side_effect=Exception("API error"))

        task = AgentTask(
            task_description="Check compliance",
            input_data={"soap_note": sample_soap_note}
        )

        response = compliance_agent.execute(task)

        assert response.success is False
        assert response.error is not None


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_exists(self):
        """Test that default config is properly defined."""
        assert ComplianceAgent.DEFAULT_CONFIG is not None
        assert ComplianceAgent.DEFAULT_CONFIG.name == "ComplianceAgent"

    def test_default_config_low_temperature(self):
        """Test temperature is low for consistent analysis."""
        # Compliance analysis should be deterministic
        assert ComplianceAgent.DEFAULT_CONFIG.temperature <= 0.2

    def test_default_config_sufficient_tokens(self):
        """Test max tokens allows for detailed analysis."""
        assert ComplianceAgent.DEFAULT_CONFIG.max_tokens >= 1000

    def test_system_prompt_contains_guidelines(self):
        """Test system prompt includes guidance on compliance analysis."""
        prompt = ComplianceAgent.DEFAULT_CONFIG.system_prompt.lower()
        assert "guideline" in prompt
        assert "compliant" in prompt or "compliance" in prompt
