"""
Comprehensive unit tests for BaseAgent pure-logic methods.

Tests cover:
- _clean_json_response
- _extract_json_from_text
- _compute_cache_key
- _get_cached_response
- _cache_response
- _prune_cache
- clear_cache
- set_cache_enabled
- add_to_history / clear_history / get_context_from_history
- _validate_task_input
"""

import hashlib
import json
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

# Path setup
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(name="TestAgent"):
    return AgentConfig(
        name=name,
        description="test",
        system_prompt="You are a test agent",
        model="gpt-4",
        temperature=0.7,
    )


class ConcreteAgent(BaseAgent):
    def execute(self, task: AgentTask) -> AgentResponse:
        return AgentResponse(result="ok")


def _make_agent(name="TestAgent"):
    mock_caller = MagicMock()
    return ConcreteAgent(_make_config(name), ai_caller=mock_caller)


def _make_task(description="Test task", input_data=None):
    return AgentTask(
        task_description=description,
        input_data=input_data if input_data is not None else {},
    )


# ===========================================================================
# _clean_json_response
# ===========================================================================

class TestCleanJsonResponse:
    """Tests for BaseAgent._clean_json_response."""

    def test_plain_json_unchanged(self):
        agent = _make_agent()
        raw = '{"a": 1}'
        result = agent._clean_json_response(raw)
        assert json.loads(result) == {"a": 1}

    def test_strips_leading_trailing_whitespace(self):
        agent = _make_agent()
        raw = '   {"a": 1}   '
        result = agent._clean_json_response(raw)
        assert json.loads(result) == {"a": 1}

    def test_strips_json_markdown_wrapper(self):
        agent = _make_agent()
        raw = '```json\n{"key": "value"}\n```'
        result = agent._clean_json_response(raw)
        assert json.loads(result) == {"key": "value"}

    def test_strips_plain_code_block_wrapper(self):
        agent = _make_agent()
        raw = '```\n{"x": 42}\n```'
        result = agent._clean_json_response(raw)
        assert json.loads(result) == {"x": 42}

    def test_extracts_json_from_surrounding_text(self):
        agent = _make_agent()
        raw = 'Here is the result: {"status": "ok"} and that is all.'
        result = agent._clean_json_response(raw)
        assert json.loads(result) == {"status": "ok"}

    def test_nested_json_preserved(self):
        agent = _make_agent()
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        result = agent._clean_json_response(raw)
        parsed = json.loads(result)
        assert parsed["outer"]["inner"] == [1, 2, 3]

    def test_uses_last_closing_brace(self):
        """rfind('}') must pick up the outermost closing brace."""
        agent = _make_agent()
        raw = '{"a": {"b": 1}}'
        result = agent._clean_json_response(raw)
        parsed = json.loads(result)
        assert parsed == {"a": {"b": 1}}

    def test_no_braces_returns_stripped_string(self):
        """When there are no braces the method returns stripped text."""
        agent = _make_agent()
        raw = '   no json here   '
        result = agent._clean_json_response(raw)
        # Should still return something (stripped); no crash expected
        assert isinstance(result, str)

    def test_multiline_json_in_markdown(self):
        agent = _make_agent()
        raw = '```json\n{\n  "medications": ["aspirin"],\n  "count": 1\n}\n```'
        result = agent._clean_json_response(raw)
        parsed = json.loads(result)
        assert parsed["count"] == 1

    def test_returns_string_type(self):
        agent = _make_agent()
        result = agent._clean_json_response('{"a": 1}')
        assert isinstance(result, str)

    def test_empty_json_object(self):
        agent = _make_agent()
        raw = '{}'
        result = agent._clean_json_response(raw)
        assert json.loads(result) == {}

    def test_prefix_text_before_json_block(self):
        agent = _make_agent()
        raw = 'Response:\n```json\n{"val": true}\n```'
        result = agent._clean_json_response(raw)
        assert json.loads(result) == {"val": True}

    def test_json_with_arrays(self):
        agent = _make_agent()
        raw = '{"items": [1, 2, 3], "count": 3}'
        result = agent._clean_json_response(raw)
        parsed = json.loads(result)
        assert parsed["items"] == [1, 2, 3]

    def test_deeply_nested_json(self):
        agent = _make_agent()
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        raw = json.dumps(data)
        result = agent._clean_json_response(raw)
        assert json.loads(result) == data


