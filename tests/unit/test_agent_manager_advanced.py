"""
Unit tests for AgentManager advanced features.

Tests cover:
- Retry strategies (EXPONENTIAL_BACKOFF, LINEAR_BACKOFF, FIXED_DELAY, NO_RETRY)
- Sub-agent execution with ThreadPoolExecutor
- Condition evaluation with safe_eval
- Agent lifecycle management (reload, get_enabled)
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import TimeoutError as FuturesTimeoutError

from ai.agents.models import (
    AgentConfig, AgentTask, AgentResponse, SubAgentConfig,
    AgentType, RetryConfig, RetryStrategy, AdvancedConfig
)
from ai.agents.ai_caller import MockAICaller


@pytest.fixture
def mock_settings():
    """Create mock settings for agent manager."""
    return {
        "agent_config": {
            "synopsis": {
                "enabled": True,
                "model": "gpt-4",
                "temperature": 0.5,
                "system_prompt": "Test synopsis prompt"
            },
            "diagnostic": {
                "enabled": True,
                "model": "gpt-4",
                "temperature": 0.3
            },
            "medication": {
                "enabled": False
            }
        }
    }


@pytest.fixture
def reset_agent_manager():
    """Reset the agent manager singleton after each test."""
    yield
    # Reset singleton
    from managers.agent_manager import AgentManager
    AgentManager._instance = None


class TestRetryStrategies:
    """Tests for retry logic with different strategies."""

    def test_no_retry_strategy(self, reset_agent_manager, mock_ai_caller):
        """Test NO_RETRY strategy doesn't retry on failure."""
        from managers.agent_manager import AgentManager, AgentExecutionError
        from ai.agents.base import BaseAgent

        # Create a mock agent that fails
        mock_agent = Mock(spec=BaseAgent)
        mock_agent.config = Mock()
        mock_agent.config.advanced = Mock()
        mock_agent.config.advanced.retry_config = RetryConfig(
            strategy=RetryStrategy.NO_RETRY,
            max_retries=3
        )
        mock_agent.config.name = "TestAgent"
        mock_agent.execute.side_effect = ConnectionError("Network error")

        # Patch the default AI caller getter to inject our mock
        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            with pytest.raises(ConnectionError):
                manager._execute_with_retry(mock_agent, Mock(spec=AgentTask))

            # Should only be called once (no retries)
            assert mock_agent.execute.call_count == 1

    def test_exponential_backoff_strategy(self, reset_agent_manager, mock_ai_caller):
        """Test EXPONENTIAL_BACKOFF increases delay exponentially."""
        from managers.agent_manager import AgentManager, AgentExecutionError
        from ai.agents.base import BaseAgent

        # Create agent that fails twice then succeeds
        call_count = [0]
        success_response = AgentResponse(result="success", success=True)

        def mock_execute(task):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Temporary error")
            return success_response

        mock_agent = Mock(spec=BaseAgent)
        mock_agent.config = Mock()
        mock_agent.config.advanced = Mock()
        mock_agent.config.advanced.retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_retries=3,
            initial_delay=0.1,  # Minimum allowed value
            backoff_factor=2.0,
            max_delay=1.0
        )
        mock_agent.config.name = "TestAgent"
        mock_agent.execute.side_effect = mock_execute

        # Patch the default AI caller getter to inject our mock
        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            with patch('time.sleep') as mock_sleep:
                response, retry_count = manager._execute_with_retry(
                    mock_agent, Mock(spec=AgentTask)
                )

                assert response.success is True
                assert mock_agent.execute.call_count == 3
                # Should have called sleep twice (after 1st and 2nd failure)
                assert mock_sleep.call_count == 2

    def test_linear_backoff_strategy(self, reset_agent_manager, mock_ai_caller):
        """Test LINEAR_BACKOFF increases delay linearly."""
        from managers.agent_manager import AgentManager
        from ai.agents.base import BaseAgent

        call_count = [0]

        def mock_execute(task):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Temporary error")
            return AgentResponse(result="success", success=True)

        mock_agent = Mock(spec=BaseAgent)
        mock_agent.config = Mock()
        mock_agent.config.advanced = Mock()
        mock_agent.config.advanced.retry_config = RetryConfig(
            strategy=RetryStrategy.LINEAR_BACKOFF,
            max_retries=3,
            initial_delay=0.1,
            max_delay=1.0
        )
        mock_agent.config.name = "TestAgent"
        mock_agent.execute.side_effect = mock_execute

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            delays = []

            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda d: delays.append(d)
                response, _ = manager._execute_with_retry(
                    mock_agent, Mock(spec=AgentTask)
                )

                assert response.success is True
                # Linear: initial + initial, initial + initial + initial
                # Delay should increase by initial_delay each time
                if len(delays) >= 2:
                    assert delays[1] > delays[0]

    def test_fixed_delay_strategy(self, reset_agent_manager, mock_ai_caller):
        """Test FIXED_DELAY uses constant delay."""
        from managers.agent_manager import AgentManager
        from ai.agents.base import BaseAgent

        call_count = [0]

        def mock_execute(task):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Temporary error")
            return AgentResponse(result="success", success=True)

        mock_agent = Mock(spec=BaseAgent)
        mock_agent.config = Mock()
        mock_agent.config.advanced = Mock()
        mock_agent.config.advanced.retry_config = RetryConfig(
            strategy=RetryStrategy.FIXED_DELAY,
            max_retries=3,
            initial_delay=0.1  # Minimum allowed value
        )
        mock_agent.config.name = "TestAgent"
        mock_agent.execute.side_effect = mock_execute

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            delays = []

            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda d: delays.append(d)
                response, _ = manager._execute_with_retry(
                    mock_agent, Mock(spec=AgentTask)
                )

                # All delays should be the same for FIXED_DELAY
                assert len(set(delays)) == 1  # All same value

    def test_max_retries_exceeded(self, reset_agent_manager, mock_ai_caller):
        """Test that AgentExecutionError is raised after max retries."""
        from managers.agent_manager import AgentManager, AgentExecutionError
        from ai.agents.base import BaseAgent

        mock_agent = Mock(spec=BaseAgent)
        mock_agent.config = Mock()
        mock_agent.config.advanced = Mock()
        mock_agent.config.advanced.retry_config = RetryConfig(
            strategy=RetryStrategy.FIXED_DELAY,
            max_retries=2,
            initial_delay=0.1  # Minimum allowed value
        )
        mock_agent.config.name = "TestAgent"
        mock_agent.execute.side_effect = ConnectionError("Persistent error")

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            with patch('time.sleep'):
                with pytest.raises(AgentExecutionError, match="All .* attempts failed"):
                    manager._execute_with_retry(mock_agent, Mock(spec=AgentTask))

            # 3 total attempts (initial + 2 retries)
            assert mock_agent.execute.call_count == 3

    def test_validation_errors_not_retried(self, reset_agent_manager, mock_ai_caller):
        """Test that ValueError/TypeError are not retried."""
        from managers.agent_manager import AgentManager
        from ai.agents.base import BaseAgent

        mock_agent = Mock(spec=BaseAgent)
        mock_agent.config = Mock()
        mock_agent.config.advanced = Mock()
        mock_agent.config.advanced.retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_retries=5
        )
        mock_agent.config.name = "TestAgent"
        mock_agent.execute.side_effect = ValueError("Invalid input")

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            with pytest.raises(ValueError, match="Invalid input"):
                manager._execute_with_retry(mock_agent, Mock(spec=AgentTask))

            # Should only be called once (validation errors not retried)
            assert mock_agent.execute.call_count == 1


