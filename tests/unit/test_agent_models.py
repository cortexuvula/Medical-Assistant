"""Comprehensive pytest unit tests for ai.agents.models — pure Pydantic, no I/O."""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from pydantic import ValidationError
from ai.agents.models import (
    ToolParameter, Tool, ToolCall, AgentTask, PerformanceMetrics,
    AgentType, ResponseFormat, RetryStrategy, AgentResponse,
    RetryConfig, AdvancedConfig, SubAgentConfig, AgentConfig,
    ChainNodeType, ChainNode, AgentChain, AgentTemplate,
)


# ── ToolParameter ─────────────────────────────────────────────────────────────

class TestToolParameter:
    def test_required_fields_accepted(self):
        p = ToolParameter(name="query", type="string", description="Search query")
        assert p.name == "query"
        assert p.type == "string"
        assert p.description == "Search query"

    def test_default_required_is_true(self):
        p = ToolParameter(name="x", type="integer", description="An int")
        assert p.required is True

    def test_default_value_is_none(self):
        p = ToolParameter(name="x", type="string", description="x")
        assert p.default is None

    def test_optional_param_with_default(self):
        p = ToolParameter(name="limit", type="integer", description="limit",
                          required=False, default=10)
        assert p.required is False
        assert p.default == 10

    def test_all_six_literal_types(self):
        for t in ("string", "integer", "boolean", "object", "array", "number"):
            p = ToolParameter(name="x", type=t, description="x")
            assert p.type == t

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            ToolParameter(name="x", type="float", description="x")

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ToolParameter(type="string", description="desc")

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            ToolParameter(name="x", type="string")

    def test_boolean_default(self):
        p = ToolParameter(name="flag", type="boolean", description="flag",
                          required=False, default=False)
        assert p.default is False

    def test_object_default(self):
        p = ToolParameter(name="opts", type="object", description="opts",
                          required=False, default={"key": "val"})
        assert p.default == {"key": "val"}


# ── Tool ──────────────────────────────────────────────────────────────────────

class TestTool:
    def test_minimal_tool(self):
        tool = Tool(name="search", description="Search the web")
        assert tool.name == "search"
        assert tool.description == "Search the web"

    def test_default_parameters_empty_list(self):
        tool = Tool(name="noop", description="Does nothing")
        assert tool.parameters == []

    def test_tool_with_single_parameter(self):
        param = ToolParameter(name="q", type="string", description="Query")
        tool = Tool(name="search", description="Search", parameters=[param])
        assert len(tool.parameters) == 1
        assert tool.parameters[0].name == "q"

    def test_tool_with_multiple_parameters(self):
        p1 = ToolParameter(name="q", type="string", description="Query")
        p2 = ToolParameter(name="limit", type="integer", description="Limit",
                           required=False, default=10)
        tool = Tool(name="search", description="Search", parameters=[p1, p2])
        assert len(tool.parameters) == 2

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            Tool(description="A tool")

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            Tool(name="tool")


# ── ToolCall ──────────────────────────────────────────────────────────────────

class TestToolCall:
    def test_minimal_tool_call(self):
        tc = ToolCall(tool_name="search")
        assert tc.tool_name == "search"
        assert tc.arguments == {}

    def test_tool_call_with_arguments(self):
        tc = ToolCall(tool_name="search", arguments={"q": "diabetes", "limit": 5})
        assert tc.arguments["q"] == "diabetes"
        assert tc.arguments["limit"] == 5

    def test_missing_tool_name_raises(self):
        with pytest.raises(ValidationError):
            ToolCall(arguments={"q": "x"})

    def test_arguments_accepts_nested_dict(self):
        tc = ToolCall(tool_name="analyze",
                      arguments={"options": {"verbose": True, "format": "json"}})
        assert tc.arguments["options"]["verbose"] is True


# ── AgentTask ─────────────────────────────────────────────────────────────────

