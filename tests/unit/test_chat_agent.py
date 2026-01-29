"""
Unit tests for ChatAgent.

Tests cover:
- Tool call extraction from AI responses
- Tool execution
- Follow-up prompt building
- Tool registry integration
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from ai.agents.chat import ChatAgent
from ai.agents.models import AgentConfig, AgentTask, AgentResponse, ToolCall
from ai.agents.ai_caller import MockAICaller


@pytest.fixture
def mock_tool_registry():
    """Create a mock tool registry."""
    registry = Mock()
    registry.get_all_definitions.return_value = []
    registry.get_cache_info.return_value = (1, True)
    return registry


@pytest.fixture
def mock_tool_executor():
    """Create a mock tool executor."""
    from ai.tools import ToolResult
    executor = Mock()
    executor.execute_tool.return_value = ToolResult(
        success=True,
        output={"result": "Tool executed successfully"}
    )
    return executor


@pytest.fixture
def chat_agent(mock_ai_caller, mock_tool_executor):
    """Create a ChatAgent with mock dependencies."""
    with patch('ai.agents.chat.tool_registry') as mock_registry:
        mock_registry.get_all_definitions.return_value = []
        mock_registry.get_cache_info.return_value = (1, True)

        agent = ChatAgent(
            ai_caller=mock_ai_caller,
            tool_executor=mock_tool_executor
        )
        return agent


class TestToolCallExtraction:
    """Tests for extracting tool calls from AI responses."""

    def test_extract_single_tool_call(self, chat_agent):
        """Test extraction of a single tool call."""
        response = """I'll search for that information.
<tool_call>
{
  "tool_name": "web_search",
  "arguments": {
    "query": "hypertension guidelines 2024"
  }
}
</tool_call>

Let me search for the latest guidelines."""

        tool_calls, remaining = chat_agent._extract_tool_calls(response)

        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "web_search"
        assert tool_calls[0].arguments["query"] == "hypertension guidelines 2024"
        assert "<tool_call>" not in remaining

    def test_extract_multiple_tool_calls(self, chat_agent):
        """Test extraction of multiple tool calls."""
        response = """I'll need to search for multiple things.
<tool_call>
{"tool_name": "search1", "arguments": {"query": "query1"}}
</tool_call>
<tool_call>
{"tool_name": "search2", "arguments": {"query": "query2"}}
</tool_call>"""

        tool_calls, remaining = chat_agent._extract_tool_calls(response)

        assert len(tool_calls) == 2
        assert tool_calls[0].tool_name == "search1"
        assert tool_calls[1].tool_name == "search2"

    def test_extract_no_tool_calls(self, chat_agent):
        """Test extraction when no tool calls present."""
        response = "I can help you with that question directly."

        tool_calls, remaining = chat_agent._extract_tool_calls(response)

        assert len(tool_calls) == 0
        assert remaining == response

    def test_extract_invalid_json(self, chat_agent):
        """Test handling of invalid JSON in tool call."""
        response = """<tool_call>
{invalid json here}
</tool_call>"""

        tool_calls, remaining = chat_agent._extract_tool_calls(response)

        # Should skip invalid JSON and continue
        assert len(tool_calls) == 0

    def test_extract_preserves_remaining_text(self, chat_agent):
        """Test that remaining text is preserved correctly."""
        response = """Before text.
