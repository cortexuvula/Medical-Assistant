"""
Unit tests for ReferralAgent.

Tests cover:
- Recipient types (SPECIALIST, GP_BACKREFERRAL, HOSPITAL, DIAGNOSTIC)
- Urgency levels (ROUTINE, SOON, URGENT, EMERGENCY)
- Referral type routing
- Specialty inference from conditions
- Recipient-aware prompt building
"""

import pytest
from unittest.mock import Mock, patch

from ai.agents.referral import (
    ReferralAgent,
    ReferralRecipientType,
    UrgencyLevel
)
from ai.agents.models import AgentConfig, AgentTask, AgentResponse
from ai.agents.ai_caller import MockAICaller


@pytest.fixture
def referral_agent(mock_ai_caller):
    """Create a ReferralAgent with mock AI caller."""
    return ReferralAgent(ai_caller=mock_ai_caller)


@pytest.fixture
def sample_soap_note():
    """Sample SOAP note for referral testing."""
    return """S: 65-year-old male presents with urinary frequency, nocturia x3, weak stream.
O: BP 130/85, Prostate mildly enlarged on DRE.
A: Benign Prostatic Hyperplasia (BPH) - N40.0
P: Refer to urology for evaluation. Continue monitoring."""


class TestReferralTypeRouting:
    """Tests for referral type routing."""

    def test_standard_referral(self, referral_agent, mock_ai_caller, sample_soap_note):
        """Test standard referral generation."""
        mock_ai_caller.default_response = "Dear Colleague, I am referring this patient..."

        task = AgentTask(
            task_description="Generate referral letter",
            input_data={
                "soap_note": sample_soap_note,
                "conditions": "BPH"
            }
        )

        response = referral_agent.execute(task)

        assert response.success is True
        assert "referral_type" in response.metadata

    def test_specialist_referral(self, referral_agent, mock_ai_caller):
        """Test specialist-specific referral."""
        mock_ai_caller.default_response = "Referral to Cardiology..."

        task = AgentTask(
            task_description="Generate specialist referral",
            input_data={
                "soap_note": "Patient with chest pain",
                "specialty": "cardiology",
                "specific_concerns": "Evaluate for coronary artery disease"
            }
        )

        response = referral_agent.execute(task)

        assert response.success is True
        assert response.metadata.get("specialty") == "cardiology"

    def test_urgent_referral(self, referral_agent, mock_ai_caller):
        """Test urgent referral generation using legacy routing."""
        mock_ai_caller.default_response = "URGENT: Please see this patient immediately..."

        # Use clinical_info (not soap_note) to trigger legacy routing
        task = AgentTask(
            task_description="Generate urgent referral",
            input_data={
                "clinical_info": "Patient with severe chest pain and diaphoresis",
                "red_flags": ["chest pain", "diaphoresis", "shortness of breath"]
            }
        )

        response = referral_agent.execute(task)

        assert response.success is True
        assert response.metadata.get("referral_type") == "urgent"
        assert response.metadata.get("urgency_level") == "urgent"
        # Should have tool calls for urgent notification
        assert len(response.tool_calls) > 0

    def test_diagnostic_referral(self, referral_agent, mock_ai_caller):
        """Test diagnostic referral generation using legacy routing."""
        mock_ai_caller.default_response = "Request for MRI Brain..."

        # Use clinical_info (not soap_note) to trigger legacy routing
        task = AgentTask(
            task_description="Generate diagnostic referral",
            input_data={
                "clinical_info": "Patient with chronic headaches",
                "requested_tests": ["MRI Brain", "MRA"],
                "clinical_question": "Rule out intracranial pathology"
            }
        )

        response = referral_agent.execute(task)

        assert response.success is True
        assert response.metadata.get("referral_type") == "diagnostic"

    def test_follow_up_referral(self, referral_agent, mock_ai_caller):
        """Test follow-up referral generation."""
        mock_ai_caller.default_response = "Follow-up referral for continued care..."

        task = AgentTask(
            task_description="Generate follow-up referral",
            input_data={
                "initial_referral": "Previous cardiology referral",
                "progress_notes": "Patient responded well to treatment",
                "current_status": "Stable but needs continued monitoring"
            }
        )

        response = referral_agent.execute(task)

        assert response.success is True
        assert response.metadata.get("referral_type") == "follow_up"