# ===========================================================================
# _extract_json_from_text
# ===========================================================================

class TestExtractJsonFromText:
    """Tests for BaseAgent._extract_json_from_text."""

    def test_extracts_simple_json(self):
        agent = _make_agent()
        text = 'The result is {"key": "value"} as expected.'
        result = agent._extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extracts_nested_json(self):
        agent = _make_agent()
        text = 'Found: {"patient": {"age": 45, "bp": "120/80"}}'
        result = agent._extract_json_from_text(text)
        assert result == {"patient": {"age": 45, "bp": "120/80"}}

    def test_returns_none_for_plain_text(self):
        agent = _make_agent()
        result = agent._extract_json_from_text("No JSON here at all.")
        assert result is None

    def test_returns_none_for_empty_string(self):
        agent = _make_agent()
        result = agent._extract_json_from_text("")
        assert result is None

    def test_returns_none_for_invalid_json(self):
        agent = _make_agent()
        text = "{ invalid json here }"
        result = agent._extract_json_from_text(text)
        assert result is None

    def test_extracts_first_valid_json(self):
        """When multiple JSON objects are present, the first valid one is returned."""
        agent = _make_agent()
        text = 'First: {"a": 1} and second: {"b": 2}'
        result = agent._extract_json_from_text(text)
        assert result == {"a": 1}

    def test_extracts_json_with_arrays(self):
        agent = _make_agent()
        text = 'Medications: {"drugs": ["aspirin", "lisinopril"], "count": 2}'
        result = agent._extract_json_from_text(text)
        assert result == {"drugs": ["aspirin", "lisinopril"], "count": 2}

    def test_extracts_json_at_start(self):
        agent = _make_agent()
        text = '{"status": "ok"} - done.'
        result = agent._extract_json_from_text(text)
        assert result == {"status": "ok"}

    def test_extracts_json_at_end(self):
        agent = _make_agent()
        text = 'Here you go: {"done": true}'
        result = agent._extract_json_from_text(text)
        assert result == {"done": True}

    def test_returns_dict_type(self):
        agent = _make_agent()
        text = 'Result: {"x": 1}'
        result = agent._extract_json_from_text(text)
        assert isinstance(result, dict)

    def test_unmatched_braces_returns_none(self):
        agent = _make_agent()
        text = "{ this has no closing brace"
        result = agent._extract_json_from_text(text)
        assert result is None

    def test_json_with_null_values(self):
        agent = _make_agent()
        text = 'Data: {"name": null, "age": 30}'
        result = agent._extract_json_from_text(text)
        assert result == {"name": None, "age": 30}

    def test_json_with_bool_values(self):
        agent = _make_agent()
        text = 'Flags: {"active": true, "deleted": false}'
        result = agent._extract_json_from_text(text)
        assert result == {"active": True, "deleted": False}

    def test_deeply_nested_json_extraction(self):
        agent = _make_agent()
        data = {"a": {"b": {"c": [1, 2, 3]}}}
        text = f"Output: {json.dumps(data)}"
        result = agent._extract_json_from_text(text)
        assert result == data


# ===========================================================================
# _compute_cache_key
# ===========================================================================

