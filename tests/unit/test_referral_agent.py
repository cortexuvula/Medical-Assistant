"""
Unit tests for ReferralAgent.

Tests cover:
- Recipient types (SPECIALIST, GP_BACKREFERRAL, HOSPITAL, DIAGNOSTIC)
- Urgency levels (ROUTINE, SOON, URGENT, EMERGENCY)
- Referral type routing
- Specialty inference from conditions
- Recipient-aware prompt building
- Pure-logic methods (no AI calls needed)
"""

import pytest
from typing import Optional
from unittest.mock import Mock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from ai.agents.referral import (
    ReferralAgent,
    ReferralRecipientType,
    UrgencyLevel
)
from ai.agents.models import AgentConfig, AgentTask, AgentResponse
from ai.agents.ai_caller import MockAICaller


# ---------------------------------------------------------------------------
# Setup helpers for pure-logic tests (no conftest fixture dependency)
# ---------------------------------------------------------------------------

def _make_agent():
    """Create a ReferralAgent with a MagicMock AI caller."""
    return ReferralAgent(ai_caller=MagicMock())


def _make_task(description="test task", input_data=None):
    """Create a minimal AgentTask."""
    return AgentTask(
        task_description=description,
        input_data=input_data or {}
    )


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


# ===========================================================================
# Pure-logic method tests (using _make_agent / _make_task helpers)
# ===========================================================================


class TestDetermineReferralType:
    """Tests for ReferralAgent._determine_referral_type."""

    def test_urgent_keyword_returns_urgent(self):
        agent = _make_agent()
        task = _make_task("urgent referral needed")
        assert agent._determine_referral_type(task) == "urgent"

    def test_emergency_keyword_returns_urgent(self):
        agent = _make_agent()
        task = _make_task("emergency consult required")
        assert agent._determine_referral_type(task) == "urgent"

    def test_specialist_keyword_returns_specialist(self):
        agent = _make_agent()
        task = _make_task("specialist referral for cardiology")
        assert agent._determine_referral_type(task) == "specialist"

    def test_specialty_keyword_returns_specialist(self):
        agent = _make_agent()
        task = _make_task("specialty consultation needed")
        assert agent._determine_referral_type(task) == "specialist"

    def test_follow_hyphen_up_keyword_returns_follow_up(self):
        agent = _make_agent()
        task = _make_task("follow-up appointment required")
        assert agent._determine_referral_type(task) == "follow_up"

    def test_follow_space_up_keyword_returns_follow_up(self):
        agent = _make_agent()
        task = _make_task("follow up visit next month")
        assert agent._determine_referral_type(task) == "follow_up"

    def test_diagnostic_keyword_returns_diagnostic(self):
        agent = _make_agent()
        task = _make_task("diagnostic workup required")
        assert agent._determine_referral_type(task) == "diagnostic"

    def test_investigation_keyword_returns_diagnostic(self):
        agent = _make_agent()
        task = _make_task("investigation needed for liver enzymes")
        assert agent._determine_referral_type(task) == "diagnostic"

    def test_routine_description_returns_standard(self):
        agent = _make_agent()
        task = _make_task("routine referral for patient")
        assert agent._determine_referral_type(task) == "standard"

    def test_general_consultation_returns_standard(self):
        agent = _make_agent()
        task = _make_task("general consultation")
        assert agent._determine_referral_type(task) == "standard"

    def test_uppercase_urgent_is_case_insensitive(self):
        agent = _make_agent()
        task = _make_task("URGENT referral needed today")
        assert agent._determine_referral_type(task) == "urgent"

    def test_capitalized_emergency_is_case_insensitive(self):
        agent = _make_agent()
        task = _make_task("Emergency visit required")
        assert agent._determine_referral_type(task) == "urgent"

    def test_urgent_takes_priority_over_specialist(self):
        # "urgent" branch is checked before "specialist" in the if-elif chain
        agent = _make_agent()
        task = _make_task("urgent specialist referral")
        assert agent._determine_referral_type(task) == "urgent"

    def test_empty_description_returns_standard(self):
        agent = _make_agent()
        task = _make_task("")
        assert agent._determine_referral_type(task) == "standard"

    def test_mixed_case_specialist(self):
        agent = _make_agent()
        task = _make_task("Specialist consult for endocrinology")
        assert agent._determine_referral_type(task) == "specialist"


