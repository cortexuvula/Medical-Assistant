"""
Unit tests for BaseAgent core methods.

Tests cover:
- Task input validation
- Input sanitization
- Cache key computation
- Response caching with TTL
- History management and pruning
- Structured JSON response parsing
"""

import json
import time
import hashlib
import pytest
from unittest.mock import Mock, patch, MagicMock

from ai.agents.base import (
    BaseAgent,
    MAX_AGENT_PROMPT_LENGTH,
    MAX_SYSTEM_MESSAGE_LENGTH,
    MAX_AGENT_HISTORY_SIZE,
    AGENT_CACHE_TTL_SECONDS,
    MAX_CACHE_ENTRIES,
)
from ai.agents.models import AgentConfig, AgentTask, AgentResponse
from ai.agents.ai_caller import MockAICaller


class ConcreteTestAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    def execute(self, task: AgentTask) -> AgentResponse:
        """Simple execute implementation for testing."""
        self._validate_task_input(task)
        return AgentResponse(
            result=f"Processed: {task.task_description}",
            success=True
        )


@pytest.fixture
def test_config():
    """Create a test agent config."""
    return AgentConfig(
        name="TestAgent",
        description="Test agent",
        system_prompt="You are a test assistant.",
        model="gpt-4",
        temperature=0.7
    )


@pytest.fixture
def test_agent(test_config, mock_ai_caller):
    """Create a test agent with mock AI caller."""
    return ConcreteTestAgent(test_config, ai_caller=mock_ai_caller)


class TestValidateTaskInput:
    """Tests for _validate_task_input method."""

    def test_valid_task(self, test_agent, sample_agent_task):
        """Test validation passes for valid task."""
        # Should not raise
        test_agent._validate_task_input(sample_agent_task)

    def test_invalid_task_type(self, test_agent):
        """Test validation fails for non-AgentTask input."""
        with pytest.raises(ValueError, match="must be an AgentTask instance"):
            test_agent._validate_task_input({"task": "invalid"})

    def test_invalid_input_data_type(self, test_agent):
        """Test validation fails when input_data is not a dict."""
        task = Mock(spec=AgentTask)
        task.input_data = "not a dict"
        task.task_description = "test"

        with pytest.raises(ValueError, match="must be a dictionary"):
            test_agent._validate_task_input(task)

    def test_empty_task_description(self, test_agent):
        """Test validation fails for empty task description."""
        task = AgentTask(
            task_description="",
            input_data={"key": "value"}
        )

        with pytest.raises(ValueError, match="cannot be empty"):
            test_agent._validate_task_input(task)

    def test_whitespace_only_task_description(self, test_agent):
        """Test validation fails for whitespace-only description."""
        task = AgentTask(
            task_description="   \n\t  ",
            input_data={"key": "value"}
        )

        with pytest.raises(ValueError, match="cannot be empty"):
            test_agent._validate_task_input(task)

    def test_missing_required_fields(self, test_agent):
        """Test validation fails when required fields are missing."""
        task = AgentTask(
            task_description="Test task",
            input_data={"key": "value"}
        )

        with pytest.raises(ValueError, match="Missing required fields"):
            test_agent._validate_task_input(task, required_fields=["clinical_text", "patient_id"])

    def test_required_fields_present(self, test_agent):
        """Test validation passes when required fields are present."""
        task = AgentTask(
            task_description="Test task",
            input_data={"clinical_text": "Patient data", "patient_id": "123"}
        )

        # Should not raise
        test_agent._validate_task_input(task, required_fields=["clinical_text", "patient_id"])

    def test_empty_required_field_logs_warning(self, test_agent):
        """Test that empty required fields log a warning but don't fail."""
        task = AgentTask(
            task_description="Test task",
            input_data={"clinical_text": "", "patient_id": "123"}
        )

        # Should not raise, but logs warning
        with patch('ai.agents.base.logger') as mock_logger:
            test_agent._validate_task_input(task, required_fields=["clinical_text"])
            # Check that warning was logged for empty field
            assert mock_logger.warning.called