class TestComputeCacheKey:
    """Tests for BaseAgent._compute_cache_key."""

    def test_returns_string(self):
        agent = _make_agent()
        key = agent._compute_cache_key("prompt")
        assert isinstance(key, str)

    def test_returns_sha256_hex_length(self):
        agent = _make_agent()
        key = agent._compute_cache_key("test prompt")
        assert len(key) == 64

    def test_returns_lowercase_hex(self):
        agent = _make_agent()
        key = agent._compute_cache_key("prompt")
        assert all(c in "0123456789abcdef" for c in key)

    def test_same_inputs_same_key(self):
        agent = _make_agent()
        k1 = agent._compute_cache_key("hello", model="gpt-4", temperature=0.5)
        k2 = agent._compute_cache_key("hello", model="gpt-4", temperature=0.5)
        assert k1 == k2

    def test_different_prompts_different_keys(self):
        agent = _make_agent()
        k1 = agent._compute_cache_key("prompt A")
        k2 = agent._compute_cache_key("prompt B")
        assert k1 != k2

    def test_different_models_different_keys(self):
        agent = _make_agent()
        k1 = agent._compute_cache_key("prompt", model="gpt-4")
        k2 = agent._compute_cache_key("prompt", model="gpt-3.5-turbo")
        assert k1 != k2

    def test_different_temperatures_different_keys(self):
        agent = _make_agent()
        k1 = agent._compute_cache_key("prompt", temperature=0.0)
        k2 = agent._compute_cache_key("prompt", temperature=1.0)
        assert k1 != k2

    def test_different_system_messages_different_keys(self):
        agent = _make_agent()
        k1 = agent._compute_cache_key("prompt", system_message="sys A")
        k2 = agent._compute_cache_key("prompt", system_message="sys B")
        assert k1 != k2

    def test_empty_prompt_produces_key(self):
        agent = _make_agent()
        key = agent._compute_cache_key("")
        assert len(key) == 64

    def test_uses_config_model_by_default(self):
        """Without explicit model kwarg, config.model is used."""
        agent = _make_agent()
        k1 = agent._compute_cache_key("prompt")
        k2 = agent._compute_cache_key("prompt", model=agent.config.model)
        assert k1 == k2

    def test_uses_config_temperature_by_default(self):
        agent = _make_agent()
        k1 = agent._compute_cache_key("prompt")
        k2 = agent._compute_cache_key("prompt", temperature=agent.config.temperature)
        assert k1 == k2

    def test_is_deterministic_across_calls(self):
        agent = _make_agent()
        keys = [agent._compute_cache_key("stable", model="m", temperature=0.3) for _ in range(5)]
        assert len(set(keys)) == 1

    def test_long_system_message_truncated_to_500(self):
        """Two system messages that differ only beyond char 500 produce the same key."""
        agent = _make_agent()
        base = "x" * 500
        k1 = agent._compute_cache_key("p", system_message=base + "AAA")
        k2 = agent._compute_cache_key("p", system_message=base + "BBB")
        assert k1 == k2

    def test_sha256_matches_manual_computation(self):
        agent = _make_agent()
        prompt = "test"
        model = agent.config.model
        temperature = agent.config.temperature
        key_parts = [prompt, str(model), str(temperature), ""]
        key_string = "|".join(key_parts)
        expected = hashlib.sha256(key_string.encode()).hexdigest()
        assert agent._compute_cache_key(prompt) == expected


# ===========================================================================
# _get_cached_response
# ===========================================================================

class TestGetCachedResponse:
    """Tests for BaseAgent._get_cached_response."""

    def test_returns_none_when_cache_empty(self):
        agent = _make_agent()
        assert agent._get_cached_response("missing_key") is None

    def test_returns_cached_value(self):
        agent = _make_agent()
        agent._response_cache["k1"] = ("hello", time.time())
        assert agent._get_cached_response("k1") == "hello"

    def test_returns_none_when_cache_disabled(self):
        agent = _make_agent()
        agent._response_cache["k1"] = ("hello", time.time())
        agent._cache_enabled = False
        assert agent._get_cached_response("k1") is None

    def test_returns_none_when_entry_expired(self):
        agent = _make_agent()
        expired_ts = time.time() - AGENT_CACHE_TTL_SECONDS - 1
        agent._response_cache["k1"] = ("value", expired_ts)
        assert agent._get_cached_response("k1") is None

    def test_removes_expired_entry_from_cache(self):
        agent = _make_agent()
        expired_ts = time.time() - AGENT_CACHE_TTL_SECONDS - 1
        agent._response_cache["k1"] = ("value", expired_ts)
        agent._get_cached_response("k1")
        assert "k1" not in agent._response_cache

    def test_returns_value_just_before_expiry(self):
        agent = _make_agent()
        # Just barely within TTL
        fresh_ts = time.time() - (AGENT_CACHE_TTL_SECONDS - 5)
        agent._response_cache["k1"] = ("fresh", fresh_ts)
        assert agent._get_cached_response("k1") == "fresh"

    def test_missing_key_returns_none_not_error(self):
        agent = _make_agent()
        result = agent._get_cached_response("definitely_not_here")
        assert result is None

    def test_cache_hit_does_not_alter_value(self):
        agent = _make_agent()
        value = '{"complex": [1, 2, 3], "nested": {"a": true}}'
        agent._response_cache["k"] = (value, time.time())
        assert agent._get_cached_response("k") == value

    def test_multiple_keys_independent(self):
        agent = _make_agent()
        agent._response_cache["k1"] = ("v1", time.time())
        agent._response_cache["k2"] = ("v2", time.time())
        assert agent._get_cached_response("k1") == "v1"
        assert agent._get_cached_response("k2") == "v2"

    def test_expired_entry_leaves_other_entries_intact(self):
        agent = _make_agent()
        expired_ts = time.time() - AGENT_CACHE_TTL_SECONDS - 1
        agent._response_cache["expired"] = ("old", expired_ts)
        agent._response_cache["fresh"] = ("new", time.time())
        agent._get_cached_response("expired")
        assert agent._get_cached_response("fresh") == "new"