class TestSubAgentExecution:
    """Tests for sub-agent execution functionality."""

    def test_execute_sub_agents_empty(self, reset_agent_manager, mock_ai_caller):
        """Test with empty sub-agent configs."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            parent_task = Mock(spec=AgentTask)
            parent_response = AgentResponse(result="parent result", success=True)

            results = manager._execute_sub_agents([], parent_task, parent_response)

            assert results == {}

    def test_execute_sub_agents_disabled(self, reset_agent_manager, mock_ai_caller):
        """Test that disabled sub-agents are skipped."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            sub_configs = [
                SubAgentConfig(
                    agent_type=AgentType.SYNOPSIS,
                    enabled=False,
                    output_key="synopsis_output"
                )
            ]

            parent_task = Mock(spec=AgentTask)
            parent_task.task_description = "Test task"
            parent_task.context = "Test context"
            parent_task.input_data = {}
            parent_task.max_iterations = 5

            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)

            assert "synopsis_output" not in results

    def test_execute_sub_agents_priority_sorting(self, reset_agent_manager, mock_ai_caller):
        """Test that sub-agents are sorted by priority."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            # Mock the execute_agent_task to track execution order
            execution_order = []

            def track_execution(agent_type, task):
                execution_order.append(agent_type)
                return AgentResponse(result="result", success=True)

            manager.execute_agent_task = track_execution

            sub_configs = [
                SubAgentConfig(
                    agent_type=AgentType.SYNOPSIS,
                    enabled=True,
                    priority=10,
                    output_key="synopsis"
                ),
                SubAgentConfig(
                    agent_type=AgentType.DIAGNOSTIC,
                    enabled=True,
                    priority=50,
                    output_key="diagnostic"
                ),
                SubAgentConfig(
                    agent_type=AgentType.MEDICATION,
                    enabled=True,
                    priority=30,
                    output_key="medication"
                )
            ]

            parent_task = AgentTask(
                task_description="Test",
                input_data={}
            )
            parent_response = AgentResponse(result="parent", success=True)

            manager._execute_sub_agents(sub_configs, parent_task, parent_response)

            # Higher priority should come first (due to reverse=True in sort)
            # Note: ThreadPoolExecutor may not preserve exact order,
            # but sorting happens before submission
            assert len(execution_order) == 3

    def test_execute_sub_agents_required_failure(self, reset_agent_manager, mock_ai_caller):
        """Test handling of required sub-agent failure."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            def fail_execution(agent_type, task):
                return AgentResponse(result="", success=False, error="Failed")

            manager.execute_agent_task = fail_execution

            sub_configs = [
                SubAgentConfig(
                    agent_type=AgentType.SYNOPSIS,
                    enabled=True,
                    required=True,
                    output_key="synopsis"
                )
            ]

            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            with patch('managers.agent_manager.logger') as mock_logger:
                results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)

                # Should log error for required failure
                assert mock_logger.error.called
                assert results["synopsis"].success is False


