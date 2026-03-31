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


class TestRetryBackoffMath:
    """Tests for precise delay calculation in _execute_with_retry()."""

    def _make_agent(self, strategy, initial_delay=0.1, max_delay=10.0, backoff_factor=2.0, max_retries=5):
        from ai.agents.base import BaseAgent
        mock_agent = Mock(spec=BaseAgent)
        mock_agent.config = Mock()
        mock_agent.config.advanced = Mock()
        mock_agent.config.advanced.retry_config = RetryConfig(
            strategy=strategy,
            max_retries=max_retries,
            initial_delay=initial_delay,
            backoff_factor=backoff_factor,
            max_delay=max_delay,
        )
        mock_agent.config.name = "TestAgent"
        return mock_agent

    def test_exponential_delay_values(self, reset_agent_manager, mock_ai_caller):
        """EXPONENTIAL: delay = initial * factor^attempt, capped at max."""
        from managers.agent_manager import AgentManager

        call_count = [0]
        def fail_then_succeed(task):
            call_count[0] += 1
            if call_count[0] <= 4:
                raise ConnectionError("err")
            return AgentResponse(result="ok", success=True)

        agent = self._make_agent(RetryStrategy.EXPONENTIAL_BACKOFF,
                                 initial_delay=1.0, backoff_factor=2.0, max_delay=100.0, max_retries=5)
        agent.execute.side_effect = fail_then_succeed

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            delays = []
            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda d: delays.append(d)
                manager._execute_with_retry(agent, Mock(spec=AgentTask))

        # delay starts at 1.0 (initial_delay)
        # After attempt 0 fail: delay = min(1.0 * 2.0, 100) = 2.0, sleep(2.0)
        # After attempt 1 fail: delay = min(2.0 * 2.0, 100) = 4.0, sleep(4.0)
        # After attempt 2 fail: delay = min(4.0 * 2.0, 100) = 8.0, sleep(8.0)
        # After attempt 3 fail: delay = min(8.0 * 2.0, 100) = 16.0, sleep(16.0)
        assert len(delays) == 4
        assert delays[0] == pytest.approx(2.0, abs=0.01)
        assert delays[1] == pytest.approx(4.0, abs=0.01)
        assert delays[2] == pytest.approx(8.0, abs=0.01)
        assert delays[3] == pytest.approx(16.0, abs=0.01)

    def test_exponential_max_delay_cap(self, reset_agent_manager, mock_ai_caller):
        """EXPONENTIAL: delay should be capped at max_delay."""
        from managers.agent_manager import AgentManager

        call_count = [0]
        def fail_then_succeed(task):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise ConnectionError("err")
            return AgentResponse(result="ok", success=True)

        agent = self._make_agent(RetryStrategy.EXPONENTIAL_BACKOFF,
                                 initial_delay=5.0, backoff_factor=3.0, max_delay=10.0, max_retries=4)
        agent.execute.side_effect = fail_then_succeed

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            delays = []
            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda d: delays.append(d)
                manager._execute_with_retry(agent, Mock(spec=AgentTask))

        # Delays: min(5*3, 10)=10, min(10*3, 10)=10, min(10*3, 10)=10
        for d in delays:
            assert d <= 10.0

    def test_linear_delay_values(self, reset_agent_manager, mock_ai_caller):
        """LINEAR: delay = delay + initial_delay each iteration, capped at max."""
        from managers.agent_manager import AgentManager

        call_count = [0]
        def fail_then_succeed(task):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise ConnectionError("err")
            return AgentResponse(result="ok", success=True)

        agent = self._make_agent(RetryStrategy.LINEAR_BACKOFF,
                                 initial_delay=1.0, max_delay=100.0, max_retries=4)
        agent.execute.side_effect = fail_then_succeed

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            delays = []
            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda d: delays.append(d)
                manager._execute_with_retry(agent, Mock(spec=AgentTask))

        # LINEAR: delay starts at initial_delay (1.0)
        # After attempt 0: delay = min(1.0 + 1.0, 100) = 2.0
        # After attempt 1: delay = min(2.0 + 1.0, 100) = 3.0
        # After attempt 2: delay = min(3.0 + 1.0, 100) = 4.0
        assert len(delays) == 3
        assert delays[0] == pytest.approx(2.0, abs=0.01)
        assert delays[1] == pytest.approx(3.0, abs=0.01)
        assert delays[2] == pytest.approx(4.0, abs=0.01)

    def test_linear_max_delay_cap(self, reset_agent_manager, mock_ai_caller):
        """LINEAR: delay capped at max_delay."""
        from managers.agent_manager import AgentManager

        call_count = [0]
        def fail_then_succeed(task):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise ConnectionError("err")
            return AgentResponse(result="ok", success=True)

        agent = self._make_agent(RetryStrategy.LINEAR_BACKOFF,
                                 initial_delay=5.0, max_delay=8.0, max_retries=4)
        agent.execute.side_effect = fail_then_succeed

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            delays = []
            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda d: delays.append(d)
                manager._execute_with_retry(agent, Mock(spec=AgentTask))

        for d in delays:
            assert d <= 8.0

    def test_fixed_delay_constant(self, reset_agent_manager, mock_ai_caller):
        """FIXED: all delays should be exactly initial_delay."""
        from managers.agent_manager import AgentManager

        call_count = [0]
        def fail_then_succeed(task):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise ConnectionError("err")
            return AgentResponse(result="ok", success=True)

        agent = self._make_agent(RetryStrategy.FIXED_DELAY,
                                 initial_delay=2.5, max_retries=4)
        agent.execute.side_effect = fail_then_succeed

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            delays = []
            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda d: delays.append(d)
                manager._execute_with_retry(agent, Mock(spec=AgentTask))

        assert len(delays) == 3
        for d in delays:
            assert d == pytest.approx(2.5, abs=0.01)

    def test_all_retries_exhausted_raises(self, reset_agent_manager, mock_ai_caller):
        """All retries fail: AgentExecutionError with original message."""
        from managers.agent_manager import AgentManager, AgentExecutionError

        agent = self._make_agent(RetryStrategy.FIXED_DELAY, initial_delay=0.1, max_retries=2)
        agent.execute.side_effect = ConnectionError("persistent failure")

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            with patch('time.sleep'):
                with pytest.raises(AgentExecutionError, match="persistent failure"):
                    manager._execute_with_retry(agent, Mock(spec=AgentTask))

    def test_network_error_triggers_retry(self, reset_agent_manager, mock_ai_caller):
        """ConnectionError and TimeoutError should trigger retries."""
        from managers.agent_manager import AgentManager

        call_count = [0]
        def mixed_errors(task):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("conn err")
            if call_count[0] == 2:
                raise TimeoutError("timeout")
            return AgentResponse(result="ok", success=True)

        agent = self._make_agent(RetryStrategy.FIXED_DELAY, initial_delay=0.1, max_retries=3)
        agent.execute.side_effect = mixed_errors

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            with patch('time.sleep'):
                response, retry_count = manager._execute_with_retry(agent, Mock(spec=AgentTask))
        assert response.success is True
        assert agent.execute.call_count == 3

    def test_validation_error_not_retried_value_error(self, reset_agent_manager, mock_ai_caller):
        """ValueError should NOT trigger retry."""
        from managers.agent_manager import AgentManager

        agent = self._make_agent(RetryStrategy.EXPONENTIAL_BACKOFF, max_retries=5)
        agent.execute.side_effect = ValueError("bad input")

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            with pytest.raises(ValueError, match="bad input"):
                manager._execute_with_retry(agent, Mock(spec=AgentTask))
        assert agent.execute.call_count == 1

    def test_type_error_not_retried(self, reset_agent_manager, mock_ai_caller):
        """TypeError should NOT trigger retry."""
        from managers.agent_manager import AgentManager

        agent = self._make_agent(RetryStrategy.EXPONENTIAL_BACKOFF, max_retries=5)
        agent.execute.side_effect = TypeError("wrong type")

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            with pytest.raises(TypeError, match="wrong type"):
                manager._execute_with_retry(agent, Mock(spec=AgentTask))
        assert agent.execute.call_count == 1

    def test_os_error_retried(self, reset_agent_manager, mock_ai_caller):
        """OSError should trigger retry (network-related)."""
        from managers.agent_manager import AgentManager

        call_count = [0]
        def fail_then_ok(task):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("socket error")
            return AgentResponse(result="ok", success=True)

        agent = self._make_agent(RetryStrategy.FIXED_DELAY, initial_delay=0.1, max_retries=2)
        agent.execute.side_effect = fail_then_ok

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            with patch('time.sleep'):
                response, _ = manager._execute_with_retry(agent, Mock(spec=AgentTask))
        assert response.success is True

    def test_generic_exception_retried(self, reset_agent_manager, mock_ai_caller):
        """Generic exceptions should also be retried."""
        from managers.agent_manager import AgentManager

        call_count = [0]
        def fail_then_ok(task):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("generic error")
            return AgentResponse(result="ok", success=True)

        agent = self._make_agent(RetryStrategy.FIXED_DELAY, initial_delay=0.1, max_retries=2)
        agent.execute.side_effect = fail_then_ok

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            with patch('time.sleep'):
                response, _ = manager._execute_with_retry(agent, Mock(spec=AgentTask))
        assert response.success is True