class TestRecipientTypes:
    """Tests for different recipient types."""

    def test_gp_backreferral(self, referral_agent, mock_ai_caller):
        """Test GP back-referral generation."""
        mock_ai_caller.default_response = "Thank you for referring this patient..."

        task = AgentTask(
            task_description="Generate back-referral",
            input_data={
                "soap_note": "Patient treatment completed",
                "recipient_type": "gp_backreferral"
            }
        )

        response = referral_agent.execute(task)

        assert response.success is True
        assert response.metadata.get("recipient_type") == "gp_backreferral"

    def test_hospital_admission_request(self, referral_agent, mock_ai_caller):
        """Test hospital admission request."""
        mock_ai_caller.default_response = "Request for hospital admission..."

        task = AgentTask(
            task_description="Generate hospital admission",
            input_data={
                "soap_note": "Patient requires inpatient care",
                "recipient_type": "hospital",
                "urgency": "urgent"
            }
        )

        response = referral_agent.execute(task)

        assert response.success is True
        assert response.metadata.get("recipient_type") == "hospital"

    def test_diagnostic_services_request(self, referral_agent, mock_ai_caller):
        """Test diagnostic services request."""
        mock_ai_caller.default_response = "Request for diagnostic imaging..."

        task = AgentTask(
            task_description="Generate diagnostic request",
            input_data={
                "soap_note": "Patient with abdominal pain",
                "recipient_type": "diagnostic",
                "conditions": "Suspected appendicitis"
            }
        )

        response = referral_agent.execute(task)

        assert response.success is True
        assert response.metadata.get("recipient_type") == "diagnostic"


class TestUrgencyLevels:
    """Tests for urgency level handling."""

    def test_routine_urgency(self, referral_agent, mock_ai_caller):
        """Test routine urgency referral."""
        mock_ai_caller.default_response = "Routine referral for evaluation..."

        task = AgentTask(
            task_description="Generate routine referral",
            input_data={
                "soap_note": "Patient with mild symptoms",
                "urgency": "routine"
            }
        )

        response = referral_agent.execute(task)

        assert response.metadata.get("urgency_level") in ["routine", "standard"]

    def test_urgent_urgency(self, referral_agent, mock_ai_caller):
        """Test urgent referral level."""
        mock_ai_caller.default_response = "URGENT: This patient requires..."

        task = AgentTask(
            task_description="Generate urgent referral",
            input_data={
                "soap_note": "Patient with concerning symptoms",
                "urgency": "urgent"
            }
        )

        response = referral_agent.execute(task)

        assert response.metadata.get("urgency_level") == "urgent"

    def test_emergency_urgency(self, referral_agent, mock_ai_caller):
        """Test emergency urgency extraction."""
        mock_ai_caller.default_response = "EMERGENCY referral for immediate assessment..."

        task = AgentTask(
            task_description="Generate emergency referral",
            input_data={
                "soap_note": "Patient with acute symptoms",
                "urgency": "emergency"
            }
        )

        response = referral_agent.execute(task)

        # Emergency should be preserved
        assert response.metadata.get("urgency_level") in ["urgent", "emergency"]