# ===========================================================================
# _cache_response
# ===========================================================================

class TestCacheResponse:
    """Tests for BaseAgent._cache_response."""

    def test_stores_value_in_cache(self):
        agent = _make_agent()
        agent._cache_response("k1", "response_text")
        assert "k1" in agent._response_cache

    def test_stored_value_is_retrievable(self):
        agent = _make_agent()
        agent._cache_response("k1", "hello")
        val, _ = agent._response_cache["k1"]
        assert val == "hello"

    def test_stores_current_timestamp(self):
        agent = _make_agent()
        before = time.time()
        agent._cache_response("k1", "v")
        after = time.time()
        _, ts = agent._response_cache["k1"]
        assert before <= ts <= after

    def test_no_op_when_cache_disabled(self):
        agent = _make_agent()
        agent._cache_enabled = False
        agent._cache_response("k1", "value")
        assert "k1" not in agent._response_cache

    def test_does_not_store_when_disabled(self):
        agent = _make_agent()
        agent._cache_enabled = False
        agent._cache_response("k1", "v")
        assert len(agent._response_cache) == 0

    def test_triggers_prune_when_cache_at_max(self):
        agent = _make_agent()
        # Fill cache exactly to MAX_CACHE_ENTRIES
        for i in range(MAX_CACHE_ENTRIES):
            agent._response_cache[f"key_{i}"] = (f"val_{i}", time.time())
        with patch.object(agent, "_prune_cache") as mock_prune:
            agent._cache_response("new_key", "new_val")
            mock_prune.assert_called_once()

    def test_no_prune_when_cache_below_max(self):
        agent = _make_agent()
        for i in range(MAX_CACHE_ENTRIES - 1):
            agent._response_cache[f"key_{i}"] = (f"val_{i}", time.time())
        with patch.object(agent, "_prune_cache") as mock_prune:
            agent._cache_response("new_key", "new_val")
            mock_prune.assert_not_called()

    def test_overwrites_existing_key(self):
        agent = _make_agent()
        agent._cache_response("k1", "first")
        agent._cache_response("k1", "second")
        val, _ = agent._response_cache["k1"]
        assert val == "second"

    def test_multiple_entries_stored_independently(self):
        agent = _make_agent()
        agent._cache_response("k1", "v1")
        agent._cache_response("k2", "v2")
        assert agent._response_cache["k1"][0] == "v1"
        assert agent._response_cache["k2"][0] == "v2"


# ===========================================================================
# _prune_cache
# ===========================================================================