class TestExtractUrgencyPure:
    """Tests for ReferralAgent._extract_urgency (pure-logic, no conftest needed)."""

    def test_urgent_keyword(self):
        assert _make_agent()._extract_urgency("This is urgent") == "urgent"

    def test_emergency_keyword(self):
        assert _make_agent()._extract_urgency("Emergency consult needed") == "urgent"

    def test_immediate_keyword(self):
        assert _make_agent()._extract_urgency("Requires immediate attention") == "urgent"

    def test_stat_keyword(self):
        assert _make_agent()._extract_urgency("STAT referral required") == "urgent"

    def test_soon_keyword(self):
        assert _make_agent()._extract_urgency("Please see soon for follow up") == "high"

    def test_expedite_keyword(self):
        assert _make_agent()._extract_urgency("Please expedite this appointment") == "high"

    def test_priority_keyword(self):
        assert _make_agent()._extract_urgency("This is a priority case") == "high"

    def test_routine_keyword(self):
        assert _make_agent()._extract_urgency("Routine follow-up appointment") == "routine"

    def test_elective_keyword(self):
        assert _make_agent()._extract_urgency("Elective procedure when available") == "routine"

    def test_no_urgency_keywords_returns_standard(self):
        assert _make_agent()._extract_urgency("General appointment for patient") == "standard"

    def test_empty_string_returns_standard(self):
        assert _make_agent()._extract_urgency("") == "standard"

    def test_case_insensitive_routine(self):
        assert _make_agent()._extract_urgency("ROUTINE check-up") == "routine"

    def test_case_insensitive_urgent(self):
        assert _make_agent()._extract_urgency("URGENT: patient requires attention") == "urgent"

    def test_case_insensitive_stat(self):
        assert _make_agent()._extract_urgency("Stat labs ordered") == "urgent"

    def test_urgent_takes_priority_over_routine_in_same_text(self):
        # "urgent" check comes first in the if-elif chain
        assert _make_agent()._extract_urgency("urgent routine matter") == "urgent"


class TestExtractSpecialtyPure:
    """Tests for ReferralAgent._extract_specialty (pure-logic, no conftest needed)."""

    def test_cardiology_found(self):
        assert _make_agent()._extract_specialty("Referral to cardiology clinic") == "Cardiology"

    def test_neurology_found(self):
        assert _make_agent()._extract_specialty("Neurology consultation requested") == "Neurology"

    def test_psychiatry_found(self):
        assert _make_agent()._extract_specialty("Psychiatry evaluation needed") == "Psychiatry"

    def test_no_specialty_returns_none(self):
        assert _make_agent()._extract_specialty("No specialty mentioned here") is None

    def test_empty_string_returns_none(self):
        assert _make_agent()._extract_specialty("") is None

    def test_case_insensitive_dermatology(self):
        assert _make_agent()._extract_specialty("DERMATOLOGY clinic visit") == "Dermatology"

    def test_oncology_found(self):
        assert _make_agent()._extract_specialty("Oncology for cancer treatment") == "Oncology"

    def test_urology_found(self):
        assert _make_agent()._extract_specialty("Urology appointment scheduled") == "Urology"

    def test_gynecology_found(self):
        assert _make_agent()._extract_specialty("Gynecology referral letter") == "Gynecology"

    def test_emergency_found(self):
        assert _make_agent()._extract_specialty("Emergency medicine department") == "Emergency"

    def test_gastroenterology_found(self):
        assert _make_agent()._extract_specialty("Referral to gastroenterology for GI workup") == "Gastroenterology"

    def test_endocrinology_found(self):
        assert _make_agent()._extract_specialty("Endocrinology follow-up for diabetes") == "Endocrinology"

    def test_rheumatology_found(self):
        assert _make_agent()._extract_specialty("Rheumatology consultation for arthritis") == "Rheumatology"

    def test_ophthalmology_found(self):
        assert _make_agent()._extract_specialty("Ophthalmology referral for cataract") == "Ophthalmology"

    def test_orthopedics_found(self):
        assert _make_agent()._extract_specialty("Orthopedics for fracture management") == "Orthopedics"

    def test_radiology_found(self):
        assert _make_agent()._extract_specialty("Radiology for imaging studies") == "Radiology"

    def test_result_is_capitalized(self):
        result = _make_agent()._extract_specialty("neurology consult")
        assert result == "Neurology"
        assert result[0].isupper()