class TestSpecialtyInference:
    """Tests for specialty inference from conditions."""

    def test_infer_urology_from_bph(self, referral_agent):
        """Test urology inference from BPH."""
        specialty = referral_agent._infer_specialty_from_conditions("BPH, prostate enlargement")
        assert specialty.lower() == "urology"

    def test_infer_cardiology_from_heart(self, referral_agent):
        """Test cardiology inference from cardiac conditions."""
        specialty = referral_agent._infer_specialty_from_conditions("chest pain, hypertension")
        assert specialty.lower() == "cardiology"

    def test_infer_neurology_from_headache(self, referral_agent):
        """Test neurology inference from neurological conditions."""
        specialty = referral_agent._infer_specialty_from_conditions("chronic migraine, vertigo")
        assert specialty.lower() == "neurology"

    def test_infer_gastroenterology(self, referral_agent):
        """Test gastroenterology inference."""
        specialty = referral_agent._infer_specialty_from_conditions("GERD, dysphagia")
        assert specialty.lower() == "gastroenterology"

    def test_infer_endocrinology(self, referral_agent):
        """Test endocrinology inference."""
        specialty = referral_agent._infer_specialty_from_conditions("Type 2 diabetes, thyroid nodule")
        assert specialty.lower() == "endocrinology"

    def test_infer_returns_none_for_general(self, referral_agent):
        """Test that general conditions return None."""
        specialty = referral_agent._infer_specialty_from_conditions("general wellness check")
        assert specialty is None

    def test_infer_from_empty_conditions(self, referral_agent):
        """Test inference from empty conditions."""
        specialty = referral_agent._infer_specialty_from_conditions("")
        assert specialty is None


class TestUrgencyExtraction:
    """Tests for urgency extraction from referral text."""

    def test_extract_urgent(self, referral_agent):
        """Test extraction of urgent level."""
        text = "This is an URGENT referral requiring immediate attention."
        urgency = referral_agent._extract_urgency(text)
        assert urgency == "urgent"

    def test_extract_routine(self, referral_agent):
        """Test extraction of routine level."""
        text = "Routine referral for elective evaluation."
        urgency = referral_agent._extract_urgency(text)
        assert urgency == "routine"

    def test_extract_high_priority(self, referral_agent):
        """Test extraction of high priority level."""
        text = "Please expedite this referral as soon as possible."
        urgency = referral_agent._extract_urgency(text)
        assert urgency == "high"

    def test_extract_standard_default(self, referral_agent):
        """Test default standard urgency."""
        text = "Please see this patient for evaluation."
        urgency = referral_agent._extract_urgency(text)
        assert urgency == "standard"


class TestSpecialtyExtraction:
    """Tests for specialty extraction from referral text."""

    def test_extract_cardiology(self, referral_agent):
        """Test extraction of cardiology specialty."""
        text = "Referral to cardiology for cardiac evaluation."
        specialty = referral_agent._extract_specialty(text)
        assert specialty == "Cardiology"

    def test_extract_neurology(self, referral_agent):
        """Test extraction of neurology specialty."""
        text = "Please refer to neurology for further assessment."
        specialty = referral_agent._extract_specialty(text)
        assert specialty == "Neurology"

    def test_extract_returns_none(self, referral_agent):
        """Test extraction returns None when no specialty found."""
        text = "Please see this patient for further evaluation."
        specialty = referral_agent._extract_specialty(text)
        assert specialty is None


class TestRecipientGuidance:
    """Tests for recipient-specific guidance."""

    def test_specialist_guidance(self, referral_agent):
        """Test guidance for specialist referrals."""
        guidance = referral_agent._get_referral_recipient_guidance("specialist")

        assert "focus" in guidance
        assert "exclude" in guidance
        assert "tone" in guidance
        assert len(guidance["focus"]) > 0

    def test_gp_backreferral_guidance(self, referral_agent):
        """Test guidance for GP back-referrals."""
        guidance = referral_agent._get_referral_recipient_guidance("gp_backreferral")

        assert "Summary of treatment" in str(guidance["focus"])
        assert "handover" in guidance["tone"].lower()

    def test_hospital_guidance(self, referral_agent):
        """Test guidance for hospital referrals."""
        guidance = referral_agent._get_referral_recipient_guidance("hospital")

        assert "Admission" in str(guidance["focus"])
        assert "actionable" in guidance["tone"].lower()

    def test_diagnostic_guidance(self, referral_agent):
        """Test guidance for diagnostic referrals."""
        guidance = referral_agent._get_referral_recipient_guidance("diagnostic")

        assert "Clinical question" in str(guidance["focus"])