<tool_call>
{"tool_name": "test", "arguments": {}}
</tool_call>
After text."""

        tool_calls, remaining = chat_agent._extract_tool_calls(response)

        assert "Before text" in remaining
        assert "After text" in remaining
        assert "<tool_call>" not in remaining

    def test_extract_complex_arguments(self, chat_agent):
        """Test extraction with complex nested arguments."""
        response = """<tool_call>
{
  "tool_name": "complex_tool",
  "arguments": {
    "nested": {"key": "value"},
    "list": [1, 2, 3],
    "boolean": true
  }
}
</tool_call>"""

        tool_calls, _ = chat_agent._extract_tool_calls(response)

        assert len(tool_calls) == 1
        assert tool_calls[0].arguments["nested"]["key"] == "value"
        assert tool_calls[0].arguments["list"] == [1, 2, 3]
        assert tool_calls[0].arguments["boolean"] is True


class TestToolExecution:
    """Tests for tool execution."""

    def test_execute_tools(self, chat_agent, mock_tool_executor):
        """Test executing tools."""
        tool_calls = [
            ToolCall(tool_name="search", arguments={"query": "test"})
        ]

        results = chat_agent._execute_tools(tool_calls)

        assert "search" in results
        assert results["search"].success is True
        mock_tool_executor.execute_tool.assert_called_once_with(
            "search", {"query": "test"}
        )

    def test_execute_multiple_tools(self, chat_agent, mock_tool_executor):
        """Test executing multiple tools."""
        tool_calls = [
            ToolCall(tool_name="tool1", arguments={}),
            ToolCall(tool_name="tool2", arguments={})
        ]

        results = chat_agent._execute_tools(tool_calls)

        assert len(results) == 2
        assert mock_tool_executor.execute_tool.call_count == 2

    def test_execute_tools_with_failure(self, chat_agent, mock_tool_executor):
        """Test handling of tool execution failure."""
        from ai.tools import ToolResult

        mock_tool_executor.execute_tool.return_value = ToolResult(
            success=False,
            output=None,
            error="Tool failed"
        )

        tool_calls = [
            ToolCall(tool_name="failing_tool", arguments={})
        ]

        results = chat_agent._execute_tools(tool_calls)

        assert results["failing_tool"].success is False
        assert results["failing_tool"].error == "Tool failed"


class TestPromptBuilding:
    """Tests for prompt building methods."""

    def test_build_prompt_basic(self, chat_agent):
        """Test basic prompt building."""
        task = AgentTask(
            task_description="What is the BP target for diabetics?",
            input_data={}
        )

        prompt = chat_agent._build_prompt(task)

        assert "BP target" in prompt
        assert "diabetics" in prompt

    def test_build_prompt_with_context(self, chat_agent):
        """Test prompt building with context."""
        task = AgentTask(
            task_description="Answer the question",
            context="Patient has hypertension and diabetes",
            input_data={}
        )

        prompt = chat_agent._build_prompt(task)

        assert "hypertension" in prompt
        assert "diabetes" in prompt

    def test_build_prompt_includes_tools(self, chat_agent):
        """Test that prompt includes available tools."""
        from ai.agents.models import Tool, ToolParameter

        chat_agent.config.available_tools = [
            Tool(
                name="search",
                description="Search the web",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search query",
                        required=True
                    )
                ]
            )
        ]

        task = AgentTask(
            task_description="Test",
            input_data={}
        )

        prompt = chat_agent._build_prompt(task)

        assert "search" in prompt
        assert "Search the web" in prompt

    def test_build_follow_up_prompt(self, chat_agent):
        """Test follow-up prompt building."""
        from ai.tools import ToolResult

        task = AgentTask(
            task_description="What are BP guidelines?",
            input_data={}
        )

        initial_response = "I'll search for that."

        tool_results = {
            "search": ToolResult(
                success=True,
                output={"text": "BP target is < 130/80 mmHg"}
            )
        }

        prompt = chat_agent._build_follow_up_prompt(task, initial_response, tool_results)

        assert "BP guidelines" in prompt
        assert "130/80" in prompt

    def test_build_follow_up_prompt_with_error(self, chat_agent):
        """Test follow-up prompt with tool error."""
        from ai.tools import ToolResult

        task = AgentTask(
            task_description="Test",
            input_data={}
        )

        tool_results = {
            "search": ToolResult(
                success=False,
                output=None,
                error="Network error"
            )
        }

        prompt = chat_agent._build_follow_up_prompt(task, "Initial", tool_results)

        assert "Error" in prompt
        assert "Network error" in prompt

    def test_build_follow_up_prompt_hypertension(self, chat_agent):
        """Test follow-up prompt for hypertension queries."""
        from ai.tools import ToolResult

        task = AgentTask(
            task_description="What are the hypertension BP targets?",
            input_data={}
        )

        tool_results = {
            "search": ToolResult(success=True, output={})
        }

        prompt = chat_agent._build_follow_up_prompt(task, "Searching...", tool_results)

        # Should include specific guidance for hypertension queries
        assert "BP" in prompt or "blood pressure" in prompt.lower()


class TestAgentExecution:
    """Tests for full agent execution."""

    def test_execute_without_tools(self, chat_agent, mock_ai_caller):
        """Test execution when AI doesn't use tools."""
        mock_ai_caller.default_response = "The answer to your question is..."

        task = AgentTask(
            task_description="Simple question",
            input_data={}
        )

        response = chat_agent.execute(task)

        assert response.success is True
        assert response.metadata["used_tools"] is False
        assert len(response.tool_calls) == 0

    def test_execute_with_tools(self, chat_agent, mock_ai_caller, mock_tool_executor):
        """Test execution when AI uses tools."""
        # First call returns tool call, second returns final answer
        mock_ai_caller.call_history = []

        def mock_call(*args, **kwargs):
            if len(mock_ai_caller.call_history) == 0:
                mock_ai_caller.call_history.append({})
                return """<tool_call>
{"tool_name": "search", "arguments": {"query": "test"}}
</tool_call>"""
            else:
                return "Based on the search results, the answer is..."

        mock_ai_caller.call = mock_call

        task = AgentTask(
            task_description="Search for something",
            input_data={}
        )

        response = chat_agent.execute(task)

        assert response.success is True
        assert response.metadata["used_tools"] is True
        assert len(response.tool_calls) > 0

    def test_execute_handles_exception(self, chat_agent, mock_ai_caller):
        """Test that execution handles exceptions gracefully."""
        mock_ai_caller.call = Mock(side_effect=Exception("API error"))

        task = AgentTask(
            task_description="Test",
            input_data={}
        )

        response = chat_agent.execute(task)

        assert response.success is False
        assert "API error" in response.error