class TestAgentTask:
    def test_required_task_description(self):
        task = AgentTask(task_description="Generate a SOAP note")
        assert task.task_description == "Generate a SOAP note"

    def test_default_context_is_none(self):
        task = AgentTask(task_description="task")
        assert task.context is None

    def test_default_input_data_is_empty_dict(self):
        task = AgentTask(task_description="task")
        assert task.input_data == {}

    def test_default_max_iterations_is_five(self):
        task = AgentTask(task_description="task")
        assert task.max_iterations == 5

    def test_all_fields_explicitly_set(self):
        task = AgentTask(
            task_description="Extract medications",
            context="Diabetic patient",
            input_data={"clinical_text": "Patient takes metformin"},
            max_iterations=3,
        )
        assert task.context == "Diabetic patient"
        assert task.input_data["clinical_text"] == "Patient takes metformin"
        assert task.max_iterations == 3

    def test_missing_task_description_raises(self):
        with pytest.raises(ValidationError):
            AgentTask()

    def test_max_iterations_none_allowed(self):
        task = AgentTask(task_description="task", max_iterations=None)
        assert task.max_iterations is None


# ── PerformanceMetrics ────────────────────────────────────────────────────────

class TestPerformanceMetrics:
    def _make(self, **kwargs):
        base = {"start_time": 0.0, "end_time": 1.5, "duration_seconds": 1.5}
        base.update(kwargs)
        return PerformanceMetrics(**base)

    def test_required_fields_stored(self):
        m = self._make()
        assert m.start_time == 0.0
        assert m.end_time == 1.5
        assert m.duration_seconds == 1.5

    def test_default_tokens_used_zero(self):
        assert self._make().tokens_used == 0

    def test_default_tokens_input_zero(self):
        assert self._make().tokens_input == 0

    def test_default_tokens_output_zero(self):
        assert self._make().tokens_output == 0

    def test_default_cost_estimate_zero(self):
        assert self._make().cost_estimate == 0.0

    def test_default_retry_count_zero(self):
        assert self._make().retry_count == 0

    def test_default_cache_hit_false(self):
        assert self._make().cache_hit is False

    def test_custom_token_values(self):
        m = self._make(tokens_used=500, tokens_input=300, tokens_output=200)
        assert m.tokens_used == 500
        assert m.tokens_input == 300
        assert m.tokens_output == 200

    def test_cache_hit_true(self):
        m = self._make(cache_hit=True)
        assert m.cache_hit is True

    def test_missing_start_time_raises(self):
        with pytest.raises(ValidationError):
            PerformanceMetrics(end_time=1.0, duration_seconds=1.0)


# ── AgentType ─────────────────────────────────────────────────────────────────

class TestAgentType:
    def test_all_eight_members_exist(self):
        values = {t.value for t in AgentType}
        assert values == {
            "synopsis", "diagnostic", "medication", "referral",
            "data_extraction", "workflow", "chat", "compliance"
        }

    def test_is_string_enum(self):
        assert isinstance(AgentType.SYNOPSIS, str)
        assert AgentType.SYNOPSIS == "synopsis"

    def test_each_member_value(self):
        assert AgentType.SYNOPSIS.value == "synopsis"
        assert AgentType.DIAGNOSTIC.value == "diagnostic"
        assert AgentType.MEDICATION.value == "medication"
        assert AgentType.REFERRAL.value == "referral"
        assert AgentType.DATA_EXTRACTION.value == "data_extraction"
        assert AgentType.WORKFLOW.value == "workflow"
        assert AgentType.CHAT.value == "chat"
        assert AgentType.COMPLIANCE.value == "compliance"

    def test_lookup_by_value(self):
        assert AgentType("synopsis") is AgentType.SYNOPSIS
        assert AgentType("compliance") is AgentType.COMPLIANCE


# ── ResponseFormat ────────────────────────────────────────────────────────────

class TestResponseFormat:
    def test_all_four_members(self):
        values = {f.value for f in ResponseFormat}
        assert values == {"plain_text", "json", "markdown", "html"}

    def test_is_string_enum(self):
        assert isinstance(ResponseFormat.PLAIN_TEXT, str)
        assert ResponseFormat.PLAIN_TEXT == "plain_text"

    def test_each_member_value(self):
        assert ResponseFormat.JSON.value == "json"
        assert ResponseFormat.MARKDOWN.value == "markdown"
        assert ResponseFormat.HTML.value == "html"

    def test_lookup_by_value(self):
        assert ResponseFormat("json") is ResponseFormat.JSON


# ── RetryStrategy ─────────────────────────────────────────────────────────────

