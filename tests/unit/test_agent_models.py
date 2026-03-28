"""Tests for ai.agents.models — Pydantic models for the agent system."""

import pytest
from ai.agents.models import (
    ToolParameter,
    Tool,
    ToolCall,
    AgentTask,
    AgentResponse,
    AgentConfig,
    AgentType,
    ResponseFormat,
    RetryStrategy,
    RetryConfig,
    AdvancedConfig,
    SubAgentConfig,
    ChainNode,
    ChainNodeType,
    AgentChain,
    PerformanceMetrics,
)


# ── ToolParameter ─────────────────────────────────────────────────────────────

class TestToolParameter:
    def test_required_fields(self):
        p = ToolParameter(name="query", type="string", description="Search query")
        assert p.name == "query"
        assert p.type == "string"
        assert p.description == "Search query"

    def test_default_required_true(self):
        p = ToolParameter(name="x", type="integer", description="An int")
        assert p.required is True

    def test_default_is_none(self):
        p = ToolParameter(name="x", type="string", description="x")
        assert p.default is None

    def test_optional_with_default(self):
        p = ToolParameter(name="limit", type="integer", description="limit", required=False, default=10)
        assert p.required is False
        assert p.default == 10

    def test_all_valid_types(self):
        for t in ("string", "integer", "boolean", "object", "array", "number"):
            p = ToolParameter(name="x", type=t, description="x")
            assert p.type == t


# ── Tool ──────────────────────────────────────────────────────────────────────

class TestTool:
    def test_basic_tool(self):
        tool = Tool(name="search", description="Search the web")
        assert tool.name == "search"
        assert tool.parameters == []

    def test_tool_with_parameters(self):
        param = ToolParameter(name="q", type="string", description="Query")
        tool = Tool(name="search", description="Search", parameters=[param])
        assert len(tool.parameters) == 1
        assert tool.parameters[0].name == "q"


# ── ToolCall ──────────────────────────────────────────────────────────────────

class TestToolCall:
    def test_basic_tool_call(self):
        tc = ToolCall(tool_name="search")
        assert tc.tool_name == "search"
        assert tc.arguments == {}

    def test_tool_call_with_args(self):
        tc = ToolCall(tool_name="search", arguments={"q": "diabetes"})
        assert tc.arguments["q"] == "diabetes"


# ── AgentTask ─────────────────────────────────────────────────────────────────

class TestAgentTask:
    def test_required_description(self):
        task = AgentTask(task_description="Generate a SOAP note")
        assert task.task_description == "Generate a SOAP note"

    def test_default_context_none(self):
        task = AgentTask(task_description="task")
        assert task.context is None

    def test_default_input_data_empty(self):
        task = AgentTask(task_description="task")
        assert task.input_data == {}

    def test_default_max_iterations(self):
        task = AgentTask(task_description="task")
        assert task.max_iterations == 5

    def test_with_all_fields(self):
        task = AgentTask(
            task_description="Extract medications",
            context="Diabetic patient",
            input_data={"clinical_text": "Patient takes metformin"},
            max_iterations=3,
        )
        assert task.context == "Diabetic patient"
        assert task.input_data["clinical_text"] == "Patient takes metformin"
        assert task.max_iterations == 3


# ── AgentResponse ─────────────────────────────────────────────────────────────

class TestAgentResponse:
    def test_basic_success_response(self):
        resp = AgentResponse(result="SOAP note here", success=True)
        assert resp.result == "SOAP note here"
        assert resp.success is True
        assert resp.error is None

    def test_failure_response(self):
        resp = AgentResponse(result="", success=False, error="AI timeout")
        assert not resp.success
        assert resp.error == "AI timeout"

    def test_default_tool_calls_empty(self):
        resp = AgentResponse(result="ok")
        assert resp.tool_calls == []

    def test_default_metadata_empty(self):
        resp = AgentResponse(result="ok")
        assert resp.metadata == {}

    def test_with_metadata(self):
        resp = AgentResponse(result="ok", metadata={"word_count": 50})
        assert resp.metadata["word_count"] == 50

    def test_with_thoughts(self):
        resp = AgentResponse(result="ok", thoughts="I analyzed the text.")
        assert resp.thoughts == "I analyzed the text."


# ── AgentType ─────────────────────────────────────────────────────────────────

class TestAgentType:
    def test_all_types_exist(self):
        types = [t.value for t in AgentType]
        assert "synopsis" in types
        assert "diagnostic" in types
        assert "medication" in types
        assert "referral" in types
        assert "data_extraction" in types
        assert "workflow" in types
        assert "chat" in types
        assert "compliance" in types

    def test_string_enum(self):
        assert AgentType.SYNOPSIS == "synopsis"


# ── RetryConfig ───────────────────────────────────────────────────────────────

