"""
Unit tests for WorkflowAgent.

Tests cover:
- Workflow type routing (patient_intake, diagnostic_workup, treatment_protocol, follow_up_care)
- Step sequencing and parsing
- Checkpoint extraction
- Duration estimation
- Progress tracking
"""

import pytest
from unittest.mock import Mock, patch
import re

from ai.agents.workflow import WorkflowAgent
from ai.agents.models import AgentConfig, AgentTask, AgentResponse
from ai.agents.ai_caller import MockAICaller


@pytest.fixture
def workflow_agent(mock_ai_caller):
    """Create a WorkflowAgent with mock AI caller."""
    return WorkflowAgent(ai_caller=mock_ai_caller)


@pytest.fixture
def mock_workflow_response():
    """Sample workflow response from AI."""
    return """WORKFLOW: Patient Intake
TYPE: Intake
DURATION: 30-45 minutes

STEPS:
1. Registration - 5 min - Complete patient demographics
   ✓ Checkpoint: Verify identity and insurance
   → Next: Proceed to medical history

2. Medical History - 10 min - Review past medical history
   ✓ Checkpoint: Confirm allergies documented
   → Next: Proceed to vital signs

3. Vital Signs - 5 min - Measure and record vitals
   ✓ Checkpoint: Alert if abnormal values
   → Next: Complete intake

4. Chief Complaint - 5 min - Document reason for visit
   ✓ Checkpoint: Ensure clarity of complaint
"""


class TestWorkflowTypeRouting:
    """Tests for workflow type routing."""

    def test_patient_intake_workflow(self, workflow_agent, mock_ai_caller):
        """Test patient intake workflow generation."""
        mock_ai_caller.default_response = "Patient intake workflow with steps 1, 2, 3"

        task = AgentTask(
            task_description="Generate patient intake workflow",
            input_data={
                "workflow_type": "patient_intake",
                "clinical_context": "New patient visit",
                "patient_info": {"type": "Adult", "visit_type": "New Patient"}
            }
        )

        response = workflow_agent.execute(task)

        assert response.success is True
        assert response.metadata["workflow_type"] == "patient_intake"
        # Check AI was called
        assert len(mock_ai_caller.call_history) > 0
        # Check prompt contained relevant keywords
        call = mock_ai_caller.call_history[0]
        assert "intake" in call["prompt"].lower()

    def test_diagnostic_workup_workflow(self, workflow_agent, mock_ai_caller):
        """Test diagnostic workup workflow generation."""
        mock_ai_caller.default_response = "Diagnostic workup: Lab tests, imaging..."

        task = AgentTask(
            task_description="Generate diagnostic workflow",
            input_data={
                "workflow_type": "diagnostic_workup",
                "clinical_context": "Suspected pneumonia",
                "patient_info": {
                    "symptoms": "cough, fever",
                    "suspected_conditions": ["Pneumonia", "Bronchitis"]
                }
            }
        )

        response = workflow_agent.execute(task)

        assert response.success is True
        assert response.metadata["workflow_type"] == "diagnostic_workup"
        assert "recommended_tests" in response.metadata

    def test_treatment_protocol_workflow(self, workflow_agent, mock_ai_caller):
        """Test treatment protocol workflow generation."""
        mock_ai_caller.default_response = "Treatment protocol: Monitor: daily BP check"

        task = AgentTask(
            task_description="Generate treatment protocol",
            input_data={
                "workflow_type": "treatment_protocol",
                "clinical_context": "Hypertension management",
                "patient_info": {
                    "diagnosis": "Essential hypertension",
                    "treatment_goals": ["BP < 140/90"]
                }
            }
        )

        response = workflow_agent.execute(task)

        assert response.success is True
        assert response.metadata["workflow_type"] == "treatment_protocol"
        assert "monitoring_parameters" in response.metadata

    def test_follow_up_care_workflow(self, workflow_agent, mock_ai_caller):
        """Test follow-up care workflow generation."""
        mock_ai_caller.default_response = "Follow-up: 1 month - Progress evaluation"

        task = AgentTask(
            task_description="Generate follow-up workflow",
            input_data={
                "workflow_type": "follow_up_care",
                "clinical_context": "Post-treatment monitoring",
                "patient_info": {
                    "treatment_completed": "Antibiotic course",
                    "follow_up_duration": "3 months"
                }
            }
        )

        response = workflow_agent.execute(task)

        assert response.success is True
        assert response.metadata["workflow_type"] == "follow_up_care"
        assert "follow_up_schedule" in response.metadata

    def test_general_workflow(self, workflow_agent, mock_ai_caller):
        """Test general workflow when no specific type provided."""
        mock_ai_caller.default_response = "General clinical workflow steps..."

        task = AgentTask(
            task_description="Create a clinical workflow",
            input_data={
                "clinical_context": "General consultation"
            }
        )

        response = workflow_agent.execute(task)

        assert response.success is True
        assert response.metadata["workflow_type"] == "general"
        assert response.metadata.get("customizable") is True