class TestInferSpecialtyFromConditions:
    """Tests for ReferralAgent._infer_specialty_from_conditions."""

    def test_none_returns_none(self):
        assert _make_agent()._infer_specialty_from_conditions(None) is None

    def test_empty_string_returns_none(self):
        assert _make_agent()._infer_specialty_from_conditions("") is None

    def test_hypertension_maps_to_cardiology(self):
        assert _make_agent()._infer_specialty_from_conditions("hypertension") == "Cardiology"

    def test_diabetes_maps_to_endocrinology(self):
        assert _make_agent()._infer_specialty_from_conditions("diabetes") == "Endocrinology"

    def test_asthma_maps_to_pulmonology(self):
        assert _make_agent()._infer_specialty_from_conditions("asthma") == "Pulmonology"

    def test_depression_maps_to_psychiatry(self):
        assert _make_agent()._infer_specialty_from_conditions("depression") == "Psychiatry"

    def test_seizure_maps_to_neurology(self):
        assert _make_agent()._infer_specialty_from_conditions("seizure") == "Neurology"

    def test_kidney_stone_maps_to_urology(self):
        assert _make_agent()._infer_specialty_from_conditions("kidney stone") == "Urology"

    def test_anemia_maps_to_hematology(self):
        assert _make_agent()._infer_specialty_from_conditions("anemia") == "Hematology"

    def test_fracture_maps_to_orthopedics(self):
        assert _make_agent()._infer_specialty_from_conditions("fracture") == "Orthopedics"

    def test_rash_maps_to_dermatology(self):
        assert _make_agent()._infer_specialty_from_conditions("rash") == "Dermatology"

    def test_cancer_maps_to_oncology(self):
        assert _make_agent()._infer_specialty_from_conditions("cancer") == "Oncology"

    def test_arthritis_maps_to_rheumatology(self):
        assert _make_agent()._infer_specialty_from_conditions("arthritis") == "Rheumatology"

    def test_cancer_treatment_returns_oncology(self):
        # "cancer" is a keyword under oncology; dict insertion order means oncology
        # wins for text containing "cancer treatment"
        result = _make_agent()._infer_specialty_from_conditions("cancer treatment")
        assert result == "Oncology"

    def test_unknown_condition_returns_none(self):
        assert _make_agent()._infer_specialty_from_conditions("Unknown condition XYZ") is None

    def test_allergy_maps_to_allergy_immunology(self):
        assert _make_agent()._infer_specialty_from_conditions("allergy") == "Allergy/Immunology"

    def test_gerd_maps_to_gastroenterology(self):
        assert _make_agent()._infer_specialty_from_conditions("gerd") == "Gastroenterology"

    def test_pregnancy_maps_to_obstetrics_gynecology(self):
        assert _make_agent()._infer_specialty_from_conditions("pregnancy") == "Obstetrics/Gynecology"

    def test_dvt_maps_to_vascular_surgery(self):
        assert _make_agent()._infer_specialty_from_conditions("dvt") == "Vascular Surgery"

    def test_insomnia_maps_to_sleep_medicine(self):
        assert _make_agent()._infer_specialty_from_conditions("insomnia") == "Sleep Medicine"

    def test_case_insensitive_hypertension(self):
        assert _make_agent()._infer_specialty_from_conditions("Hypertension") == "Cardiology"

    def test_hematuria_maps_to_urology(self):
        assert _make_agent()._infer_specialty_from_conditions("hematuria") == "Urology"

    def test_uti_maps_to_urology(self):
        assert _make_agent()._infer_specialty_from_conditions("uti") == "Urology"

    def test_afib_maps_to_cardiology(self):
        assert _make_agent()._infer_specialty_from_conditions("afib") == "Cardiology"

    def test_migraine_maps_to_neurology(self):
        assert _make_agent()._infer_specialty_from_conditions("migraine") == "Neurology"

    def test_allergy_wins_before_cardiology_in_insertion_order(self):
        # allergy/immunology is the first key in the dict; "allergy" should always
        # map to Allergy/Immunology even when combined with cardiac text
        result = _make_agent()._infer_specialty_from_conditions("allergy and heart issue")
        assert result == "Allergy/Immunology"