class TestRetryStrategy:
    def test_all_four_members(self):
        values = {s.value for s in RetryStrategy}
        assert values == {
            "exponential_backoff", "linear_backoff", "fixed_delay", "no_retry"
        }

    def test_is_string_enum(self):
        assert isinstance(RetryStrategy.NO_RETRY, str)
        assert RetryStrategy.NO_RETRY == "no_retry"

    def test_lookup_by_value(self):
        assert RetryStrategy("fixed_delay") is RetryStrategy.FIXED_DELAY


# ── RetryConfig ───────────────────────────────────────────────────────────────

class TestRetryConfig:
    def test_defaults(self):
        rc = RetryConfig()
        assert rc.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert rc.max_retries == 3
        assert rc.initial_delay == 1.0
        assert rc.max_delay == 60.0
        assert rc.backoff_factor == 2.0

    def test_max_retries_zero_allowed(self):
        rc = RetryConfig(max_retries=0)
        assert rc.max_retries == 0

    def test_max_retries_ten_allowed(self):
        rc = RetryConfig(max_retries=10)
        assert rc.max_retries == 10

    def test_max_retries_above_ten_raises(self):
        with pytest.raises(ValidationError):
            RetryConfig(max_retries=11)

    def test_max_retries_negative_raises(self):
        with pytest.raises(ValidationError):
            RetryConfig(max_retries=-1)

    def test_initial_delay_minimum_allowed(self):
        rc = RetryConfig(initial_delay=0.1)
        assert rc.initial_delay == 0.1

    def test_initial_delay_below_minimum_raises(self):
        with pytest.raises(ValidationError):
            RetryConfig(initial_delay=0.09)

    def test_initial_delay_maximum_allowed(self):
        rc = RetryConfig(initial_delay=60.0)
        assert rc.initial_delay == 60.0

    def test_initial_delay_above_maximum_raises(self):
        with pytest.raises(ValidationError):
            RetryConfig(initial_delay=60.1)

    def test_max_delay_minimum_allowed(self):
        rc = RetryConfig(max_delay=1.0)
        assert rc.max_delay == 1.0

    def test_max_delay_above_maximum_raises(self):
        with pytest.raises(ValidationError):
            RetryConfig(max_delay=300.1)

    def test_backoff_factor_minimum_allowed(self):
        rc = RetryConfig(backoff_factor=1.0)
        assert rc.backoff_factor == 1.0

    def test_backoff_factor_above_maximum_raises(self):
        with pytest.raises(ValidationError):
            RetryConfig(backoff_factor=10.1)

    def test_no_retry_strategy(self):
        rc = RetryConfig(strategy=RetryStrategy.NO_RETRY, max_retries=0)
        assert rc.strategy == RetryStrategy.NO_RETRY


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

    def test_default_retry_config_is_nested(self):
        ac = AdvancedConfig()
        assert isinstance(ac.retry_config, RetryConfig)
        assert ac.retry_config.max_retries == 3

    def test_timeout_minimum_allowed(self):
        ac = AdvancedConfig(timeout_seconds=5.0)
        assert ac.timeout_seconds == 5.0

    def test_timeout_below_minimum_raises(self):
        with pytest.raises(ValidationError):
            AdvancedConfig(timeout_seconds=4.9)

    def test_timeout_maximum_allowed(self):
        ac = AdvancedConfig(timeout_seconds=300.0)
        assert ac.timeout_seconds == 300.0

    def test_timeout_above_maximum_raises(self):
        with pytest.raises(ValidationError):
            AdvancedConfig(timeout_seconds=300.1)

    def test_context_window_zero_allowed(self):
        ac = AdvancedConfig(context_window_size=0)
        assert ac.context_window_size == 0

    def test_context_window_twenty_allowed(self):
        ac = AdvancedConfig(context_window_size=20)
        assert ac.context_window_size == 20

    def test_context_window_above_max_raises(self):
        with pytest.raises(ValidationError):
            AdvancedConfig(context_window_size=21)

    def test_response_format_json(self):
        ac = AdvancedConfig(response_format=ResponseFormat.JSON)
        assert ac.response_format == ResponseFormat.JSON

    def test_cache_ttl_zero_allowed(self):
        ac = AdvancedConfig(cache_ttl_seconds=0)
        assert ac.cache_ttl_seconds == 0

    def test_custom_retry_config(self):
        rc = RetryConfig(max_retries=5, strategy=RetryStrategy.LINEAR_BACKOFF)
        ac = AdvancedConfig(retry_config=rc)
        assert ac.retry_config.max_retries == 5
        assert ac.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF


# ── AgentResponse ─────────────────────────────────────────────────────────────

class TestAgentResponse:
    def test_minimal_success_response(self):
        resp = AgentResponse(result="SOAP note")
        assert resp.result == "SOAP note"
        assert resp.success is True

    def test_default_success_true(self):
        resp = AgentResponse(result="ok")
        assert resp.success is True

    def test_default_thoughts_none(self):
        assert AgentResponse(result="ok").thoughts is None

    def test_default_tool_calls_empty(self):
        assert AgentResponse(result="ok").tool_calls == []

    def test_default_error_none(self):
        assert AgentResponse(result="ok").error is None

    def test_default_metadata_empty_dict(self):
        assert AgentResponse(result="ok").metadata == {}

    def test_default_metrics_none(self):
        assert AgentResponse(result="ok").metrics is None

    def test_default_sub_agent_results_empty(self):
        assert AgentResponse(result="ok").sub_agent_results == {}

    def test_failure_response(self):
        resp = AgentResponse(result="", success=False, error="Timeout")
        assert resp.success is False
        assert resp.error == "Timeout"

    def test_with_thoughts(self):
        resp = AgentResponse(result="ok", thoughts="Reasoned step by step.")
        assert resp.thoughts == "Reasoned step by step."

    def test_with_tool_calls(self):
        tc = ToolCall(tool_name="search", arguments={"q": "metformin"})
        resp = AgentResponse(result="ok", tool_calls=[tc])
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].tool_name == "search"

    def test_with_metadata(self):
        resp = AgentResponse(result="ok", metadata={"word_count": 120, "version": 2})
        assert resp.metadata["word_count"] == 120

    def test_with_performance_metrics(self):
        m = PerformanceMetrics(start_time=0.0, end_time=2.0, duration_seconds=2.0,
                               tokens_used=300)
        resp = AgentResponse(result="ok", metrics=m)
        assert resp.metrics.tokens_used == 300

    def test_with_sub_agent_results(self):
        sub = AgentResponse(result="sub result")
        resp = AgentResponse(result="main", sub_agent_results={"synopsis": sub})
        assert resp.sub_agent_results["synopsis"].result == "sub result"

    def test_missing_result_raises(self):
        with pytest.raises(ValidationError):
            AgentResponse()


# ── SubAgentConfig ────────────────────────────────────────────────────────────