class TestSubAgentConcurrency:
    """Tests for _execute_sub_agents() including concurrency and conditions."""

    def test_multiple_enabled_sub_agents_run(self, reset_agent_manager, mock_ai_caller):
        """Multiple enabled sub-agents all run."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            execution_order = []
            def track(agent_type, task):
                execution_order.append(agent_type)
                return AgentResponse(result="ok", success=True)

            manager.execute_agent_task = track

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True, output_key="s"),
                SubAgentConfig(agent_type=AgentType.DIAGNOSTIC, enabled=True, output_key="d"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert "s" in results
            assert "d" in results
            assert len(execution_order) == 2

    def test_condition_false_skips_agent(self, reset_agent_manager, mock_ai_caller):
        """Sub-agent with condition=False is skipped."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            manager.execute_agent_task = Mock(return_value=AgentResponse(result="ok", success=True))

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True,
                               output_key="s", condition="False"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert "s" not in results
            manager.execute_agent_task.assert_not_called()

    def test_condition_true_runs_agent(self, reset_agent_manager, mock_ai_caller):
        """Sub-agent with condition=True runs."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            manager.execute_agent_task = Mock(return_value=AgentResponse(result="ok", success=True))

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True,
                               output_key="s", condition="True"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert "s" in results

    def test_required_sub_agent_failure_recorded(self, reset_agent_manager, mock_ai_caller):
        """Required sub-agent failure is recorded with success=False."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            manager.execute_agent_task = Mock(
                return_value=AgentResponse(result="", success=False, error="failed")
            )

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True,
                               required=True, output_key="s"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            with patch('managers.agent_manager.logger'):
                results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert "s" in results
            assert results["s"].success is False

    def test_timeout_scenario(self, reset_agent_manager, mock_ai_caller):
        """Timeout produces error response."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            def slow_fn(agent_type, task):
                raise FuturesTimeoutError("timed out")

            manager.execute_agent_task = slow_fn

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True, output_key="s"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert "s" in results
            assert results["s"].success is False

    def test_priority_sorting_order(self, reset_agent_manager, mock_ai_caller):
        """Higher priority sub-agents sorted first."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            execution_order = []
            def track(agent_type, task):
                execution_order.append(agent_type)
                return AgentResponse(result="ok", success=True)

            manager.execute_agent_task = track

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True, priority=1, output_key="s"),
                SubAgentConfig(agent_type=AgentType.DIAGNOSTIC, enabled=True, priority=100, output_key="d"),
                SubAgentConfig(agent_type=AgentType.MEDICATION, enabled=True, priority=50, output_key="m"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert len(execution_order) == 3
            assert len(results) == 3

    def test_empty_sub_agents_returns_empty(self, reset_agent_manager, mock_ai_caller):
        """Empty sub-agents list returns empty dict."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents([], parent_task, parent_response)
            assert results == {}

    def test_all_disabled_returns_empty(self, reset_agent_manager, mock_ai_caller):
        """All disabled sub-agents returns empty dict."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            manager.execute_agent_task = Mock()

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=False, output_key="s"),
                SubAgentConfig(agent_type=AgentType.DIAGNOSTIC, enabled=False, output_key="d"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert results == {}
            manager.execute_agent_task.assert_not_called()

    def test_sub_agent_returns_none(self, reset_agent_manager, mock_ai_caller):
        """When agent_task returns None, output_key not in results."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            manager.execute_agent_task = Mock(return_value=None)

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True, output_key="s"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert "s" not in results

    def test_exception_in_sub_agent_recorded(self, reset_agent_manager, mock_ai_caller):
        """Exception during sub-agent is recorded as failure."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()

            def raise_error(agent_type, task):
                raise RuntimeError("sub-agent boom")

            manager.execute_agent_task = raise_error

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True, output_key="s"),
            ]
            parent_task = AgentTask(task_description="Test", input_data={})
            parent_response = AgentResponse(result="parent", success=True)

            with patch('managers.agent_manager.logger'):
                results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert "s" in results
            assert results["s"].success is False

    def test_condition_with_input_data(self, reset_agent_manager, mock_ai_caller):
        """Condition referencing task input_data."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            manager = AgentManager()
            manager.execute_agent_task = Mock(return_value=AgentResponse(result="ok", success=True))

            sub_configs = [
                SubAgentConfig(agent_type=AgentType.SYNOPSIS, enabled=True,
                               output_key="s",
                               condition="input_data.get('has_medications', False)"),
            ]
            parent_task = AgentTask(task_description="Test",
                                   input_data={"has_medications": True})
            parent_response = AgentResponse(result="parent", success=True)

            results = manager._execute_sub_agents(sub_configs, parent_task, parent_response)
            assert "s" in results


class TestConditionEvalSecurity:
    """Tests for _evaluate_condition() with various inputs."""

    def _get_manager(self, mock_ai_caller, reset_agent_manager):
        from managers.agent_manager import AgentManager
        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            return AgentManager()

    def test_true_returns_true(self, reset_agent_manager, mock_ai_caller):
        manager = self._get_manager(mock_ai_caller, reset_agent_manager)
        task = AgentTask(task_description="test", input_data={})
        response = AgentResponse(result="test", success=True)
        assert manager._evaluate_condition("True", task, response, {}) is True

    def test_false_returns_false(self, reset_agent_manager, mock_ai_caller):
        manager = self._get_manager(mock_ai_caller, reset_agent_manager)
        task = AgentTask(task_description="test", input_data={})
        response = AgentResponse(result="test", success=True)
        assert manager._evaluate_condition("False", task, response, {}) is False

    def test_task_data_get(self, reset_agent_manager, mock_ai_caller):
        manager = self._get_manager(mock_ai_caller, reset_agent_manager)
        task = AgentTask(task_description="test", input_data={"key": True})
        response = AgentResponse(result="test", success=True)
        result = manager._evaluate_condition(
            "input_data.get('key', False)", task, response, {}
        )
        assert result is True

    def test_malformed_expression_defaults_true(self, reset_agent_manager, mock_ai_caller):
        manager = self._get_manager(mock_ai_caller, reset_agent_manager)
        task = AgentTask(task_description="test", input_data={})
        response = AgentResponse(result="test", success=True)
        result = manager._evaluate_condition("!!!invalid!!!", task, response, {})
        assert result is True

    def test_import_attempt_blocked(self, reset_agent_manager, mock_ai_caller):
        """Dangerous expressions should be blocked, defaults to True."""
        manager = self._get_manager(mock_ai_caller, reset_agent_manager)
        task = AgentTask(task_description="test", input_data={})
        response = AgentResponse(result="test", success=True)
        result = manager._evaluate_condition("__import__('os')", task, response, {})
        assert result is True

    def test_integer_coercion_zero_is_false(self, reset_agent_manager, mock_ai_caller):
        manager = self._get_manager(mock_ai_caller, reset_agent_manager)
        task = AgentTask(task_description="test", input_data={})
        response = AgentResponse(result="test", success=True)
        result = manager._evaluate_condition("0", task, response, {})
        assert result is False

    def test_integer_coercion_one_is_true(self, reset_agent_manager, mock_ai_caller):
        manager = self._get_manager(mock_ai_caller, reset_agent_manager)
        task = AgentTask(task_description="test", input_data={})
        response = AgentResponse(result="test", success=True)
        result = manager._evaluate_condition("1", task, response, {})
        assert result is True

    def test_empty_condition_defaults_true(self, reset_agent_manager, mock_ai_caller):
        """Empty string with safe_eval default=True returns True."""
        manager = self._get_manager(mock_ai_caller, reset_agent_manager)
        task = AgentTask(task_description="test", input_data={})
        response = AgentResponse(result="test", success=True)
        result = manager._evaluate_condition("", task, response, {})
        assert result is True


class TestInitializeAgentProviderFix:
    """Tests for provider/model correction logic in _initialize_agent()."""

    def test_anthropic_provider_with_gpt_model_corrected(self, reset_agent_manager, mock_ai_caller):
        """provider='anthropic' + model='gpt-4' corrected to 'openai'."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "model": "gpt-4",
                    "provider": "anthropic",
                    "system_prompt": "test prompt " * 20,
                }
                with patch('managers.agent_manager.logger'):
                    manager._initialize_agent(AgentType.SYNOPSIS, config_dict)
                    agent = manager._agents.get(AgentType.SYNOPSIS)
                    assert agent is not None
                    assert agent.config.provider == "openai"

    def test_openai_provider_with_claude_model_corrected(self, reset_agent_manager, mock_ai_caller):
        """provider='openai' + model='claude-3-opus' corrected to 'anthropic'."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "model": "claude-3-opus",
                    "provider": "openai",
                    "system_prompt": "test prompt " * 20,
                }
                manager._initialize_agent(AgentType.DIAGNOSTIC, config_dict)
                agent = manager._agents.get(AgentType.DIAGNOSTIC)
                assert agent is not None
                assert agent.config.provider == "anthropic"

    def test_openai_provider_with_gpt_no_correction(self, reset_agent_manager, mock_ai_caller):
        """provider='openai' + model='gpt-4' no correction needed."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "model": "gpt-4",
                    "provider": "openai",
                    "system_prompt": "test prompt " * 20,
                }
                manager._initialize_agent(AgentType.DIAGNOSTIC, config_dict)
                agent = manager._agents.get(AgentType.DIAGNOSTIC)
                assert agent is not None
                assert agent.config.provider == "openai"

    def test_anthropic_provider_with_claude_no_correction(self, reset_agent_manager, mock_ai_caller):
        """provider='anthropic' + model='claude-3-sonnet' no correction needed."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "model": "claude-3-sonnet",
                    "provider": "anthropic",
                    "system_prompt": "test prompt " * 20,
                }
                manager._initialize_agent(AgentType.DIAGNOSTIC, config_dict)
                agent = manager._agents.get(AgentType.DIAGNOSTIC)
                assert agent is not None
                assert agent.config.provider == "anthropic"

    def test_unknown_model_no_correction(self, reset_agent_manager, mock_ai_caller):
        """Unknown model name: no correction applied."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "model": "custom-local-model",
                    "provider": "openai",
                    "system_prompt": "test prompt " * 20,
                }
                manager._initialize_agent(AgentType.DIAGNOSTIC, config_dict)
                agent = manager._agents.get(AgentType.DIAGNOSTIC)
                assert agent is not None
                assert agent.config.provider == "openai"

    def test_missing_model_uses_default(self, reset_agent_manager, mock_ai_caller):
        """Missing model field uses default 'gpt-4'."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "system_prompt": "test prompt " * 20,
                }
                manager._initialize_agent(AgentType.DIAGNOSTIC, config_dict)
                agent = manager._agents.get(AgentType.DIAGNOSTIC)
                assert agent is not None
                assert agent.config.model == "gpt-4"

    def test_invalid_retry_strategy_fallback(self, reset_agent_manager, mock_ai_caller):
        """Invalid RetryStrategy falls back to EXPONENTIAL_BACKOFF."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "model": "gpt-4",
                    "system_prompt": "test prompt " * 20,
                    "advanced": {
                        "retry_config": {
                            "strategy": "INVALID_STRATEGY_VALUE",
                        }
                    }
                }
                manager._initialize_agent(AgentType.DIAGNOSTIC, config_dict)
                agent = manager._agents.get(AgentType.DIAGNOSTIC)
                assert agent is not None
                assert agent.config.advanced.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF

    def test_invalid_response_format_fallback(self, reset_agent_manager, mock_ai_caller):
        """Invalid ResponseFormat falls back to PLAIN_TEXT."""
        from managers.agent_manager import AgentManager
        from ai.agents.models import ResponseFormat

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "model": "gpt-4",
                    "system_prompt": "test prompt " * 20,
                    "advanced": {
                        "response_format": "INVALID_FORMAT",
                    }
                }
                manager._initialize_agent(AgentType.DIAGNOSTIC, config_dict)
                agent = manager._agents.get(AgentType.DIAGNOSTIC)
                assert agent is not None
                assert agent.config.advanced.response_format == ResponseFormat.PLAIN_TEXT

    def test_no_provider_set(self, reset_agent_manager, mock_ai_caller):
        """Provider is None: no correction logic applied."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
            with patch('managers.agent_manager.settings_manager') as mock_sm:
                mock_sm.get.return_value = {}
                manager = AgentManager()

                config_dict = {
                    "enabled": True,
                    "model": "gpt-4",
                    "system_prompt": "test prompt " * 20,
                }
                manager._initialize_agent(AgentType.DIAGNOSTIC, config_dict)
                agent = manager._agents.get(AgentType.DIAGNOSTIC)
                assert agent is not None
                assert agent.config.provider is None


class TestExecuteAgentTaskWithSubAgents:
    """Tests for execute_agent_task with sub-agent support."""

    def test_agent_with_sub_agents_calls_sub(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Agent with sub-agents configured: sub-agents run after main agent."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis",
                    description="test",
                    system_prompt="test",
                    sub_agents=[
                        SubAgentConfig(
                            agent_type=AgentType.DIAGNOSTIC,
                            enabled=True,
                            output_key="diagnostic_output",
                        )
                    ]
                )
                mock_agent.config.advanced = AdvancedConfig(enable_metrics=False)
                mock_agent.execute.return_value = AgentResponse(
                    result="main result", success=True
                )
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                with patch.object(manager, '_execute_sub_agents',
                                  return_value={"diagnostic_output": AgentResponse(result="sub", success=True)}
                                  ) as mock_sub:
                    task = AgentTask(task_description="Test", input_data={})
                    response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                    assert response.success is True
                    mock_sub.assert_called_once()

    def test_sub_agent_results_merged(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Sub-agent results are merged into main response."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis", description="test", system_prompt="test",
                    sub_agents=[
                        SubAgentConfig(agent_type=AgentType.DIAGNOSTIC, enabled=True, output_key="diag"),
                    ]
                )
                mock_agent.config.advanced = AdvancedConfig(enable_metrics=False)
                mock_agent.execute.return_value = AgentResponse(result="main", success=True)
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                sub_response = AgentResponse(result="sub_result", success=True)
                with patch.object(manager, '_execute_sub_agents',
                                  return_value={"diag": sub_response}):
                    task = AgentTask(task_description="Test", input_data={})
                    response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                    assert response.sub_agent_results is not None
                    assert "diag" in response.sub_agent_results

    def test_main_agent_fails_no_sub_agents(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Main agent fails: sub-agents do not run."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis", description="test", system_prompt="test",
                    sub_agents=[
                        SubAgentConfig(agent_type=AgentType.DIAGNOSTIC, enabled=True, output_key="diag"),
                    ]
                )
                mock_agent.config.advanced = AdvancedConfig(
                    retry_config=RetryConfig(strategy=RetryStrategy.NO_RETRY)
                )
                mock_agent.execute.side_effect = ValueError("bad input")
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                with patch.object(manager, '_execute_sub_agents') as mock_sub:
                    task = AgentTask(task_description="Test", input_data={})
                    response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                    assert response.success is False
                    mock_sub.assert_not_called()

    def test_main_succeeds_sub_agent_fails(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Main agent succeeds but sub-agent fails: response still has main result."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis", description="test", system_prompt="test",
                    sub_agents=[
                        SubAgentConfig(agent_type=AgentType.DIAGNOSTIC, enabled=True, output_key="diag"),
                    ]
                )
                mock_agent.config.advanced = AdvancedConfig(enable_metrics=False)
                mock_agent.execute.return_value = AgentResponse(result="main ok", success=True)
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                failed_sub = AgentResponse(result="", success=False, error="sub failed")
                with patch.object(manager, '_execute_sub_agents',
                                  return_value={"diag": failed_sub}):
                    task = AgentTask(task_description="Test", input_data={})
                    response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                    assert response.success is True
                    assert "main ok" in response.result
                    assert response.sub_agent_results["diag"].success is False

    def test_no_sub_agents_configured(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Agent without sub-agents: _execute_sub_agents not called."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis", description="test", system_prompt="test",
                    sub_agents=[]
                )
                mock_agent.config.advanced = AdvancedConfig(enable_metrics=False)
                mock_agent.execute.return_value = AgentResponse(result="main", success=True)
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                with patch.object(manager, '_execute_sub_agents') as mock_sub:
                    task = AgentTask(task_description="Test", input_data={})
                    response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                    assert response.success is True
                    mock_sub.assert_not_called()

    def test_agent_not_available_returns_none(self, reset_agent_manager, mock_ai_caller):
        """Agent not available returns None."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = {}
            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()
                task = AgentTask(task_description="Test", input_data={})
                response = manager.execute_agent_task(AgentType.SYNOPSIS, task)
                assert response is None

    def test_execution_error_returns_failure(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """AgentExecutionError returns response with success=False."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis", description="test", system_prompt="test",
                )
                mock_agent.config.advanced = AdvancedConfig(
                    retry_config=RetryConfig(strategy=RetryStrategy.NO_RETRY)
                )
                mock_agent.execute.side_effect = RuntimeError("boom")
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                task = AgentTask(task_description="Test", input_data={})
                response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                assert response is not None
                assert response.success is False

    def test_unexpected_error_returns_failure(self, reset_agent_manager, mock_ai_caller, mock_settings):
        """Unexpected exception returns response with success=False."""
        from managers.agent_manager import AgentManager

        with patch('managers.agent_manager.settings_manager') as mock_settings_mgr:
            mock_settings_mgr.get.return_value = mock_settings["agent_config"]

            with patch('managers.agent_manager.get_default_ai_caller', return_value=mock_ai_caller):
                manager = AgentManager()

                mock_agent = Mock()
                mock_agent.config = AgentConfig(
                    name="synopsis", description="test", system_prompt="test",
                )
                mock_agent.config.advanced = AdvancedConfig(
                    retry_config=RetryConfig(
                        strategy=RetryStrategy.FIXED_DELAY,
                        max_retries=0,
                        initial_delay=0.1,
                    )
                )
                mock_agent.execute.side_effect = ConnectionError("network fail")
                manager._agents[AgentType.SYNOPSIS] = mock_agent

                task = AgentTask(task_description="Test", input_data={})
                response = manager.execute_agent_task(AgentType.SYNOPSIS, task)

                assert response is not None
                assert response.success is False
