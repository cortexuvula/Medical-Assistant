"""
Tests for src/ai/agents/synopsis.py — SynopsisAgent pure-logic methods.
No network, no Tkinter, no real AI calls.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.synopsis import SynopsisAgent
from ai.agents.ai_caller import MockAICaller
from ai.agents.models import AgentConfig, AgentTask, AgentResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(response="Patient presents with atypical chest pain."):
    """Return (agent, mock_caller) pair."""
    caller = MockAICaller(response)
    return SynopsisAgent(ai_caller=caller), caller


def _make_task(soap_note="", context=None, description="Generate synopsis"):
    input_data = {}
    if soap_note:
        input_data["soap_note"] = soap_note
    return AgentTask(
        task_description=description,
        context=context,
        input_data=input_data,
    )


SAMPLE_SOAP = (
    "S: Patient is a 45-year-old male presenting with 2 hours of chest pain.\n"
    "O: BP 140/90, HR 88, T 98.6. EKG: normal sinus rhythm. Troponin: negative.\n"
    "A: Atypical chest pain, likely musculoskeletal.\n"
    "P: Discharge home with ibuprofen, return precautions, follow-up in 1 week."
)


# ---------------------------------------------------------------------------
# TestDefaultConfig
# ---------------------------------------------------------------------------

class TestDefaultConfig:
    """DEFAULT_CONFIG class attribute tests."""

    def test_default_config_name(self):
        assert SynopsisAgent.DEFAULT_CONFIG.name == "SynopsisAgent"

    def test_default_config_temperature(self):
        assert SynopsisAgent.DEFAULT_CONFIG.temperature == 0.3

    def test_default_config_max_tokens(self):
        assert SynopsisAgent.DEFAULT_CONFIG.max_tokens == 300

    def test_default_config_model(self):
        assert SynopsisAgent.DEFAULT_CONFIG.model == "gpt-4"

    def test_default_config_has_system_prompt(self):
        assert SynopsisAgent.DEFAULT_CONFIG.system_prompt != ""

    def test_default_config_description_not_empty(self):
        assert SynopsisAgent.DEFAULT_CONFIG.description != ""


# ---------------------------------------------------------------------------
# TestSynopsisAgentInit
# ---------------------------------------------------------------------------

class TestSynopsisAgentInit:
    """Initialization tests."""

    def test_creates_with_no_args(self):
        agent = SynopsisAgent()
        assert agent is not None

    def test_default_config_applied_when_none_passed(self):
        agent = SynopsisAgent(config=None)
        assert agent.config.name == "SynopsisAgent"

    def test_custom_config_accepted(self):
        config = AgentConfig(
            name="CustomSynopsis",
            description="test",
            system_prompt="test",
            model="gpt-3",
        )
        agent = SynopsisAgent(config=config)
        assert agent.config.name == "CustomSynopsis"

    def test_custom_model_preserved(self):
        config = AgentConfig(
            name="X",
            description="d",
            system_prompt="s",
            model="claude-3",
        )
        agent = SynopsisAgent(config=config)
        assert agent.config.model == "claude-3"

    def test_accepts_mock_ai_caller(self):
        caller = MockAICaller("test")
        agent = SynopsisAgent(ai_caller=caller)
        assert agent is not None

    def test_history_starts_empty(self):
        agent = SynopsisAgent()
        assert agent.history == []

    def test_injected_caller_is_stored(self):
        caller = MockAICaller("hello")
        agent = SynopsisAgent(ai_caller=caller)
        assert agent._ai_caller is caller


# ---------------------------------------------------------------------------
# TestBuildPrompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    """_build_prompt() tests."""

    def test_contains_soap_note_label(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert "SOAP Note:" in prompt

    def test_contains_synopsis_label(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert "Synopsis:" in prompt

    def test_soap_note_content_in_prompt(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert "chest pain" in prompt

    def test_ends_with_synopsis_colon(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert prompt.strip().endswith("Synopsis:")

    def test_context_prepended_when_provided(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP, context="Patient is diabetic")
        # Context should appear before the SOAP note content
        ctx_pos = prompt.find("Patient is diabetic")
        soap_pos = prompt.find("SOAP Note:")
        assert ctx_pos < soap_pos

    def test_context_absent_when_none(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP, context=None)
        assert "Additional Context:" not in prompt

    def test_context_label_present_when_context_given(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP, context="Hypertension history")
        assert "Additional Context:" in prompt

    def test_context_value_in_prompt(self):
        agent, _ = _make_agent()
        ctx = "Patient has known COPD"
        prompt = agent._build_prompt(SAMPLE_SOAP, context=ctx)
        assert ctx in prompt

    def test_empty_context_string_not_prepended(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP, context="")
        assert "Additional Context:" not in prompt

    def test_prompt_is_string(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert isinstance(prompt, str)

    def test_prompt_contains_200_word_instruction(self):
        agent, _ = _make_agent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert "200" in prompt

    def test_multiple_contexts_each_unique(self):
        agent, _ = _make_agent()
        p1 = agent._build_prompt(SAMPLE_SOAP, context="Context A")
        p2 = agent._build_prompt(SAMPLE_SOAP, context="Context B")
        assert "Context A" in p1
        assert "Context B" in p2
        assert "Context B" not in p1

    def test_soap_content_not_duplicated(self):
        agent, _ = _make_agent()
        short_note = "S: fever. O: temp 38. A: viral. P: rest."
        prompt = agent._build_prompt(short_note)
        assert prompt.count("S: fever") == 1


# ---------------------------------------------------------------------------
# TestCleanSynopsis
# ---------------------------------------------------------------------------

class TestCleanSynopsis:
    """_clean_synopsis() tests."""

    def test_strips_leading_whitespace(self):
        agent, _ = _make_agent()
        assert agent._clean_synopsis("  hello") == "hello"

    def test_strips_trailing_whitespace(self):
        agent, _ = _make_agent()
        assert agent._clean_synopsis("hello   ") == "hello"

    def test_strips_both_ends(self):
        agent, _ = _make_agent()
        assert agent._clean_synopsis("  hello world  ") == "hello world"

    def test_strips_newlines(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("\nhello\n")
        assert result == "hello"

    def test_removes_double_asterisk(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("**Important** finding noted")
        assert "**" not in result

    def test_removes_single_asterisk(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("*emphasis* on this")
        assert "*" not in result

    def test_removes_mixed_bold_italic(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("**bold** and *italic* text")
        assert "*" not in result
        assert "**" not in result

    def test_text_preserved_after_markdown_removal(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("**Important** finding")
        assert "Important" in result
        assert "finding" in result

    def test_removes_synopsis_prefix(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("Synopsis: Patient has pain.")
        assert not result.startswith("Synopsis:")

    def test_synopsis_prefix_content_preserved(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("Synopsis: Patient has pain.")
        assert "Patient has pain." in result

    def test_removes_summary_prefix(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("Summary: Acute onset headache.")
        assert not result.startswith("Summary:")

    def test_summary_prefix_content_preserved(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("Summary: Acute onset headache.")
        assert "Acute onset headache." in result

    def test_removes_clinical_synopsis_prefix(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("Clinical Synopsis: HTN uncontrolled.")
        assert not result.startswith("Clinical Synopsis:")

    def test_clinical_synopsis_prefix_content_preserved(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("Clinical Synopsis: HTN uncontrolled.")
        assert "HTN uncontrolled." in result

    def test_no_prefix_text_unchanged(self):
        agent, _ = _make_agent()
        text = "Patient is a 55-year-old female."
        assert agent._clean_synopsis(text) == text

    def test_empty_string_returns_empty(self):
        agent, _ = _make_agent()
        assert agent._clean_synopsis("") == ""

    def test_whitespace_only_returns_empty(self):
        agent, _ = _make_agent()
        assert agent._clean_synopsis("   ") == ""

    def test_prefix_case_sensitive_not_removed(self):
        # Lowercase "synopsis:" should NOT be stripped (implementation matches exact case)
        agent, _ = _make_agent()
        text = "synopsis: lowercase prefix"
        result = agent._clean_synopsis(text)
        # The method uses startswith which is case-sensitive
        assert result == text  # unchanged because prefix doesn't match

    def test_double_bold_multiple_words(self):
        agent, _ = _make_agent()
        result = agent._clean_synopsis("**First** and **second** bold.")
        assert "**" not in result
        assert "First" in result
        assert "second" in result

    def test_returns_string(self):
        agent, _ = _make_agent()
        assert isinstance(agent._clean_synopsis("anything"), str)


# ---------------------------------------------------------------------------
# TestTruncateToWordLimit
# ---------------------------------------------------------------------------

class TestTruncateToWordLimit:
    """_truncate_to_word_limit() tests."""

    def test_short_text_returned_unchanged(self):
        agent, _ = _make_agent()
        text = "Short sentence here."
        assert agent._truncate_to_word_limit(text, 200) == text

    def test_exact_word_limit_not_truncated(self):
        agent, _ = _make_agent()
        text = " ".join(["word"] * 200)
        result = agent._truncate_to_word_limit(text, 200)
        assert result == text

    def test_one_word_over_limit_triggers_truncation(self):
        agent, _ = _make_agent()
        text = " ".join(["word"] * 201)
        result = agent._truncate_to_word_limit(text, 200)
        assert result != text

    def test_long_text_word_count_within_limit(self):
        agent, _ = _make_agent()
        text = " ".join(["word"] * 250)
        result = agent._truncate_to_word_limit(text, 200)
        # Either ends at sentence boundary or ellipsis, but base words <= 200
        assert len(result.split()) <= 201  # +1 for possible "..."

    def test_no_sentence_boundary_gets_ellipsis(self):
        agent, _ = _make_agent()
        text = " ".join(["word"] * 250)  # no punctuation
        result = agent._truncate_to_word_limit(text, 200)
        assert result.endswith("...")

    def test_period_used_as_sentence_boundary(self):
        agent, _ = _make_agent()
        # Place a period just before the limit
        base = " ".join(["word"] * 195) + ". " + " ".join(["word"] * 60)
        result = agent._truncate_to_word_limit(base, 200)
        assert result.endswith(".")

    def test_question_mark_used_as_sentence_boundary(self):
        agent, _ = _make_agent()
        base = " ".join(["word"] * 190) + "? " + " ".join(["word"] * 60)
        result = agent._truncate_to_word_limit(base, 200)
        assert result.endswith("?")

    def test_exclamation_mark_used_as_sentence_boundary(self):
        agent, _ = _make_agent()
        base = " ".join(["word"] * 190) + "! " + " ".join(["word"] * 60)
        result = agent._truncate_to_word_limit(base, 200)
        assert result.endswith("!")

    def test_sentence_boundary_used_over_ellipsis(self):
        agent, _ = _make_agent()
        # Has a period well inside the limit
        base = " ".join(["word"] * 100) + ". " + " ".join(["word"] * 200)
        result = agent._truncate_to_word_limit(base, 150)
        assert not result.endswith("...")

    def test_returns_string(self):
        agent, _ = _make_agent()
        result = agent._truncate_to_word_limit("some text here.", 10)
        assert isinstance(result, str)

    def test_single_word_within_limit(self):
        agent, _ = _make_agent()
        assert agent._truncate_to_word_limit("Hello.", 5) == "Hello."

    def test_empty_string_returned_unchanged(self):
        agent, _ = _make_agent()
        assert agent._truncate_to_word_limit("", 200) == ""

    def test_word_limit_of_one(self):
        agent, _ = _make_agent()
        text = "First. Second. Third."
        result = agent._truncate_to_word_limit(text, 1)
        # Only 1 word allowed; result should be <= 1 word (or ellipsis)
        assert len(result) > 0

    def test_multiple_sentence_endings_picks_last(self):
        agent, _ = _make_agent()
        # Two sentences within word limit, overflow after
        base = "Sentence one. Sentence two. " + " ".join(["extra"] * 200)
        result = agent._truncate_to_word_limit(base, 10)
        # Should end with a sentence terminator
        assert result[-1] in ".?!"

    def test_large_word_limit_behaves_like_no_truncation(self):
        agent, _ = _make_agent()
        text = "Patient is stable. Discharge planned."
        result = agent._truncate_to_word_limit(text, 10000)
        assert result == text


# ---------------------------------------------------------------------------
# TestExecute
# ---------------------------------------------------------------------------

class TestExecute:
    """execute() integration tests with mocked AI."""

    def test_returns_agent_response_type(self):
        agent, _ = _make_agent("Brief synopsis.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert isinstance(result, AgentResponse)

    def test_missing_soap_note_key_returns_failure(self):
        agent, _ = _make_agent()
        task = AgentTask(task_description="Generate synopsis", input_data={})
        result = agent.execute(task)
        assert result.success is False

    def test_missing_soap_note_error_message_set(self):
        agent, _ = _make_agent()
        task = AgentTask(task_description="Generate synopsis", input_data={})
        result = agent.execute(task)
        assert result.error is not None
        assert len(result.error) > 0

    def test_empty_soap_note_returns_failure(self):
        agent, _ = _make_agent()
        result = agent.execute(_make_task(soap_note=""))
        assert result.success is False

    def test_empty_soap_note_error_set(self):
        agent, _ = _make_agent()
        result = agent.execute(_make_task(soap_note=""))
        assert result.error is not None

    def test_valid_soap_note_returns_success(self):
        agent, _ = _make_agent("Patient is a 45-year-old male.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert result.success is True

    def test_valid_soap_note_result_not_empty(self):
        agent, _ = _make_agent("Patient is a 45-year-old male.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert result.result != ""

    def test_metadata_word_count_present(self):
        agent, _ = _make_agent("Synopsis text with four words.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert "word_count" in result.metadata

    def test_metadata_soap_length_present(self):
        agent, _ = _make_agent("Synopsis.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert "soap_length" in result.metadata

    def test_metadata_soap_length_correct(self):
        agent, _ = _make_agent("Synopsis.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert result.metadata["soap_length"] == len(SAMPLE_SOAP)

    def test_metadata_model_used_present(self):
        agent, _ = _make_agent("Synopsis.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert "model_used" in result.metadata

    def test_metadata_model_used_value(self):
        agent, _ = _make_agent("Synopsis.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert result.metadata["model_used"] == "gpt-4"

    def test_long_synopsis_gets_truncated(self):
        long_text = " ".join(["word"] * 210) + "."
        agent, _ = _make_agent(long_text)
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert result.success is True
        assert len(result.result.split()) <= 201

    def test_thoughts_field_set_on_success(self):
        agent, _ = _make_agent("Short synopsis text.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert result.thoughts is not None

    def test_execution_adds_to_history(self):
        agent, _ = _make_agent("Synopsis.")
        agent.execute(_make_task(SAMPLE_SOAP))
        assert len(agent.history) == 1

    def test_multiple_executions_accumulate_history(self):
        agent, _ = _make_agent("Synopsis.")
        agent.execute(_make_task(SAMPLE_SOAP))
        agent.execute(_make_task(SAMPLE_SOAP))
        assert len(agent.history) == 2

    def test_ai_caller_exception_returns_failure(self):
        caller = MagicMock()
        caller.call.side_effect = RuntimeError("API down")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert result.success is False

    def test_ai_caller_exception_error_message_preserved(self):
        caller = MagicMock()
        caller.call.side_effect = RuntimeError("API timeout")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert "API timeout" in result.error

    def test_ai_caller_exception_result_is_empty_string(self):
        caller = MagicMock()
        caller.call.side_effect = Exception("fail")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert result.result == ""

    def test_context_passed_to_prompt(self):
        """execute() passes context from task into _build_prompt."""
        agent, caller = _make_agent("Synopsis.")
        task = _make_task(SAMPLE_SOAP, context="Diabetic patient")
        agent.execute(task)
        # The prompt passed to the AI caller should contain the context
        assert len(caller.call_history) == 1
        prompt_sent = caller.call_history[0]["prompt"]
        assert "Diabetic patient" in prompt_sent

    def test_markdown_cleaned_in_result(self):
        """AI response containing markdown is cleaned before returning."""
        agent, _ = _make_agent("**Important** patient finding noted.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert "**" not in result.result

    def test_synopsis_prefix_stripped_from_result(self):
        agent, _ = _make_agent("Synopsis: Patient has chest pain.")
        result = agent.execute(_make_task(SAMPLE_SOAP))
        assert not result.result.startswith("Synopsis:")

    def test_failure_does_not_add_to_history(self):
        agent, _ = _make_agent()
        agent.execute(_make_task(soap_note=""))  # failure case
        assert len(agent.history) == 0

    def test_mock_caller_call_history_recorded(self):
        agent, caller = _make_agent("Short response.")
        agent.execute(_make_task(SAMPLE_SOAP))
        assert len(caller.call_history) == 1

    def test_model_from_config_passed_to_caller(self):
        agent, caller = _make_agent("Response.")
        agent.execute(_make_task(SAMPLE_SOAP))
        assert caller.call_history[0]["model"] == "gpt-4"

    def test_temperature_from_config_passed_to_caller(self):
        agent, caller = _make_agent("Response.")
        agent.execute(_make_task(SAMPLE_SOAP))
        assert caller.call_history[0]["temperature"] == 0.3