class TestSubAgentConfig:
    def test_required_fields(self):
        sac = SubAgentConfig(agent_type=AgentType.SYNOPSIS, output_key="synopsis_out")
        assert sac.agent_type == AgentType.SYNOPSIS
        assert sac.output_key == "synopsis_out"

    def test_default_enabled_true(self):
        sac = SubAgentConfig(agent_type=AgentType.CHAT, output_key="chat_out")
        assert sac.enabled is True

    def test_default_priority_zero(self):
        sac = SubAgentConfig(agent_type=AgentType.CHAT, output_key="out")
        assert sac.priority == 0

    def test_default_required_false(self):
        sac = SubAgentConfig(agent_type=AgentType.CHAT, output_key="out")
        assert sac.required is False

    def test_default_pass_context_true(self):
        sac = SubAgentConfig(agent_type=AgentType.CHAT, output_key="out")
        assert sac.pass_context is True

    def test_default_condition_none(self):
        sac = SubAgentConfig(agent_type=AgentType.CHAT, output_key="out")
        assert sac.condition is None

    def test_priority_zero_allowed(self):
        sac = SubAgentConfig(agent_type=AgentType.CHAT, output_key="out", priority=0)
        assert sac.priority == 0

    def test_priority_hundred_allowed(self):
        sac = SubAgentConfig(agent_type=AgentType.CHAT, output_key="out", priority=100)
        assert sac.priority == 100

    def test_priority_above_hundred_raises(self):
        with pytest.raises(ValidationError):
            SubAgentConfig(agent_type=AgentType.SYNOPSIS, output_key="x", priority=101)

    def test_priority_negative_raises(self):
        with pytest.raises(ValidationError):
            SubAgentConfig(agent_type=AgentType.SYNOPSIS, output_key="x", priority=-1)

    def test_missing_agent_type_raises(self):
        with pytest.raises(ValidationError):
            SubAgentConfig(output_key="out")

    def test_missing_output_key_raises(self):
        with pytest.raises(ValidationError):
            SubAgentConfig(agent_type=AgentType.SYNOPSIS)

    def test_with_condition(self):
        sac = SubAgentConfig(agent_type=AgentType.MEDICATION, output_key="med",
                             condition="has_medications == True")
        assert sac.condition == "has_medications == True"


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

    def test_required_fields_stored(self):
        cfg = self._make()
        assert cfg.name == "TestAgent"
        assert cfg.description == "A test agent"
        assert cfg.system_prompt == "You are helpful."

    def test_default_model_gpt4(self):
        assert self._make().model == "gpt-4"

    def test_default_temperature(self):
        assert self._make().temperature == 0.7

    def test_default_max_tokens_none(self):
        assert self._make().max_tokens is None

    def test_default_provider_none(self):
        assert self._make().provider is None

    def test_default_available_tools_empty(self):
        assert self._make().available_tools == []

    def test_default_sub_agents_empty(self):
        assert self._make().sub_agents == []

    def test_default_tags_empty(self):
        assert self._make().tags == []

    def test_default_version(self):
        assert self._make().version == "1.0.0"

    def test_default_advanced_config_nested(self):
        cfg = self._make()
        assert isinstance(cfg.advanced, AdvancedConfig)

    def test_temperature_zero_allowed(self):
        cfg = self._make(temperature=0.0)
        assert cfg.temperature == 0.0

    def test_temperature_two_allowed(self):
        cfg = self._make(temperature=2.0)
        assert cfg.temperature == 2.0

    def test_temperature_above_two_raises(self):
        with pytest.raises(ValidationError):
            self._make(temperature=2.1)

    def test_temperature_negative_raises(self):
        with pytest.raises(ValidationError):
            self._make(temperature=-0.1)

    def test_custom_model(self):
        cfg = self._make(model="claude-3-opus")
        assert cfg.model == "claude-3-opus"

    def test_with_tools(self):
        tool = Tool(name="lookup", description="Look up info")
        cfg = self._make(available_tools=[tool])
        assert len(cfg.available_tools) == 1

    def test_with_sub_agents(self):
        sac = SubAgentConfig(agent_type=AgentType.MEDICATION, output_key="med")
        cfg = self._make(sub_agents=[sac])
        assert len(cfg.sub_agents) == 1

    def test_with_tags(self):
        cfg = self._make(tags=["clinical", "soap"])
        assert "clinical" in cfg.tags

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            AgentConfig(description="d", system_prompt="sp")

    def test_missing_system_prompt_raises(self):
        with pytest.raises(ValidationError):
            AgentConfig(name="n", description="d")


# ── ChainNodeType ─────────────────────────────────────────────────────────────

class TestChainNodeType:
    def test_all_six_members(self):
        values = {t.value for t in ChainNodeType}
        assert values == {
            "agent", "condition", "transformer", "aggregator", "parallel", "loop"
        }

    def test_is_string_enum(self):
        assert isinstance(ChainNodeType.AGENT, str)
        assert ChainNodeType.AGENT == "agent"

    def test_lookup_by_value(self):
        assert ChainNodeType("loop") is ChainNodeType.LOOP
        assert ChainNodeType("parallel") is ChainNodeType.PARALLEL


# ── ChainNode ─────────────────────────────────────────────────────────────────

class TestChainNode:
    def test_required_fields(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="SynopsisNode")
        assert node.id == "n1"
        assert node.type == ChainNodeType.AGENT
        assert node.name == "SynopsisNode"

    def test_default_agent_type_none(self):
        node = ChainNode(id="n1", type=ChainNodeType.CONDITION, name="Check")
        assert node.agent_type is None

    def test_default_config_empty(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="N")
        assert node.config == {}

    def test_default_inputs_empty(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="N")
        assert node.inputs == []

    def test_default_outputs_empty(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="N")
        assert node.outputs == []

    def test_default_position_empty(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="N")
        assert node.position == {}

    def test_all_chain_node_types(self):
        for nt in ChainNodeType:
            node = ChainNode(id="n", type=nt, name="node")
            assert node.type == nt

    def test_with_agent_type(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="N",
                         agent_type=AgentType.DIAGNOSTIC)
        assert node.agent_type == AgentType.DIAGNOSTIC

    def test_with_inputs_outputs(self):
        node = ChainNode(id="n2", type=ChainNodeType.TRANSFORMER, name="T",
                         inputs=["n1"], outputs=["n3"])
        assert node.inputs == ["n1"]
        assert node.outputs == ["n3"]

    def test_with_position(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="N",
                         position={"x": 100.0, "y": 200.0})
        assert node.position["x"] == 100.0

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            ChainNode(type=ChainNodeType.AGENT, name="N")

    def test_missing_type_raises(self):
        with pytest.raises(ValidationError):
            ChainNode(id="n1", name="N")