class TestToolRegistryIntegration:
    """Tests for tool registry integration."""

    def test_refresh_available_tools(self, mock_ai_caller, mock_tool_executor):
        """Test refreshing available tools from registry."""
        from ai.agents.models import Tool

        with patch('ai.agents.chat.tool_registry') as mock_registry:
            mock_registry.get_cache_info.return_value = (1, True)
            mock_registry.get_all_definitions.return_value = [
                Tool(name="tool1", description="Test tool 1", parameters=[]),
                Tool(name="tool2", description="Test tool 2", parameters=[])
            ]

            agent = ChatAgent(
                ai_caller=mock_ai_caller,
                tool_executor=mock_tool_executor
            )

            # Initial refresh during init
            assert len(agent.config.available_tools) == 2

            # Update cache version to trigger refresh
            mock_registry.get_cache_info.return_value = (2, True)
            mock_registry.get_all_definitions.return_value = [
                Tool(name="tool1", description="Test tool 1", parameters=[]),
                Tool(name="tool2", description="Test tool 2", parameters=[]),
                Tool(name="tool3", description="Test tool 3", parameters=[])
            ]

            refreshed = agent.refresh_available_tools()

            assert refreshed is True
            assert len(agent.config.available_tools) == 3

    def test_no_refresh_when_cache_valid(self, chat_agent):
        """Test that tools aren't refreshed when cache is valid."""
        with patch.object(chat_agent, 'tool_registry') as mock_registry:
            mock_registry.get_cache_info.return_value = (chat_agent._last_cache_version, True)

            refreshed = chat_agent.refresh_available_tools()

            assert refreshed is False


class TestDebugIntegration:
    """Tests for debug tracking integration."""

    def test_debug_tracking_start_end(self, chat_agent, mock_ai_caller):
        """Test that debug tracking is started and ended."""
        mock_ai_caller.default_response = "Simple response"

        with patch('ai.agents.chat.chat_debugger') as mock_debugger:
            task = AgentTask(
                task_description="Test",
                input_data={}
            )

            chat_agent.execute(task)

            mock_debugger.start_execution.assert_called_once()
            mock_debugger.end_execution.assert_called_once()

    def test_debug_logs_tool_calls(self, chat_agent, mock_ai_caller, mock_tool_executor):
        """Test that tool calls are logged for debugging."""
        mock_ai_caller.call_history = []

        def mock_call(*args, **kwargs):
            if len(mock_ai_caller.call_history) == 0:
                mock_ai_caller.call_history.append({})
                return '<tool_call>{"tool_name": "test", "arguments": {}}</tool_call>'
            return "Result"

        mock_ai_caller.call = mock_call

        with patch('ai.agents.chat.chat_debugger') as mock_debugger:
            task = AgentTask(
                task_description="Test",
                input_data={}
            )

            chat_agent.execute(task)

            # Should log tool call
            mock_debugger.log_tool_call.assert_called()


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_exists(self):
        """Test that default config is properly defined."""
        assert ChatAgent.DEFAULT_CONFIG is not None
        assert ChatAgent.DEFAULT_CONFIG.name == "ChatAgent"

    def test_system_prompt_includes_tool_instructions(self):
        """Test that system prompt includes tool usage instructions."""
        prompt = ChatAgent.DEFAULT_CONFIG.system_prompt.lower()
        assert "tool_call" in prompt or "tool" in prompt

    def test_custom_config_preserves_tool_prompt(self, mock_ai_caller, mock_tool_executor):
        """Test that custom config gets tool-calling instructions added."""
        custom_config = AgentConfig(
            name="CustomChat",
            description="Custom",
            system_prompt="Be helpful",  # Doesn't include tool instructions
            model="gpt-4",
            temperature=0.7
        )

        with patch('ai.agents.chat.tool_registry') as mock_registry:
            mock_registry.get_all_definitions.return_value = []
            mock_registry.get_cache_info.return_value = (1, True)

            agent = ChatAgent(
                config=custom_config,
                ai_caller=mock_ai_caller,
                tool_executor=mock_tool_executor
            )

            # Should have tool instructions added
            assert "tool_call" in agent.config.system_prompt