class TestRetryConfig:
    def test_defaults(self):
        rc = RetryConfig()
        assert rc.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert rc.max_retries == 3
        assert rc.initial_delay == 1.0
        assert rc.max_delay == 60.0
        assert rc.backoff_factor == 2.0

    def test_max_retries_clamped(self):
        with pytest.raises(Exception):  # Pydantic validation
            RetryConfig(max_retries=11)  # > 10

    def test_initial_delay_min(self):
        with pytest.raises(Exception):
            RetryConfig(initial_delay=0.05)  # < 0.1


# ── AdvancedConfig ────────────────────────────────────────────────────────────

class TestAdvancedConfig:
    def test_defaults(self):
        ac = AdvancedConfig()
        assert ac.response_format == ResponseFormat.PLAIN_TEXT
        assert ac.context_window_size == 5
        assert ac.timeout_seconds == 30.0
        assert ac.enable_caching is True
        assert ac.cache_ttl_seconds == 3600
        assert ac.enable_logging is True
        assert ac.enable_metrics is True

    def test_timeout_bounds(self):
        with pytest.raises(Exception):
            AdvancedConfig(timeout_seconds=4.0)  # < 5.0

    def test_context_window_bounds(self):
        with pytest.raises(Exception):
            AdvancedConfig(context_window_size=21)  # > 20


# ── AgentConfig ───────────────────────────────────────────────────────────────

class TestAgentConfig:
    def _make(self, **kwargs):
        base = {
            "name": "TestAgent",
            "description": "A test agent",
            "system_prompt": "You are helpful.",
        }
        base.update(kwargs)
        return AgentConfig(**base)

    def test_required_fields(self):
        cfg = self._make()
        assert cfg.name == "TestAgent"
        assert cfg.description == "A test agent"
        assert cfg.system_prompt == "You are helpful."

    def test_default_model(self):
        cfg = self._make()
        assert cfg.model == "gpt-4"

    def test_default_temperature(self):
        cfg = self._make()
        assert cfg.temperature == 0.7

    def test_temperature_bounds(self):
        with pytest.raises(Exception):
            self._make(temperature=2.1)  # > 2.0

    def test_custom_model(self):
        cfg = self._make(model="claude-3")
        assert cfg.model == "claude-3"

    def test_default_version(self):
        cfg = self._make()
        assert cfg.version == "1.0.0"

    def test_available_tools_default_empty(self):
        cfg = self._make()
        assert cfg.available_tools == []


# ── SubAgentConfig ────────────────────────────────────────────────────────────

class TestSubAgentConfig:
    def test_required_fields(self):
        sac = SubAgentConfig(
            agent_type=AgentType.SYNOPSIS,
            output_key="synopsis_result"
        )
        assert sac.agent_type == AgentType.SYNOPSIS
        assert sac.output_key == "synopsis_result"

    def test_defaults(self):
        sac = SubAgentConfig(agent_type=AgentType.MEDICATION, output_key="med_result")
        assert sac.enabled is True
        assert sac.priority == 0
        assert sac.required is False
        assert sac.pass_context is True
        assert sac.condition is None

    def test_priority_bounds(self):
        with pytest.raises(Exception):
            SubAgentConfig(agent_type=AgentType.SYNOPSIS, output_key="x", priority=101)


# ── ChainNode ─────────────────────────────────────────────────────────────────

class TestChainNode:
    def test_basic_node(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="SynopsisNode")
        assert node.id == "n1"
        assert node.type == ChainNodeType.AGENT
        assert node.name == "SynopsisNode"

    def test_default_inputs_outputs(self):
        node = ChainNode(id="n1", type=ChainNodeType.CONDITION, name="Check")
        assert node.inputs == []
        assert node.outputs == []

    def test_all_node_types(self):
        for nt in ChainNodeType:
            node = ChainNode(id="n", type=nt, name="node")
            assert node.type == nt


# ── AgentChain ────────────────────────────────────────────────────────────────

class TestAgentChain:
    def test_basic_chain(self):
        chain = AgentChain(
            id="chain1",
            name="SOAP Chain",
            description="Generates SOAP notes",
            start_node_id="n1",
        )
        assert chain.id == "chain1"
        assert chain.nodes == []

    def test_chain_with_nodes(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="Start")
        chain = AgentChain(
            id="c1",
            name="C",
            description="D",
            start_node_id="n1",
            nodes=[node],
        )
        assert len(chain.nodes) == 1


# ── PerformanceMetrics ────────────────────────────────────────────────────────

class TestPerformanceMetrics:
    def test_required_fields(self):
        m = PerformanceMetrics(start_time=0.0, end_time=1.0, duration_seconds=1.0)
        assert m.start_time == 0.0
        assert m.end_time == 1.0
        assert m.duration_seconds == 1.0

    def test_defaults(self):
        m = PerformanceMetrics(start_time=0.0, end_time=1.0, duration_seconds=1.0)
        assert m.tokens_used == 0
        assert m.tokens_input == 0
        assert m.tokens_output == 0
        assert m.cost_estimate == 0.0
        assert m.retry_count == 0
        assert m.cache_hit is False