class TestPruneCache:
    """Tests for BaseAgent._prune_cache."""

    def test_removes_expired_entries(self):
        agent = _make_agent()
        expired_ts = time.time() - AGENT_CACHE_TTL_SECONDS - 10
        agent._response_cache["expired1"] = ("v", expired_ts)
        agent._response_cache["expired2"] = ("v", expired_ts)
        agent._response_cache["fresh"] = ("v", time.time())
        agent._prune_cache()
        assert "expired1" not in agent._response_cache
        assert "expired2" not in agent._response_cache
        assert "fresh" in agent._response_cache

    def test_does_not_remove_fresh_entries(self):
        agent = _make_agent()
        agent._response_cache["fresh"] = ("v", time.time())
        agent._prune_cache()
        assert "fresh" in agent._response_cache

    def test_removes_oldest_when_still_over_limit(self):
        """After expiry removal, if still >= MAX, oldest by timestamp is removed."""
        agent = _make_agent()
        # Fill with fresh entries; oldest has earliest timestamp
        base_time = time.time()
        for i in range(MAX_CACHE_ENTRIES):
            agent._response_cache[f"key_{i}"] = (f"v_{i}", base_time + i)
        agent._prune_cache()
        assert len(agent._response_cache) < MAX_CACHE_ENTRIES

    def test_empty_cache_does_not_crash(self):
        agent = _make_agent()
        agent._prune_cache()  # Should not raise

    def test_all_expired_cache_is_emptied(self):
        agent = _make_agent()
        old_ts = time.time() - AGENT_CACHE_TTL_SECONDS - 100
        for i in range(10):
            agent._response_cache[f"k{i}"] = ("v", old_ts)
        agent._prune_cache()
        assert len(agent._response_cache) == 0

    def test_cache_size_below_max_after_prune(self):
        agent = _make_agent()
        base_time = time.time()
        for i in range(MAX_CACHE_ENTRIES + 20):
            agent._response_cache[f"key_{i}"] = (f"v", base_time + i)
        agent._prune_cache()
        assert len(agent._response_cache) < MAX_CACHE_ENTRIES

    def test_oldest_key_removed_first(self):
        """The key with the smallest timestamp is removed first."""
        agent = _make_agent()
        base_time = time.time()
        for i in range(MAX_CACHE_ENTRIES):
            agent._response_cache[f"key_{i}"] = ("v", base_time + i)
        agent._prune_cache()
        # key_0 has the smallest timestamp and should be removed
        assert "key_0" not in agent._response_cache


# ===========================================================================
# clear_cache
# ===========================================================================

class TestClearCache:
    """Tests for BaseAgent.clear_cache."""

    def test_empties_cache(self):
        agent = _make_agent()
        agent._cache_response("k1", "v1")
        agent._cache_response("k2", "v2")
        agent.clear_cache()
        assert len(agent._response_cache) == 0

    def test_cache_empty_after_clear(self):
        agent = _make_agent()
        for i in range(10):
            agent._cache_response(f"k{i}", f"v{i}")
        agent.clear_cache()
        assert agent._response_cache == {}

    def test_clear_empty_cache_does_not_raise(self):
        agent = _make_agent()
        agent.clear_cache()  # Should not raise

    def test_cache_usable_after_clear(self):
        agent = _make_agent()
        agent._cache_response("k1", "v1")
        agent.clear_cache()
        agent._cache_response("k2", "v2")
        assert agent._get_cached_response("k2") == "v2"

    def test_clear_does_not_affect_cache_enabled_flag(self):
        agent = _make_agent()
        agent._cache_response("k", "v")
        agent.clear_cache()
        assert agent._cache_enabled is True


# ===========================================================================
# set_cache_enabled
# ===========================================================================