class TestGetReferralRecipientGuidancePure:
    """Tests for ReferralAgent._get_referral_recipient_guidance (pure-logic)."""

    REQUIRED_KEYS = {"focus", "exclude", "tone", "format", "opening", "closing"}

    def test_specialist_returns_all_required_keys(self):
        result = _make_agent()._get_referral_recipient_guidance("specialist")
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_specialist_focus_is_non_empty_list(self):
        result = _make_agent()._get_referral_recipient_guidance("specialist")
        assert isinstance(result["focus"], list)
        assert len(result["focus"]) > 0

    def test_specialist_tone_contains_physician_to_physician(self):
        result = _make_agent()._get_referral_recipient_guidance("specialist")
        assert "physician-to-physician" in result["tone"].lower()

    def test_gp_backreferral_returns_all_required_keys(self):
        result = _make_agent()._get_referral_recipient_guidance("gp_backreferral")
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_gp_backreferral_focus_includes_follow_up_requirements(self):
        result = _make_agent()._get_referral_recipient_guidance("gp_backreferral")
        combined = " ".join(result["focus"]).lower()
        assert "follow-up requirements" in combined

    def test_gp_backreferral_tone_contains_handover(self):
        result = _make_agent()._get_referral_recipient_guidance("gp_backreferral")
        assert "handover" in result["tone"].lower()

    def test_hospital_returns_all_required_keys(self):
        result = _make_agent()._get_referral_recipient_guidance("hospital")
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_hospital_tone_contains_actionable(self):
        result = _make_agent()._get_referral_recipient_guidance("hospital")
        assert "actionable" in result["tone"].lower()

    def test_diagnostic_returns_all_required_keys(self):
        result = _make_agent()._get_referral_recipient_guidance("diagnostic")
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_diagnostic_tone_exact_value(self):
        result = _make_agent()._get_referral_recipient_guidance("diagnostic")
        assert result["tone"] == "Request form style, clear and specific"

    def test_unknown_type_falls_back_to_specialist(self):
        unknown = _make_agent()._get_referral_recipient_guidance("nonexistent_type")
        specialist = _make_agent()._get_referral_recipient_guidance("specialist")
        assert unknown == specialist

    def test_all_four_types_have_non_empty_focus(self):
        agent = _make_agent()
        for rtype in ("specialist", "gp_backreferral", "hospital", "diagnostic"):
            result = agent._get_referral_recipient_guidance(rtype)
            assert len(result["focus"]) > 0, f"{rtype} focus is empty"

    def test_all_four_types_have_non_empty_exclude(self):
        agent = _make_agent()
        for rtype in ("specialist", "gp_backreferral", "hospital", "diagnostic"):
            result = agent._get_referral_recipient_guidance(rtype)
            assert len(result["exclude"]) > 0, f"{rtype} exclude is empty"

    def test_specialist_opening_starts_with_thank_you(self):
        result = _make_agent()._get_referral_recipient_guidance("specialist")
        assert result["opening"].startswith("Thank you")

    def test_hospital_opening_contains_requesting_admission(self):
        result = _make_agent()._get_referral_recipient_guidance("hospital")
        assert "requesting admission" in result["opening"].lower()

    def test_gp_backreferral_closing_mentions_re_refer(self):
        result = _make_agent()._get_referral_recipient_guidance("gp_backreferral")
        assert "re-refer" in result["closing"].lower()

    def test_specialist_closing_mentions_expert_opinion(self):
        result = _make_agent()._get_referral_recipient_guidance("specialist")
        assert "expert opinion" in result["closing"].lower()