class TestPromptBuilding:
    """Tests for prompt building methods."""

    def test_build_standard_prompt(self, referral_agent):
        """Test standard referral prompt building."""
        prompt = referral_agent._build_standard_referral_prompt(
            source_text="Patient with condition",
            conditions="BPH",
            context="Additional context",
            specialty="Urology"
        )

        assert "BPH" in prompt
        assert "Urology" in prompt
        assert "ONLY include" in prompt  # Condition filtering instructions

    def test_build_specialist_prompt(self, referral_agent):
        """Test specialist referral prompt building."""
        prompt = referral_agent._build_specialist_referral_prompt(
            clinical_info="Patient information",
            specialty="Cardiology",
            specific_concerns="Rule out CAD",
            context="Additional context"
        )

        assert "Cardiology" in prompt
        assert "Rule out CAD" in prompt

    def test_build_urgent_prompt(self, referral_agent):
        """Test urgent referral prompt building."""
        prompt = referral_agent._build_urgent_referral_prompt(
            clinical_info="Patient with severe symptoms",
            red_flags=["chest pain", "shortness of breath"],
            context=None
        )

        assert "URGENT" in prompt
        assert "chest pain" in prompt

    def test_build_recipient_aware_prompt(self, referral_agent):
        """Test recipient-aware prompt building."""
        prompt = referral_agent._build_recipient_aware_prompt(
            source_text="Patient data",
            conditions="Hypertension",
            recipient_type="gp_backreferral",
            urgency="routine",
            specialty=None,
            recipient_details={"name": "Dr. Smith", "facility": "City Clinic"},
            context=None
        )

        assert "Dr. Smith" in prompt
        assert "City Clinic" in prompt
        assert "back-referral" in prompt.lower()


class TestConvenienceMethods:
    """Tests for convenience methods."""

    def test_generate_referral_from_soap(self, referral_agent, mock_ai_caller, sample_soap_note):
        """Test convenience method for SOAP-based referral."""
        mock_ai_caller.default_response = "Generated referral letter..."

        result = referral_agent.generate_referral_from_soap(
            soap_note=sample_soap_note,
            conditions="BPH"
        )

        assert result is not None
        assert "Generated referral" in result

    def test_generate_referral_from_soap_failure(self, referral_agent, mock_ai_caller):
        """Test convenience method when generation fails."""
        mock_ai_caller.call = Mock(side_effect=Exception("API error"))

        result = referral_agent.generate_referral_from_soap(
            soap_note="Test note",
            conditions="Test condition"
        )

        assert result is None


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_clinical_info(self, referral_agent, mock_ai_caller):
        """Test handling of missing clinical information."""
        task = AgentTask(
            task_description="Generate referral",
            input_data={}  # No soap_note or transcript
        )

        response = referral_agent.execute(task)

        assert response.success is False
        assert "No clinical information" in response.error

    def test_execution_exception(self, referral_agent, mock_ai_caller):
        """Test handling of exceptions during execution."""
        mock_ai_caller.call = Mock(side_effect=Exception("API error"))

        task = AgentTask(
            task_description="Generate referral",
            input_data={"soap_note": "Test note"}
        )

        response = referral_agent.execute(task)

        assert response.success is False


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_exists(self):
        """Test that default config is properly defined."""
        assert ReferralAgent.DEFAULT_CONFIG is not None
        assert ReferralAgent.DEFAULT_CONFIG.name == "ReferralAgent"

    def test_default_config_temperature(self):
        """Test temperature is low for professional consistency."""
        assert ReferralAgent.DEFAULT_CONFIG.temperature <= 0.5

    def test_default_config_max_tokens(self):
        """Test max tokens is sufficient for referral letters."""
        assert ReferralAgent.DEFAULT_CONFIG.max_tokens >= 800