class TestWorkflowParsing:
    """Tests for workflow parsing functionality."""

    def test_parse_workflow_steps(self, workflow_agent, mock_workflow_response, mock_ai_caller):
        """Test parsing of workflow steps."""
        parsed = workflow_agent._parse_workflow(mock_workflow_response, "patient_intake")

        assert parsed["type"] == "patient_intake"
        assert len(parsed["steps"]) >= 4
        assert parsed["steps"][0]["number"] == 1
        assert "Registration" in parsed["steps"][0]["name"]

    def test_parse_workflow_checkpoints(self, workflow_agent, mock_workflow_response, mock_ai_caller):
        """Test extraction of checkpoints."""
        parsed = workflow_agent._parse_workflow(mock_workflow_response, "patient_intake")

        assert len(parsed["checkpoints"]) >= 2
        assert any("identity" in cp.lower() for cp in parsed["checkpoints"])

    def test_parse_workflow_duration(self, workflow_agent, mock_workflow_response, mock_ai_caller):
        """Test extraction of workflow duration."""
        parsed = workflow_agent._parse_workflow(mock_workflow_response, "patient_intake")

        assert "30-45 minutes" in parsed["duration"]

    def test_parse_workflow_empty_text(self, workflow_agent, mock_ai_caller):
        """Test parsing empty workflow text."""
        parsed = workflow_agent._parse_workflow("", "general")

        assert parsed["type"] == "general"
        assert parsed["steps"] == []
        assert parsed["checkpoints"] == []


class TestDiagnosticTestExtraction:
    """Tests for diagnostic test extraction."""

    def test_extract_lab_tests(self, workflow_agent, mock_ai_caller):
        """Test extraction of laboratory tests."""
        workflow_text = """
        Laboratory tests: CBC, BMP, Lipid panel
        Imaging: Chest X-ray
        Test: Urinalysis
        """

        tests = workflow_agent._extract_diagnostic_tests(workflow_text)

        assert len(tests) >= 3
        test_names = [t["name"].lower() for t in tests]
        assert any("cbc" in name for name in test_names)

    def test_extract_test_priorities(self, workflow_agent, mock_ai_caller):
        """Test extraction of test priorities."""
        workflow_text = """
        Laboratory tests: STAT Troponin, CBC urgent, Routine lipid panel
        """

        tests = workflow_agent._extract_diagnostic_tests(workflow_text)

        # Check priority assignment
        priorities = {t["name"]: t["priority"] for t in tests}
        assert any(p == "STAT" for p in priorities.values())

    def test_extract_empty_tests(self, workflow_agent, mock_ai_caller):
        """Test extraction when no tests present."""
        workflow_text = "General consultation without specific tests."

        tests = workflow_agent._extract_diagnostic_tests(workflow_text)

        assert tests == []


class TestMonitoringParameterExtraction:
    """Tests for monitoring parameter extraction."""

    def test_extract_monitoring_parameters(self, workflow_agent, mock_ai_caller):
        """Test extraction of monitoring parameters."""
        workflow_text = """
        Monitoring: Blood pressure daily, Heart rate
        Check: Glucose levels weekly
        Assess: Kidney function monthly
        """

        params = workflow_agent._extract_monitoring_parameters(workflow_text)

        assert len(params) >= 3
        param_names = [p["parameter"].lower() for p in params]
        assert any("blood pressure" in name for name in param_names)

    def test_extract_monitoring_frequencies(self, workflow_agent, mock_ai_caller):
        """Test extraction of monitoring frequencies."""
        workflow_text = """
        Monitor: BP daily
        Check: Labs weekly
        Assess: Symptoms monthly
        """

        params = workflow_agent._extract_monitoring_parameters(workflow_text)

        frequencies = [p["frequency"] for p in params]
        assert "Daily" in frequencies
        assert "Weekly" in frequencies
        assert "Monthly" in frequencies