class TestBuildRecipientAwarePrompt:
    """Tests for ReferralAgent._build_recipient_aware_prompt."""

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _prompt(source_text="Patient clinical notes.", conditions="",
                recipient_type="specialist", urgency="routine",
                specialty=None, recipient_details=None, context=None):
        return _make_agent()._build_recipient_aware_prompt(
            source_text=source_text,
            conditions=conditions,
            recipient_type=recipient_type,
            urgency=urgency,
            specialty=specialty,
            recipient_details=recipient_details,
            context=context,
        )

    # ------------------------------------------------------------------
    # Opening / type-specific text
    # ------------------------------------------------------------------

    def test_specialist_with_specialty_contains_generate_professional_referral_to(self):
        prompt = self._prompt(recipient_type="specialist", specialty="Cardiology")
        assert "Generate a professional referral letter to a" in prompt

    def test_specialist_with_specialty_includes_specialty_name(self):
        prompt = self._prompt(recipient_type="specialist", specialty="Cardiology")
        assert "Cardiology" in prompt

    def test_gp_backreferral_prompt_contains_back_referral_letter(self):
        prompt = self._prompt(recipient_type="gp_backreferral")
        assert "back-referral letter" in prompt

    def test_hospital_prompt_contains_hospital_admission_request(self):
        prompt = self._prompt(recipient_type="hospital")
        assert "hospital admission request" in prompt

    def test_diagnostic_prompt_contains_diagnostic_services_request(self):
        prompt = self._prompt(recipient_type="diagnostic")
        assert "diagnostic services request" in prompt

    def test_unknown_recipient_type_falls_back_to_generic_referral(self):
        prompt = self._prompt(recipient_type="unknown_type")
        assert "Generate a professional referral letter" in prompt

    # ------------------------------------------------------------------
    # Urgency statements
    # ------------------------------------------------------------------

    def test_urgency_routine_includes_routine_elective(self):
        prompt = self._prompt(urgency="routine")
        assert "routine/elective referral" in prompt

    def test_urgency_urgent_includes_uppercase_urgent(self):
        prompt = self._prompt(urgency="urgent")
        assert "URGENT" in prompt

    def test_urgency_emergency_includes_uppercase_emergency(self):
        prompt = self._prompt(urgency="emergency")
        assert "EMERGENCY" in prompt

    def test_urgency_soon_includes_2_4_weeks(self):
        prompt = self._prompt(urgency="soon")
        assert "2-4 weeks" in prompt

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def test_context_provided_appears_in_prompt(self):
        prompt = self._prompt(context="Patient is allergic to penicillin.")
        assert "Additional Context:" in prompt

    def test_context_none_not_in_prompt(self):
        prompt = self._prompt(context=None)
        assert "Additional Context:" not in prompt

    # ------------------------------------------------------------------
    # Condition focus section
    # ------------------------------------------------------------------

    def test_conditions_provided_includes_condition_focus_section(self):
        prompt = self._prompt(conditions="hypertension, diabetes")
        assert "CONDITION FOCUS:" in prompt

    def test_conditions_empty_no_condition_focus_section(self):
        prompt = self._prompt(conditions="")
        assert "CONDITION FOCUS:" not in prompt

    # ------------------------------------------------------------------
    # Recipient details
    # ------------------------------------------------------------------

    def test_recipient_details_with_name_includes_name_in_prompt(self):
        prompt = self._prompt(recipient_details={"name": "Dr. Jane Smith"})
        assert "Dr. Jane Smith" in prompt

    def test_recipient_details_with_name_and_facility_includes_facility(self):
        prompt = self._prompt(recipient_details={"name": "Dr. Jane Smith", "facility": "City Hospital"})
        assert "City Hospital" in prompt

    def test_recipient_details_with_name_includes_do_not_use_placeholder_warning(self):
        prompt = self._prompt(recipient_details={"name": "Dr. Jane Smith"})
        assert "DO NOT use placeholder text" in prompt

    def test_no_recipient_details_includes_appropriate_placeholders_guidance(self):
        prompt = self._prompt(recipient_details=None)
        assert "appropriate placeholders" in prompt

    # ------------------------------------------------------------------
    # Source text and structural sections
    # ------------------------------------------------------------------

    def test_source_text_included_in_prompt(self):
        source = "Patient has chest pain on exertion."
        prompt = self._prompt(source_text=source)
        assert source in prompt

    def test_clinical_information_section_present(self):
        prompt = self._prompt()
        assert "Clinical Information:" in prompt

    def test_include_section_present(self):
        prompt = self._prompt()
        assert "**INCLUDE (focus on):**" in prompt

    def test_exclude_section_present(self):
        prompt = self._prompt()
        assert "**EXCLUDE (do not include):**" in prompt

    # ------------------------------------------------------------------
    # Guidance opening / closing pass-through in letter structure
    # ------------------------------------------------------------------

    def test_specialist_opening_thank_you_in_prompt(self):
        prompt = self._prompt(recipient_type="specialist", specialty="Neurology")
        assert "Thank you" in prompt

    def test_hospital_opening_requesting_admission_in_prompt(self):
        prompt = self._prompt(recipient_type="hospital")
        assert "requesting admission" in prompt.lower()

    def test_gp_backreferral_opening_returning_to_care_in_prompt(self):
        prompt = self._prompt(recipient_type="gp_backreferral")
        assert "returning them to your care" in prompt

    def test_diagnostic_opening_perform_investigation_in_prompt(self):
        prompt = self._prompt(recipient_type="diagnostic")
        assert "Please perform the following investigation" in prompt

    # ------------------------------------------------------------------
    # Tone and format guidance pass-through
    # ------------------------------------------------------------------

    def test_tone_section_in_prompt(self):
        prompt = self._prompt()
        assert "**TONE:**" in prompt

    def test_format_section_in_prompt(self):
        prompt = self._prompt()
        assert "**FORMAT:**" in prompt

    # ------------------------------------------------------------------
    # Unknown urgency falls back to routine statement
    # ------------------------------------------------------------------

    def test_unknown_urgency_falls_back_to_routine_statement(self):
        prompt = self._prompt(urgency="unknown_level")
        assert "routine/elective referral" in prompt

    # ------------------------------------------------------------------
    # Return type and non-empty
    # ------------------------------------------------------------------

    def test_returns_string(self):
        assert isinstance(self._prompt(), str)

    def test_prompt_is_non_empty(self):
        assert len(self._prompt()) > 0

    # ------------------------------------------------------------------
    # Specialist without specialty falls back to generic opening
    # ------------------------------------------------------------------

    def test_specialist_without_specialty_still_generates_professional_letter(self):
        prompt = self._prompt(recipient_type="specialist", specialty=None)
        assert "Generate a professional referral letter" in prompt