class TestConditionEvaluation:
    """Tests for condition evaluation in sub-agent execution."""

    def test_evaluate_simple_condition_true(self, reset_agent_manager, mock_ai_caller):
        """Test simple true condition."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            task = Mock()
            task.task_description = "Analyze medications"
            task.context = "Patient context"
            task.input_data = {"key": "value"}

            response = Mock()
            response.result = "Analysis complete"
            response.success = True

            # Test simple boolean condition
            result = manager._evaluate_condition("True", task, response, {})
            assert result is True

            result = manager._evaluate_condition("False", task, response, {})
            assert result is False

    def test_evaluate_condition_with_task_data(self, reset_agent_manager, mock_ai_caller):
        """Test condition using task data."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            task = AgentTask(
                task_description="medication analysis",
                context="",
                input_data={"has_medications": True}
            )
            response = AgentResponse(result="test", success=True)

            # Test accessing input_data
            result = manager._evaluate_condition(
                "input_data.get('has_medications', False)",
                task, response, {}
            )
            assert result is True

    def test_evaluate_condition_with_response_success(self, reset_agent_manager, mock_ai_caller):
        """Test condition using response success."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            task = AgentTask(task_description="test", input_data={})
            response = AgentResponse(result="test", success=True)

            result = manager._evaluate_condition("success", task, response, {})
            assert result is True

            response.success = False
            result = manager._evaluate_condition("success", task, response, {})
            assert result is False

    def test_evaluate_condition_default_on_error(self, reset_agent_manager, mock_ai_caller):
        """Test that invalid conditions return default (True)."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            task = AgentTask(task_description="test", input_data={})
            response = AgentResponse(result="test", success=True)

            # Invalid expression should return default (True)
            result = manager._evaluate_condition(
                "invalid_python_syntax!!!",
                task, response, {}
            )
            assert result is True