class TestSetCacheEnabled:
    """Tests for BaseAgent.set_cache_enabled."""

    def test_enable_sets_flag_true(self):
        agent = _make_agent()
        agent._cache_enabled = False
        agent.set_cache_enabled(True)
        assert agent._cache_enabled is True

    def test_disable_sets_flag_false(self):
        agent = _make_agent()
        agent.set_cache_enabled(False)
        assert agent._cache_enabled is False

    def test_disabling_clears_cache(self):
        agent = _make_agent()
        agent._cache_response("k1", "v1")
        agent.set_cache_enabled(False)
        assert len(agent._response_cache) == 0

    def test_enabling_does_not_clear_existing_cache(self):
        agent = _make_agent()
        agent._cache_response("k1", "v1")
        agent.set_cache_enabled(True)
        # Already enabled; existing entries should remain
        assert len(agent._response_cache) == 1

    def test_enable_allows_caching(self):
        agent = _make_agent()
        agent.set_cache_enabled(True)
        agent._cache_response("k", "v")
        assert agent._get_cached_response("k") == "v"

    def test_disable_prevents_caching(self):
        agent = _make_agent()
        agent.set_cache_enabled(False)
        agent._cache_response("k", "v")
        assert agent._get_cached_response("k") is None

    def test_re_enabling_allows_caching_again(self):
        agent = _make_agent()
        agent.set_cache_enabled(False)
        agent.set_cache_enabled(True)
        agent._cache_response("k", "v")
        assert agent._get_cached_response("k") == "v"

    def test_disable_twice_idempotent(self):
        agent = _make_agent()
        agent.set_cache_enabled(False)
        agent.set_cache_enabled(False)
        assert agent._cache_enabled is False
        assert len(agent._response_cache) == 0


# ===========================================================================
# add_to_history
# ===========================================================================