# ── AgentChain ────────────────────────────────────────────────────────────────

class TestAgentChain:
    def _make(self, **kwargs):
        base = {
            "id": "chain1",
            "name": "SOAP Chain",
            "description": "Generates SOAP notes",
            "start_node_id": "n1",
        }
        base.update(kwargs)
        return AgentChain(**base)

    def test_required_fields_stored(self):
        chain = self._make()
        assert chain.id == "chain1"
        assert chain.name == "SOAP Chain"
        assert chain.start_node_id == "n1"

    def test_default_nodes_empty(self):
        assert self._make().nodes == []

    def test_default_metadata_empty(self):
        assert self._make().metadata == {}

    def test_with_nodes(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="Start")
        chain = self._make(nodes=[node])
        assert len(chain.nodes) == 1
        assert chain.nodes[0].id == "n1"

    def test_with_metadata(self):
        chain = self._make(metadata={"created_by": "admin", "version": 2})
        assert chain.metadata["created_by"] == "admin"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            AgentChain(name="C", description="D", start_node_id="n1")

    def test_missing_start_node_id_raises(self):
        with pytest.raises(ValidationError):
            AgentChain(id="c1", name="C", description="D")


# ── AgentTemplate ─────────────────────────────────────────────────────────────

class TestAgentTemplate:
    def _agent_config(self):
        return AgentConfig(
            name="SynopsisAgent",
            description="Generates synopsis",
            system_prompt="You summarize clinical notes.",
        )

    def _make(self, **kwargs):
        base = {
            "id": "tmpl-001",
            "name": "SOAP Template",
            "description": "Standard SOAP workflow",
            "category": "clinical",
            "agent_configs": {AgentType.SYNOPSIS: self._agent_config()},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        base.update(kwargs)
        return AgentTemplate(**base)

    def test_required_fields_stored(self):
        t = self._make()
        assert t.id == "tmpl-001"
        assert t.name == "SOAP Template"
        assert t.category == "clinical"

    def test_agent_configs_stored_by_agent_type_key(self):
        t = self._make()
        assert AgentType.SYNOPSIS in t.agent_configs
        assert t.agent_configs[AgentType.SYNOPSIS].name == "SynopsisAgent"

    def test_default_chain_none(self):
        assert self._make().chain is None

    def test_default_tags_empty(self):
        assert self._make().tags == []

    def test_default_author_system(self):
        assert self._make().author == "system"

    def test_default_version(self):
        assert self._make().version == "1.0.0"

    def test_created_at_stored(self):
        t = self._make()
        assert t.created_at == "2024-01-01T00:00:00Z"

    def test_updated_at_stored(self):
        t = self._make()
        assert t.updated_at == "2024-01-01T00:00:00Z"

    def test_with_chain(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="Start")
        chain = AgentChain(id="c1", name="C", description="D",
                           start_node_id="n1", nodes=[node])
        t = self._make(chain=chain)
        assert t.chain is not None
        assert t.chain.id == "c1"

    def test_with_multiple_agent_configs(self):
        med_cfg = AgentConfig(
            name="MedAgent",
            description="Handles medications",
            system_prompt="You list medications.",
        )
        t = self._make(agent_configs={
            AgentType.SYNOPSIS: self._agent_config(),
            AgentType.MEDICATION: med_cfg,
        })
        assert len(t.agent_configs) == 2
        assert AgentType.MEDICATION in t.agent_configs

    def test_with_tags(self):
        t = self._make(tags=["soap", "clinical", "v2"])
        assert "soap" in t.tags

    def test_custom_author(self):
        t = self._make(author="dr_smith")
        assert t.author == "dr_smith"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            AgentTemplate(
                name="T", description="D", category="c",
                agent_configs={AgentType.SYNOPSIS: self._agent_config()},
                created_at="2024-01-01", updated_at="2024-01-01",
            )

    def test_missing_created_at_raises(self):
        with pytest.raises(ValidationError):
            AgentTemplate(
                id="t1", name="T", description="D", category="c",
                agent_configs={AgentType.SYNOPSIS: self._agent_config()},
                updated_at="2024-01-01",
            )

    def test_empty_agent_configs_allowed(self):
        t = self._make(agent_configs={})
        assert t.agent_configs == {}


# ── Nested / Integration Tests ────────────────────────────────────────────────

class TestNestedModelConstruction:
    def test_agent_config_with_full_advanced_config(self):
        rc = RetryConfig(strategy=RetryStrategy.FIXED_DELAY, max_retries=2,
                         initial_delay=5.0, max_delay=30.0, backoff_factor=1.0)
        ac = AdvancedConfig(
            response_format=ResponseFormat.MARKDOWN,
            context_window_size=10,
            timeout_seconds=60.0,
            retry_config=rc,
            enable_caching=False,
            cache_ttl_seconds=900,
        )
        cfg = AgentConfig(
            name="FullAgent",
            description="Fully configured agent",
            system_prompt="Be precise.",
            advanced=ac,
        )
        assert cfg.advanced.response_format == ResponseFormat.MARKDOWN
        assert cfg.advanced.retry_config.strategy == RetryStrategy.FIXED_DELAY
        assert cfg.advanced.timeout_seconds == 60.0

    def test_agent_response_with_nested_sub_agent_and_metrics(self):
        m = PerformanceMetrics(start_time=1000.0, end_time=1002.0,
                               duration_seconds=2.0, tokens_used=100, cache_hit=True)
        sub = AgentResponse(result="sub output", metrics=m)
        main = AgentResponse(
            result="main output",
            sub_agent_results={"helper": sub},
            metadata={"provider": "openai"},
        )
        assert main.sub_agent_results["helper"].metrics.cache_hit is True
        assert main.metadata["provider"] == "openai"

    def test_chain_node_with_full_config(self):
        node = ChainNode(
            id="loop-1",
            type=ChainNodeType.LOOP,
            name="RetryLoop",
            agent_type=AgentType.WORKFLOW,
            config={"max_iterations": 3, "exit_condition": "success"},
            inputs=["start"],
            outputs=["end"],
            position={"x": 50.0, "y": 75.0},
        )
        assert node.config["max_iterations"] == 3
        assert node.agent_type == AgentType.WORKFLOW

    def test_tool_with_nested_parameters_in_agent_config(self):
        p1 = ToolParameter(name="patient_id", type="string", description="Patient ID")
        p2 = ToolParameter(name="include_history", type="boolean",
                           description="Include history", required=False, default=True)
        tool = Tool(name="get_patient", description="Fetch patient record",
                    parameters=[p1, p2])
        cfg = AgentConfig(
            name="EHRAgent",
            description="Accesses EHR",
            system_prompt="You query the EHR.",
            available_tools=[tool],
        )
        assert cfg.available_tools[0].parameters[1].default is True

    def test_full_agent_template_round_trip(self):
        node = ChainNode(id="n1", type=ChainNodeType.AGENT, name="Main",
                         agent_type=AgentType.DATA_EXTRACTION)
        chain = AgentChain(id="c1", name="Extraction Chain",
                           description="Extracts data", start_node_id="n1",
                           nodes=[node])
        cfg = AgentConfig(
            name="ExtractAgent",
            description="Data extractor",
            system_prompt="Extract structured data from notes.",
            model="gpt-4o",
            temperature=0.3,
        )
        template = AgentTemplate(
            id="tmpl-extract",
            name="Extraction Template",
            description="Template for data extraction workflows",
            category="extraction",
            agent_configs={AgentType.DATA_EXTRACTION: cfg},
            chain=chain,
            tags=["extraction", "structured"],
            author="team_ai",
            version="2.0.0",
            created_at="2024-06-01T00:00:00Z",
            updated_at="2024-06-15T00:00:00Z",
        )
        assert template.chain.nodes[0].agent_type == AgentType.DATA_EXTRACTION
        assert template.agent_configs[AgentType.DATA_EXTRACTION].model == "gpt-4o"
        assert template.version == "2.0.0"
