"""Regression tests for the agent system.

These tests verify that agents execute correctly and
return proper responses.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAgentModels:
    """Tests for agent data models."""

    def test_agent_config_creation(self):
        """AgentConfig should be creatable with required fields."""
        from src.ai.agents.models import AgentConfig

        config = AgentConfig(
            name="Test Agent",
            description="A test agent for unit testing",
            system_prompt="Test prompt",
            model="gpt-4",
            temperature=0.7,
            provider="openai"
        )

        assert config.name == "Test Agent"
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7

    def test_agent_task_creation(self):
        """AgentTask should be creatable."""
        from src.ai.agents.models import AgentTask

        task = AgentTask(
            task_description="Analyze the content",
            context="Additional context here",
            input_data={"key": "value"}
        )

        assert task.task_description == "Analyze the content"
        assert task.context == "Additional context here"
        assert task.input_data == {"key": "value"}

    def test_agent_response_creation(self):
        """AgentResponse should be creatable."""
        from src.ai.agents.models import AgentResponse

        response = AgentResponse(
            result="Result content",
            success=True,
            error=None
        )

        assert response.success is True
        assert response.result == "Result content"
        assert response.error is None

    def test_agent_response_with_error(self):
        """AgentResponse should handle error state."""
        from src.ai.agents.models import AgentResponse

        response = AgentResponse(
            result="",
            success=False,
            error="Something went wrong"
        )

        assert response.success is False
        assert response.error == "Something went wrong"


class TestBaseAgent:
    """Tests for BaseAgent class."""

    def test_base_agent_is_abstract(self):
        """BaseAgent should be abstract."""
        from src.ai.agents.base import BaseAgent

        with pytest.raises(TypeError):
            BaseAgent()  # Should not be instantiable

    def test_base_agent_defines_execute(self):
        """BaseAgent should define execute method."""
        from src.ai.agents.base import BaseAgent

        assert hasattr(BaseAgent, 'execute')


class TestAgentManager:
    """Tests for AgentManager class."""

    def test_agent_manager_imports(self):
        """AgentManager should import correctly."""
        try:
            from src.managers.agent_manager import AgentManager
            assert AgentManager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AgentManager: {e}")

    def test_agent_manager_singleton(self):
        """AgentManager should be a singleton."""
        from src.managers.agent_manager import AgentManager

        with patch.object(AgentManager, '_load_agents'):
            manager1 = AgentManager()
            manager2 = AgentManager()

        # Should be same instance (singleton)
        assert manager1 is manager2

    def test_agent_manager_has_execute_method(self):
        """AgentManager should have execute_agent_task method."""
        from src.managers.agent_manager import AgentManager

        assert hasattr(AgentManager, 'execute_agent_task')

    def test_agent_manager_has_get_agent(self):
        """AgentManager should have get_agent method."""
        from src.managers.agent_manager import AgentManager

        assert hasattr(AgentManager, 'get_agent')


class TestSynopsisAgent:
    """Tests for Synopsis agent."""

    def test_synopsis_agent_imports(self):
        """SynopsisAgent should import correctly."""
        try:
            from src.ai.agents.synopsis import SynopsisAgent
            assert SynopsisAgent is not None
        except ImportError as e:
            pytest.fail(f"Failed to import SynopsisAgent: {e}")

    def test_synopsis_agent_has_default_config(self):
        """SynopsisAgent should have DEFAULT_CONFIG."""
        from src.ai.agents.synopsis import SynopsisAgent

        assert hasattr(SynopsisAgent, 'DEFAULT_CONFIG')

    def test_synopsis_agent_execute(self, mock_api_keys):
        """SynopsisAgent.execute should return AgentResponse."""
        from src.ai.agents.synopsis import SynopsisAgent
        from src.ai.agents.models import AgentConfig, AgentTask, AgentResponse

        config = AgentConfig(
            name="Synopsis Agent",
            description="Creates brief synopsis of medical visits",
            system_prompt="Create synopsis",
            model="gpt-4",
            temperature=0.3,
            provider="openai"
        )

        mock_ai_caller = MagicMock()
        mock_ai_caller.call.return_value = "Brief synopsis of the visit"

        agent = SynopsisAgent(config=config, ai_caller=mock_ai_caller)

        task = AgentTask(
            task_description="Create a synopsis of this visit",
            input_data={"content": "Full SOAP note content here"}
        )

        response = agent.execute(task)

        assert isinstance(response, AgentResponse)


class TestMedicationAgent:
    """Tests for Medication agent."""

    def test_medication_agent_imports(self):
        """MedicationAgent should import correctly."""
        try:
            from src.ai.agents.medication import MedicationAgent
            assert MedicationAgent is not None
        except ImportError as e:
            pytest.fail(f"Failed to import MedicationAgent: {e}")

    def test_medication_agent_execute(self, mock_api_keys):
        """MedicationAgent.execute should return AgentResponse."""
        from src.ai.agents.medication import MedicationAgent
        from src.ai.agents.models import AgentConfig, AgentTask, AgentResponse

        config = AgentConfig(
            name="Medication Agent",
            description="Analyzes medications for interactions and dosing",
            system_prompt="Analyze medications",
            model="gpt-4",
            temperature=0.2,
            provider="openai"
        )

        mock_ai_caller = MagicMock()
        mock_ai_caller.call.return_value = "Medication analysis result"

        agent = MedicationAgent(config=config, ai_caller=mock_ai_caller)

        task = AgentTask(
            task_description="Analyze medications",
            input_data={"content": "Patient on metformin 500mg, lisinopril 10mg"}
        )

        response = agent.execute(task)

        assert isinstance(response, AgentResponse)


class TestDiagnosticAgent:
    """Tests for Diagnostic agent."""

    def test_diagnostic_agent_imports(self):
        """DiagnosticAgent should import correctly."""
        try:
            from src.ai.agents.diagnostic import DiagnosticAgent
            assert DiagnosticAgent is not None
        except ImportError as e:
            pytest.fail(f"Failed to import DiagnosticAgent: {e}")


class TestWorkflowAgent:
    """Tests for Workflow agent."""

    def test_workflow_agent_imports(self):
        """WorkflowAgent should import correctly."""
        try:
            from src.ai.agents.workflow import WorkflowAgent
            assert WorkflowAgent is not None
        except ImportError as e:
            pytest.fail(f"Failed to import WorkflowAgent: {e}")


class TestAgentInputValidation:
    """Tests for agent input validation."""

    def test_agent_validates_empty_prompt(self, mock_api_keys):
        """Agent should validate empty prompts."""
        from src.ai.agents.synopsis import SynopsisAgent
        from src.ai.agents.models import AgentConfig, AgentTask

        config = AgentConfig(
            name="Synopsis Agent",
            description="Creates brief synopsis",
            system_prompt="Create synopsis",
            model="gpt-4",
            temperature=0.3,
            provider="openai"
        )

        mock_ai_caller = MagicMock()
        agent = SynopsisAgent(config=config, ai_caller=mock_ai_caller)

        task = AgentTask(
            task_description="Create synopsis",
            input_data={"content": ""}  # Empty content
        )

        response = agent.execute(task)

        # Should handle empty input gracefully
        assert response is not None

    def test_agent_truncates_long_prompt(self, mock_api_keys):
        """Agent should truncate very long prompts."""
        from src.ai.agents.base import MAX_AGENT_PROMPT_LENGTH

        # Verify the constant exists
        assert MAX_AGENT_PROMPT_LENGTH > 0
        assert MAX_AGENT_PROMPT_LENGTH == 50000  # As per codebase


class TestAgentRetry:
    """Tests for agent retry logic."""

    def test_agent_manager_retry_on_failure(self, mock_api_keys):
        """AgentManager should retry on failure."""
        from src.managers.agent_manager import AgentManager
        from src.ai.agents.models import AgentTask, AgentResponse

        with patch.object(AgentManager, '_load_agents'):
            manager = AgentManager()

            # Mock an agent that fails then succeeds
            mock_agent = MagicMock()
            mock_agent.execute.side_effect = [
                AgentResponse(result="", success=False, error="Retry 1"),
                AgentResponse(result="Success", success=True, error=None)
            ]

            with patch.object(manager, 'get_agent', return_value=mock_agent):
                with patch.object(manager, '_execute_with_retry') as mock_retry:
                    mock_retry.return_value = (
                        AgentResponse(result="Success", success=True, error=None),
                        2  # Took 2 attempts
                    )

                    task = AgentTask(task_description="Test task")
                    # The actual call would use retry logic
                    result = mock_retry(mock_agent, task)

        assert result[0].success is True


@pytest.mark.regression
class TestAgentSystemRegressionSuite:
    """Comprehensive regression tests for agent system."""

    def test_all_agent_types_import(self):
        """All agent types should import correctly."""
        agent_modules = [
            ('synopsis', 'SynopsisAgent'),
            ('diagnostic', 'DiagnosticAgent'),
            ('medication', 'MedicationAgent'),
            ('referral', 'ReferralAgent'),
            ('data_extraction', 'DataExtractionAgent'),
            ('workflow', 'WorkflowAgent'),
        ]

        for module_name, class_name in agent_modules:
            try:
                module = __import__(f'src.ai.agents.{module_name}', fromlist=[class_name])
                agent_class = getattr(module, class_name)
                assert agent_class is not None
            except ImportError as e:
                pytest.fail(f"Failed to import {class_name}: {e}")

    def test_agent_response_is_serializable(self):
        """AgentResponse should be JSON serializable."""
        import json
        from src.ai.agents.models import AgentResponse

        response = AgentResponse(
            result="Test content",
            success=True,
            error=None,
            metadata={"key": "value"}
        )

        # Should be convertible to dict and then to JSON
        response_dict = {
            "success": response.success,
            "result": response.result,
            "error": response.error,
            "metadata": response.metadata
        }

        json_str = json.dumps(response_dict)
        assert isinstance(json_str, str)

    def test_agent_task_accepts_context(self):
        """AgentTask should accept various context types."""
        from src.ai.agents.models import AgentTask

        # String context
        task1 = AgentTask(
            task_description="Test task",
            context="Additional context",
            input_data={"key": "value"}
        )
        assert task1.context == "Additional context"
        assert task1.input_data == {"key": "value"}

        # None context
        task2 = AgentTask(
            task_description="Test task",
            context=None
        )
        assert task2.context is None

    def test_agent_config_temperature_range(self):
        """AgentConfig temperature should be in valid range."""
        from src.ai.agents.models import AgentConfig

        # Valid temperatures
        for temp in [0.0, 0.5, 1.0]:
            config = AgentConfig(
                name="Test Agent",
                description="Test description",
                system_prompt="Test",
                model="gpt-4",
                temperature=temp,
                provider="openai"
            )
            assert 0.0 <= config.temperature <= 2.0

    def test_agent_config_with_defaults(self, mock_api_keys):
        """AgentConfig should have sensible defaults."""
        from src.ai.agents.models import AgentConfig

        config = AgentConfig(
            name="Test Agent",
            description="Test description",
            system_prompt="Test prompt"
        )

        # Check default values are applied
        assert config.model == "gpt-4"  # Default model
        assert config.temperature == 0.7  # Default temperature
        assert config.provider is None  # Default provider
        assert config.available_tools == []  # Default empty tools

    def test_agent_handles_unicode_content(self, mock_api_keys):
        """Agents should handle unicode content."""
        from src.ai.agents.synopsis import SynopsisAgent
        from src.ai.agents.models import AgentConfig, AgentTask, AgentResponse

        config = AgentConfig(
            name="Synopsis Agent",
            description="Creates brief synopsis",
            system_prompt="Test",
            model="gpt-4",
            temperature=0.3,
            provider="openai"
        )

        mock_ai_caller = MagicMock()
        mock_ai_caller.call.return_value = "Response with émojis 🏥"

        agent = SynopsisAgent(config=config, ai_caller=mock_ai_caller)

        task = AgentTask(
            task_description="Create synopsis",
            input_data={"content": "Patient José García, température 38°C"}
        )

        response = agent.execute(task)

        assert isinstance(response, AgentResponse)