class TestValidateAndSanitizeInput:
    """Tests for _validate_and_sanitize_input method."""

    def test_valid_prompt(self, test_agent):
        """Test valid prompt passes through."""
        prompt, system = test_agent._validate_and_sanitize_input(
            "Tell me about hypertension",
            "You are a medical assistant"
        )
        assert "hypertension" in prompt
        assert "medical assistant" in system

    def test_empty_prompt_raises(self, test_agent):
        """Test empty prompt raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            test_agent._validate_and_sanitize_input("", "system message")

    def test_whitespace_prompt_raises(self, test_agent):
        """Test whitespace-only prompt raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            test_agent._validate_and_sanitize_input("   \n  ", "system message")

    def test_long_prompt_truncation(self, test_agent):
        """Test that very long prompts are truncated."""
        long_prompt = "x" * (MAX_AGENT_PROMPT_LENGTH + 1000)

        with patch('ai.agents.base.logger') as mock_logger:
            prompt, _ = test_agent._validate_and_sanitize_input(long_prompt, "system")
            # The prompt goes through two truncation steps:
            # 1. Base agent truncates at MAX_AGENT_PROMPT_LENGTH (50000) and adds message
            # 2. sanitize_prompt truncates at MAX_PROMPT_LENGTH (10000) and adds "..."
            # So we check that:
            # - The prompt is significantly shorter than the input
            # - A warning was logged about truncation
            assert len(prompt) < len(long_prompt)
            assert len(prompt) <= 10100  # 10000 + small margin for truncation markers
            assert mock_logger.warning.called

    def test_long_system_message_truncation(self, test_agent):
        """Test that very long system messages are truncated."""
        long_system = "x" * (MAX_SYSTEM_MESSAGE_LENGTH + 500)

        with patch('ai.agents.base.logger') as mock_logger:
            _, system = test_agent._validate_and_sanitize_input("valid prompt", long_system)
            assert len(system) <= MAX_SYSTEM_MESSAGE_LENGTH
            assert mock_logger.warning.called

    def test_empty_system_message_allowed(self, test_agent):
        """Test that empty system message is allowed."""
        prompt, system = test_agent._validate_and_sanitize_input("valid prompt", "")
        assert system == ""

    def test_none_system_message_converted(self, test_agent):
        """Test that None system message is converted to empty string."""
        prompt, system = test_agent._validate_and_sanitize_input("valid prompt", None)
        assert system == ""


class TestCacheKeyComputation:
    """Tests for _compute_cache_key method."""

    def test_same_inputs_same_key(self, test_agent):
        """Test that same inputs produce same cache key."""
        key1 = test_agent._compute_cache_key("prompt", model="gpt-4", temperature=0.7)
        key2 = test_agent._compute_cache_key("prompt", model="gpt-4", temperature=0.7)
        assert key1 == key2

    def test_different_prompts_different_keys(self, test_agent):
        """Test that different prompts produce different cache keys."""
        key1 = test_agent._compute_cache_key("prompt1")
        key2 = test_agent._compute_cache_key("prompt2")
        assert key1 != key2

    def test_different_models_different_keys(self, test_agent):
        """Test that different models produce different cache keys."""
        key1 = test_agent._compute_cache_key("prompt", model="gpt-4")
        key2 = test_agent._compute_cache_key("prompt", model="gpt-3.5-turbo")
        assert key1 != key2

    def test_different_temperatures_different_keys(self, test_agent):
        """Test that different temperatures produce different cache keys."""
        key1 = test_agent._compute_cache_key("prompt", temperature=0.5)
        key2 = test_agent._compute_cache_key("prompt", temperature=0.9)
        assert key1 != key2

    def test_cache_key_is_sha256(self, test_agent):
        """Test that cache key is a valid SHA256 hash."""
        key = test_agent._compute_cache_key("prompt")
        # SHA256 produces 64 hex characters
        assert len(key) == 64
        assert all(c in '0123456789abcdef' for c in key)


class TestResponseCaching:
    """Tests for response caching methods."""

    def test_cache_and_retrieve(self, test_agent):
        """Test basic cache set and get."""
        key = "test_key"
        response = "cached response"

        test_agent._cache_response(key, response)
        cached = test_agent._get_cached_response(key)

        assert cached == response

    def test_cache_miss(self, test_agent):
        """Test cache miss returns None."""
        result = test_agent._get_cached_response("nonexistent_key")
        assert result is None

    def test_cache_ttl_expiration(self, test_agent):
        """Test that cached responses expire after TTL."""
        key = "test_key"
        response = "cached response"

        test_agent._cache_response(key, response)

        # Manually expire the cache entry
        test_agent._response_cache[key] = (response, time.time() - AGENT_CACHE_TTL_SECONDS - 1)

        cached = test_agent._get_cached_response(key)
        assert cached is None
        assert key not in test_agent._response_cache  # Should be removed

    def test_cache_disabled(self, test_agent):
        """Test caching when disabled."""
        test_agent._cache_enabled = False

        test_agent._cache_response("key", "value")
        result = test_agent._get_cached_response("key")

        assert result is None
        assert len(test_agent._response_cache) == 0

    def test_cache_eviction_on_max_entries(self, test_agent):
        """Test that old entries are evicted when cache is full."""
        # Fill cache to max
        for i in range(MAX_CACHE_ENTRIES + 10):
            test_agent._cache_response(f"key_{i}", f"value_{i}")

        assert len(test_agent._response_cache) <= MAX_CACHE_ENTRIES

    def test_clear_cache(self, test_agent):
        """Test clearing the cache."""
        test_agent._cache_response("key1", "value1")
        test_agent._cache_response("key2", "value2")

        test_agent.clear_cache()

        assert len(test_agent._response_cache) == 0

    def test_set_cache_enabled(self, test_agent):
        """Test enabling/disabling cache."""
        test_agent._cache_response("key", "value")
        assert len(test_agent._response_cache) == 1

        test_agent.set_cache_enabled(False)
        assert test_agent._cache_enabled is False
        assert len(test_agent._response_cache) == 0

        test_agent.set_cache_enabled(True)
        assert test_agent._cache_enabled is True

    def test_call_ai_cached(self, test_agent, mock_ai_caller):
        """Test _call_ai_cached uses cache correctly."""
        mock_ai_caller.default_response = "AI response"

        # First call - should call AI
        result1 = test_agent._call_ai_cached("test prompt")
        assert result1 == "AI response"
        assert len(mock_ai_caller.call_history) == 1

        # Second call - should use cache
        result2 = test_agent._call_ai_cached("test prompt")
        assert result2 == "AI response"
        assert len(mock_ai_caller.call_history) == 1  # No additional call