class TestFollowUpScheduleGeneration:
    """Tests for follow-up schedule generation."""

    def test_generate_schedule_from_workflow(self, workflow_agent, mock_ai_caller):
        """Test schedule generation from workflow steps."""
        structured_workflow = {
            "steps": [
                {"name": "1 week follow-up appointment", "description": "Check progress"},
                {"name": "Monthly follow-up", "description": "Review medication"},
            ],
            "duration": "3 months"
        }

        schedule = workflow_agent._generate_follow_up_schedule(structured_workflow, "3 months")

        assert len(schedule) >= 1

    def test_generate_default_schedule(self, workflow_agent, mock_ai_caller):
        """Test default schedule generation when steps don't specify."""
        structured_workflow = {
            "steps": [
                {"name": "General check", "description": "Routine follow-up"},
            ],
            "duration": "6 months"
        }

        schedule = workflow_agent._generate_follow_up_schedule(structured_workflow, "6 months")

        # Should create monthly follow-ups for 6 months
        assert len(schedule) >= 3

    def test_schedule_contains_required_fields(self, workflow_agent, mock_ai_caller):
        """Test that schedule entries have required fields."""
        structured_workflow = {"steps": [], "duration": "3 months"}

        schedule = workflow_agent._generate_follow_up_schedule(structured_workflow, "3 months")

        if schedule:
            entry = schedule[0]
            assert "interval" in entry
            assert "days_from_start" in entry
            assert "appointment_type" in entry


class TestErrorHandling:
    """Tests for error handling in workflow agent."""

    def test_execute_with_exception(self, workflow_agent, mock_ai_caller):
        """Test handling of exceptions during execution."""
        mock_ai_caller.default_response = None
        mock_ai_caller.call = Mock(side_effect=Exception("AI call failed"))

        task = AgentTask(
            task_description="Generate workflow",
            input_data={"workflow_type": "patient_intake"}
        )

        response = workflow_agent.execute(task)

        assert response.success is False
        assert response.error is not None

    def test_execute_with_empty_context(self, workflow_agent, mock_ai_caller):
        """Test execution with minimal/empty context."""
        mock_ai_caller.default_response = "Simple workflow: Step 1, Step 2"

        task = AgentTask(
            task_description="Generate workflow",
            input_data={
                "workflow_type": "patient_intake",
                "clinical_context": "",
                "patient_info": {}
            }
        )

        response = workflow_agent.execute(task)

        assert response.success is True


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_exists(self):
        """Test that default config is properly defined."""
        assert WorkflowAgent.DEFAULT_CONFIG is not None
        assert WorkflowAgent.DEFAULT_CONFIG.name == "WorkflowAgent"

    def test_default_config_temperature(self):
        """Test that temperature is set for consistency."""
        # Lower temperature for more consistent workflow outputs
        assert WorkflowAgent.DEFAULT_CONFIG.temperature <= 0.5

    def test_create_with_default_config(self, mock_ai_caller):
        """Test agent creation with default config."""
        agent = WorkflowAgent(ai_caller=mock_ai_caller)

        assert agent.config.name == "WorkflowAgent"
        assert agent.config.system_prompt is not None
        assert "workflow" in agent.config.system_prompt.lower()

    def test_create_with_custom_config(self, mock_ai_caller):
        """Test agent creation with custom config."""
        custom_config = AgentConfig(
            name="CustomWorkflowAgent",
            description="Custom workflow",
            system_prompt="Custom prompt",
            model="gpt-3.5-turbo",
            temperature=0.1
        )

        agent = WorkflowAgent(config=custom_config, ai_caller=mock_ai_caller)

        assert agent.config.name == "CustomWorkflowAgent"
        assert agent.config.model == "gpt-3.5-turbo"