class TestAddToHistory:
    """Tests for BaseAgent.add_to_history."""

    def test_appends_entry(self):
        agent = _make_agent()
        task = _make_task()
        resp = AgentResponse(result="r")
        agent.add_to_history(task, resp)
        assert len(agent.history) == 1

    def test_entry_contains_task_and_response(self):
        agent = _make_agent()
        task = _make_task("describe")
        resp = AgentResponse(result="done")
        agent.add_to_history(task, resp)
        assert agent.history[0]["task"] is task
        assert agent.history[0]["response"] is resp

    def test_multiple_entries_in_order(self):
        agent = _make_agent()
        tasks = [_make_task(f"task {i}") for i in range(5)]
        resp = AgentResponse(result="r")
        for t in tasks:
            agent.add_to_history(t, resp)
        for i, entry in enumerate(agent.history):
            assert entry["task"].task_description == f"task {i}"

    def test_prunes_when_exceeds_max(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(MAX_AGENT_HISTORY_SIZE + 10):
            agent.add_to_history(_make_task(f"t{i}"), resp)
        assert len(agent.history) == MAX_AGENT_HISTORY_SIZE

    def test_keeps_most_recent_after_prune(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        total = MAX_AGENT_HISTORY_SIZE + 20
        for i in range(total):
            agent.add_to_history(_make_task(f"task_{i}"), resp)
        # The last entry should be task_{total-1}
        last = agent.history[-1]["task"].task_description
        assert last == f"task_{total - 1}"

    def test_oldest_entries_dropped_on_prune(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(MAX_AGENT_HISTORY_SIZE + 5):
            agent.add_to_history(_make_task(f"task_{i}"), resp)
        # First entry should NOT be task_0
        first = agent.history[0]["task"].task_description
        assert first != "task_0"

    def test_exact_max_size_no_prune(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(MAX_AGENT_HISTORY_SIZE):
            agent.add_to_history(_make_task(f"t{i}"), resp)
        assert len(agent.history) == MAX_AGENT_HISTORY_SIZE

    def test_one_over_max_triggers_prune(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(MAX_AGENT_HISTORY_SIZE + 1):
            agent.add_to_history(_make_task(f"t{i}"), resp)
        assert len(agent.history) == MAX_AGENT_HISTORY_SIZE


# ===========================================================================
# clear_history
# ===========================================================================

class TestClearHistory:
    """Tests for BaseAgent.clear_history."""

    def test_empties_history(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(5):
            agent.add_to_history(_make_task(f"t{i}"), resp)
        agent.clear_history()
        assert len(agent.history) == 0

    def test_clear_empty_history_no_error(self):
        agent = _make_agent()
        agent.clear_history()  # Should not raise

    def test_history_usable_after_clear(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        agent.add_to_history(_make_task("old"), resp)
        agent.clear_history()
        agent.add_to_history(_make_task("new"), resp)
        assert len(agent.history) == 1
        assert agent.history[0]["task"].task_description == "new"


# ===========================================================================
# get_context_from_history
# ===========================================================================

class TestGetContextFromHistory:
    """Tests for BaseAgent.get_context_from_history."""

    def test_returns_empty_string_when_no_history(self):
        agent = _make_agent()
        assert agent.get_context_from_history() == ""

    def test_includes_task_description(self):
        agent = _make_agent()
        agent.add_to_history(
            _make_task("Check vitals"), AgentResponse(result="Normal")
        )
        ctx = agent.get_context_from_history()
        assert "Check vitals" in ctx

    def test_includes_result(self):
        agent = _make_agent()
        agent.add_to_history(
            _make_task("Check vitals"), AgentResponse(result="BP 120/80")
        )
        ctx = agent.get_context_from_history()
        assert "BP 120/80" in ctx

    def test_includes_context_field_when_present(self):
        agent = _make_agent()
        task = AgentTask(
            task_description="Process note",
            context="Extra context here",
            input_data={},
        )
        agent.add_to_history(task, AgentResponse(result="done"))
        ctx = agent.get_context_from_history()
        assert "Extra context here" in ctx

    def test_respects_max_entries_limit(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(10):
            agent.add_to_history(_make_task(f"Task {i}"), resp)
        ctx = agent.get_context_from_history(max_entries=3)
        assert "Task 7" in ctx
        assert "Task 8" in ctx
        assert "Task 9" in ctx

    def test_excludes_entries_beyond_max(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(10):
            agent.add_to_history(_make_task(f"Task {i}"), resp)
        ctx = agent.get_context_from_history(max_entries=3)
        assert "Task 0" not in ctx
        assert "Task 5" not in ctx

    def test_default_max_entries_is_5(self):
        """Default max_entries=5 should include last 5 items."""
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(8):
            agent.add_to_history(_make_task(f"Task {i}"), resp)
        ctx = agent.get_context_from_history()
        assert "Task 3" in ctx  # 8-5=3, so Tasks 3-7 included
        assert "Task 7" in ctx
        assert "Task 2" not in ctx

    def test_returns_string_type(self):
        agent = _make_agent()
        agent.add_to_history(_make_task("t"), AgentResponse(result="r"))
        assert isinstance(agent.get_context_from_history(), str)

    def test_max_entries_larger_than_history(self):
        agent = _make_agent()
        resp = AgentResponse(result="r")
        for i in range(3):
            agent.add_to_history(_make_task(f"Task {i}"), resp)
        ctx = agent.get_context_from_history(max_entries=10)
        for i in range(3):
            assert f"Task {i}" in ctx

    def test_multiple_entries_all_present_within_limit(self):
        agent = _make_agent()
        tasks_and_results = [
            ("Analyze ECG", "Sinus rhythm"),
            ("Check meds", "Aspirin 81mg"),
        ]
        for desc, res in tasks_and_results:
            agent.add_to_history(_make_task(desc), AgentResponse(result=res))
        ctx = agent.get_context_from_history(max_entries=5)
        assert "Analyze ECG" in ctx
        assert "Sinus rhythm" in ctx
        assert "Check meds" in ctx
        assert "Aspirin 81mg" in ctx


# ===========================================================================
# _validate_task_input
# ===========================================================================

class TestValidateTaskInput:
    """Tests for BaseAgent._validate_task_input."""

    def test_valid_task_no_required_fields(self):
        agent = _make_agent()
        task = _make_task("valid task")
        agent._validate_task_input(task)  # Should not raise

    def test_valid_task_with_required_fields_present(self):
        agent = _make_agent()
        task = _make_task("analyze", {"clinical_text": "Patient data"})
        agent._validate_task_input(task, required_fields=["clinical_text"])

    def test_raises_for_non_agent_task(self):
        agent = _make_agent()
        with pytest.raises(ValueError, match="AgentTask instance"):
            agent._validate_task_input({"task": "wrong type"})

    def test_raises_for_string_input(self):
        agent = _make_agent()
        with pytest.raises(ValueError, match="AgentTask instance"):
            agent._validate_task_input("not a task")

    def test_raises_for_none_input(self):
        agent = _make_agent()
        with pytest.raises(ValueError, match="AgentTask instance"):
            agent._validate_task_input(None)

    def test_raises_for_integer_input(self):
        agent = _make_agent()
        with pytest.raises(ValueError, match="AgentTask instance"):
            agent._validate_task_input(42)

    def test_raises_for_non_dict_input_data(self):
        """Uses Mock with AgentTask spec to simulate non-dict input_data."""
        agent = _make_agent()
        mock_task = Mock(spec=AgentTask)
        mock_task.input_data = "not a dict"
        mock_task.task_description = "valid description"
        with pytest.raises(ValueError, match="dictionary"):
            agent._validate_task_input(mock_task)

    def test_raises_for_list_input_data(self):
        agent = _make_agent()
        mock_task = Mock(spec=AgentTask)
        mock_task.input_data = [1, 2, 3]
        mock_task.task_description = "valid description"
        with pytest.raises(ValueError, match="dictionary"):
            agent._validate_task_input(mock_task)

    def test_raises_for_empty_task_description(self):
        agent = _make_agent()
        task = AgentTask(task_description="", input_data={})
        with pytest.raises(ValueError, match="empty"):
            agent._validate_task_input(task)

    def test_raises_for_whitespace_only_description(self):
        agent = _make_agent()
        task = AgentTask(task_description="   \t\n  ", input_data={})
        with pytest.raises(ValueError, match="empty"):
            agent._validate_task_input(task)

    def test_raises_for_missing_required_field(self):
        agent = _make_agent()
        task = _make_task("task", {"other_field": "value"})
        with pytest.raises(ValueError, match="Missing required fields"):
            agent._validate_task_input(task, required_fields=["clinical_text"])

    def test_raises_listing_all_missing_fields(self):
        agent = _make_agent()
        task = _make_task("task", {})
        with pytest.raises(ValueError, match="Missing required fields"):
            agent._validate_task_input(task, required_fields=["field_a", "field_b"])

    def test_does_not_raise_when_all_required_fields_present(self):
        agent = _make_agent()
        task = _make_task("task", {"a": "1", "b": "2", "c": "3"})
        agent._validate_task_input(task, required_fields=["a", "b", "c"])

    def test_empty_required_field_value_logs_warning_not_raise(self):
        agent = _make_agent()
        task = _make_task("task", {"clinical_text": ""})
        with patch("ai.agents.base.logger") as mock_logger:
            agent._validate_task_input(task, required_fields=["clinical_text"])
            assert mock_logger.warning.called

    def test_required_fields_none_skips_check(self):
        agent = _make_agent()
        task = _make_task("valid task")
        agent._validate_task_input(task, required_fields=None)

    def test_required_fields_empty_list_skips_check(self):
        agent = _make_agent()
        task = _make_task("valid task")
        agent._validate_task_input(task, required_fields=[])

    def test_partial_missing_fields_raises(self):
        agent = _make_agent()
        task = _make_task("task", {"field_a": "present"})
        with pytest.raises(ValueError, match="Missing required fields"):
            agent._validate_task_input(task, required_fields=["field_a", "field_b"])

    def test_extra_fields_in_input_data_allowed(self):
        agent = _make_agent()
        task = _make_task("task", {"required": "v", "extra": "x", "more": "y"})
        agent._validate_task_input(task, required_fields=["required"])

    def test_error_message_mentions_type_name_for_wrong_type(self):
        agent = _make_agent()
        with pytest.raises(ValueError) as exc_info:
            agent._validate_task_input({"dict": "input"})
        assert "dict" in str(exc_info.value).lower()


# ===========================================================================
# Constants sanity checks
# ===========================================================================

class TestConstants:
    """Verify constants are exported with correct values."""

    def test_max_agent_prompt_length(self):
        assert MAX_AGENT_PROMPT_LENGTH == 50000

    def test_max_system_message_length(self):
        assert MAX_SYSTEM_MESSAGE_LENGTH == 10000

    def test_max_agent_history_size(self):
        assert MAX_AGENT_HISTORY_SIZE == 100

    def test_agent_cache_ttl_seconds(self):
        assert AGENT_CACHE_TTL_SECONDS == 300

    def test_max_cache_entries(self):
        assert MAX_CACHE_ENTRIES == 50