class TestHistoryManagement:
    """Tests for history management methods."""

    def test_add_to_history(self, test_agent, sample_agent_task):
        """Test adding task/response to history."""
        response = AgentResponse(result="test result", success=True)

        test_agent.add_to_history(sample_agent_task, response)

        assert len(test_agent.history) == 1
        assert test_agent.history[0]['task'] == sample_agent_task
        assert test_agent.history[0]['response'] == response

    def test_history_pruning(self, test_agent, sample_agent_task):
        """Test that history is pruned when exceeding max size."""
        response = AgentResponse(result="test", success=True)

        # Add more than max entries
        for i in range(MAX_AGENT_HISTORY_SIZE + 20):
            task = AgentTask(
                task_description=f"Task {i}",
                input_data={"index": i}
            )
            test_agent.add_to_history(task, response)

        assert len(test_agent.history) == MAX_AGENT_HISTORY_SIZE
        # Most recent should be kept
        assert test_agent.history[-1]['task'].input_data['index'] == MAX_AGENT_HISTORY_SIZE + 19

    def test_clear_history(self, test_agent, sample_agent_task):
        """Test clearing history."""
        response = AgentResponse(result="test", success=True)
        test_agent.add_to_history(sample_agent_task, response)

        test_agent.clear_history()

        assert len(test_agent.history) == 0

    def test_get_context_from_history_empty(self, test_agent):
        """Test getting context from empty history."""
        context = test_agent.get_context_from_history()
        assert context == ""

    def test_get_context_from_history(self, test_agent):
        """Test getting context from history."""
        task = AgentTask(
            task_description="Analyze symptoms",
            context="Patient context",
            input_data={}
        )
        response = AgentResponse(result="Analysis result", success=True)

        test_agent.add_to_history(task, response)

        context = test_agent.get_context_from_history()

        assert "Analyze symptoms" in context
        assert "Patient context" in context
        assert "Analysis result" in context

    def test_get_context_from_history_max_entries(self, test_agent):
        """Test that only max_entries are included in context."""
        for i in range(10):
            task = AgentTask(task_description=f"Task {i}", input_data={})
            response = AgentResponse(result=f"Result {i}", success=True)
            test_agent.add_to_history(task, response)

        context = test_agent.get_context_from_history(max_entries=3)

        # Should only contain last 3 entries
        assert "Task 7" in context
        assert "Task 8" in context
        assert "Task 9" in context
        assert "Task 5" not in context