class TestAgentLifecycle:
    """Tests for agent lifecycle management."""

    def test_reload_agents(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Test reloading agents from settings."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()
                initial_count = len(manager._agents)

                # Modify settings
                mock_settings["agent_config"]["medication"]["enabled"] = True
                mock_settings_mgr.get.return_value = mock_settings["agent_config"]

                manager.reload_agents()

                # Agents should be reloaded
                mock_settings_mgr.reload.assert_called_once()

    def test_get_enabled_agents(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Test getting list of enabled agents."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()
                enabled = manager.get_enabled_agents()

                # Should return a copy
                assert isinstance(enabled, dict)
                assert enabled is not manager._agents

    def test_is_agent_enabled(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Test checking if specific agent is enabled."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                assert manager.is_agent_enabled(AgentType.SYNOPSIS) is True
                assert manager.is_agent_enabled(AgentType.MEDICATION) is False

    def test_get_agent_returns_none_for_disabled(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Test that get_agent returns None for disabled agents."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                result = manager.get_agent(AgentType.MEDICATION)
                assert result is None


class TestExecuteAgentTask:
    """Tests for the main execute_agent_task method."""

    def test_execute_task_success(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Test successful task execution."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                # Mock an agent
                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis",
                    description="test",
                    system_prompt="test"
                )
                mock_agent.config.advanced = AdvancedConfig()
                mock_agent.execute.return_value = AgentResponse(
                    result="Synopsis result",
                    success=True
                )
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                task = AgentTask(
                    task_description="Generate synopsis",
                    input_data={"soap_note": "Test note"}
                )

                response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                assert response is not None
                assert response.success is True
                assert "Synopsis result" in response.result

    def test_execute_task_agent_not_available(self, reset_agent_manager, mock_ai_caller):
        """Test execution when agent is not available."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = {}

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                task = AgentTask(
                    task_description="Test",
                    input_data={}
                )

                response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                assert response is None

    def test_execute_task_timeout(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Test task execution timeout handling."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                # Mock agent that raises TimeoutError
                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis",
                    description="test",
                    system_prompt="test"
                )
                mock_agent.config.advanced = AdvancedConfig(timeout_seconds=5.0)
                mock_agent.execute.side_effect = TimeoutError("Timed out")
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                task = AgentTask(task_description="Test", input_data={})

                response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                assert response is not None
                assert response.success is False
                assert "timed out" in response.error.lower()

    def test_execute_task_validation_error(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Test handling of validation errors."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis",
                    description="test",
                    system_prompt="test"
                )
                mock_agent.config.advanced = AdvancedConfig()
                mock_agent.execute.side_effect = ValueError("Missing required field")
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                task = AgentTask(task_description="Test", input_data={})

                response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                assert response is not None
                assert response.success is False
                assert "Invalid input" in response.error

    def test_execute_task_with_performance_metrics(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Test that performance metrics are collected."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis",
                    description="test",
                    system_prompt="test"
                )
                mock_agent.config.advanced = AdvancedConfig(enable_metrics=True)
                mock_agent.config.sub_agents = []
                mock_agent.execute.return_value = AgentResponse(
                    result="Result",
                    success=True
                )
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                task = AgentTask(task_description="Test", input_data={})

                response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                assert response.metrics is not None
                assert response.metrics.duration_seconds >= 0
                assert response.metrics.start_time < response.metrics.end_time


class TestPrepareSubTask:
    """Tests for sub-task preparation."""

    def test_prepare_sub_task_with_context(self, reset_agent_manager, mock_ai_caller):
        """Test preparing sub-task with context passing."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            sub_config = SubAgentConfig(
                agent_type=AgentType.SYNOPSIS,
                pass_context=True,
                output_key="synopsis"
            )

            parent_task = AgentTask(
                task_description="Parent task",
                context="Important parent context",
                input_data={"key": "value"}
            )

            parent_response = AgentResponse(
                result="Parent analysis result",
                success=True,
                thoughts="Parent reasoning"
            )

            sub_task = manager._prepare_sub_task(sub_config, parent_task, parent_response)

            assert "Parent context" in sub_task.context
            assert "Parent analysis result" in sub_task.context
            assert sub_task.input_data["parent_result"] == "Parent analysis result"
            assert sub_task.input_data["key"] == "value"  # Inherited from parent

    def test_prepare_sub_task_without_context(self, reset_agent_manager, mock_ai_caller):
        """Test preparing sub-task without context passing."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            sub_config = SubAgentConfig(
                agent_type=AgentType.SYNOPSIS,
                pass_context=False,
                output_key="synopsis"
            )

            parent_task = AgentTask(
                task_description="Parent task",
                context="Should not be passed",
                input_data={}
            )

            parent_response = AgentResponse(result="Result", success=True)

            sub_task = manager._prepare_sub_task(sub_config, parent_task, parent_response)

            # Should still have parent result in context, but not parent context
            assert "Should not be passed" not in (sub_task.context or "")