class TestStructuredJSONParsing:
    """Tests for structured JSON response methods."""

    def test_clean_json_response_simple(self, test_agent):
        """Test cleaning simple JSON response."""
        response = '{"key": "value"}'
        cleaned = test_agent._clean_json_response(response)
        assert json.loads(cleaned) == {"key": "value"}

    def test_clean_json_response_with_markdown(self, test_agent):
        """Test cleaning JSON wrapped in markdown."""
        response = '```json\n{"key": "value"}\n```'
        cleaned = test_agent._clean_json_response(response)
        assert json.loads(cleaned) == {"key": "value"}

    def test_clean_json_response_with_surrounding_text(self, test_agent):
        """Test cleaning JSON with surrounding text."""
        response = 'Here is the result: {"key": "value"} hope this helps!'
        cleaned = test_agent._clean_json_response(response)
        assert json.loads(cleaned) == {"key": "value"}

    def test_extract_json_from_text(self, test_agent):
        """Test extracting JSON from mixed text."""
        text = 'The analysis shows {"medications": ["aspirin", "lisinopril"]} based on the data.'
        result = test_agent._extract_json_from_text(text)

        assert result is not None
        assert result == {"medications": ["aspirin", "lisinopril"]}

    def test_extract_json_from_text_nested(self, test_agent):
        """Test extracting nested JSON from text."""
        text = 'Result: {"patient": {"name": "John", "vitals": {"bp": "120/80"}}}'
        result = test_agent._extract_json_from_text(text)

        assert result is not None
        assert result["patient"]["name"] == "John"
        assert result["patient"]["vitals"]["bp"] == "120/80"

    def test_extract_json_from_text_no_json(self, test_agent):
        """Test extraction when no valid JSON present."""
        text = 'This is just plain text without any JSON.'
        result = test_agent._extract_json_from_text(text)
        assert result is None

    def test_extract_json_from_text_invalid_json(self, test_agent):
        """Test extraction with malformed JSON."""
        text = '{"key": "value", invalid}'
        result = test_agent._extract_json_from_text(text)
        # Should return None for invalid JSON
        assert result is None

    def test_get_structured_response(self, test_agent, mock_ai_caller):
        """Test getting structured JSON response."""
        mock_ai_caller.default_response = '{"status": "success", "count": 5}'

        schema = {"status": "str", "count": "int"}
        result = test_agent._get_structured_response("test prompt", schema)

        assert result["status"] == "success"
        assert result["count"] == 5

    def test_get_structured_response_with_fallback(self, test_agent, mock_ai_caller):
        """Test structured response with fallback parser."""
        mock_ai_caller.default_response = "Not valid JSON"

        def fallback_parser(text):
            return {"parsed": True, "text": text}

        schema = {"status": "str"}
        result = test_agent._get_structured_response_with_fallback(
            "test prompt",
            schema,
            fallback_parser=fallback_parser
        )

        assert result["parsed"] is True

    def test_get_structured_response_recovery(self, test_agent, mock_ai_caller):
        """Test JSON recovery from mixed response."""
        # Response has valid JSON embedded in text
        mock_ai_caller.default_response = 'Here is the analysis: {"result": "found", "items": [1, 2, 3]} Let me explain...'

        schema = {"result": "str", "items": "list"}
        result = test_agent._get_structured_response("test prompt", schema)

        assert result["result"] == "found"
        assert result["items"] == [1, 2, 3]


class TestCallAI:
    """Tests for _call_ai method."""

    def test_call_ai_basic(self, test_agent, mock_ai_caller):
        """Test basic AI call."""
        mock_ai_caller.default_response = "AI response"

        result = test_agent._call_ai("test prompt")

        assert result == "AI response"
        assert len(mock_ai_caller.call_history) == 1

    def test_call_ai_with_model_override(self, test_agent, mock_ai_caller):
        """Test AI call with model override."""
        test_agent._call_ai("prompt", model="gpt-3.5-turbo")

        call = mock_ai_caller.call_history[-1]
        assert call["model"] == "gpt-3.5-turbo"

    def test_call_ai_with_temperature_override(self, test_agent, mock_ai_caller):
        """Test AI call with temperature override."""
        test_agent._call_ai("prompt", temperature=0.2)

        call = mock_ai_caller.call_history[-1]
        assert call["temperature"] == 0.2

    def test_call_ai_uses_config_defaults(self, test_agent, mock_ai_caller):
        """Test that AI call uses config defaults."""
        test_agent._call_ai("prompt")

        call = mock_ai_caller.call_history[-1]
        assert call["model"] == test_agent.config.model
        assert call["temperature"] == test_agent.config.temperature

    def test_call_ai_with_provider(self, test_config, mock_ai_caller):
        """Test AI call with specific provider."""
        test_config.provider = "anthropic"
        agent = ConcreteTestAgent(test_config, ai_caller=mock_ai_caller)

        agent._call_ai("prompt")

        call = mock_ai_caller.call_history[-1]
        assert call["provider"] == "anthropic"


class TestAgentExecution:
    """Integration tests for agent execution."""

    def test_execute_valid_task(self, test_agent, sample_agent_task):
        """Test executing a valid task."""
        result = test_agent.execute(sample_agent_task)

        assert result.success is True
        assert "Processed:" in result.result

    def test_execute_invalid_task(self, test_agent):
        """Test that execution handles invalid tasks."""
        # This should raise during validation in our concrete implementation
        invalid_task = AgentTask(task_description="", input_data={})

        with pytest.raises(ValueError):
            test_agent.execute(invalid_task)

    def test_ai_caller_property(self, test_agent, mock_ai_caller):
        """Test ai_caller property returns the caller."""
        assert test_agent.ai_caller is mock_ai_caller
