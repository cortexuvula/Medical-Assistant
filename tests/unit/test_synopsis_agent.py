"""Tests for ai.agents.synopsis — SynopsisAgent."""

import pytest
from unittest.mock import MagicMock, patch

from ai.agents.synopsis import SynopsisAgent
from ai.agents.ai_caller import MockAICaller
from ai.agents.models import AgentTask, AgentResponse, AgentConfig


def make_task(soap_note: str = "", context: str = None) -> AgentTask:
    input_data = {}
    if soap_note:
        input_data["soap_note"] = soap_note
    return AgentTask(
        task_description="Generate synopsis",
        context=context,
        input_data=input_data,
    )


SAMPLE_SOAP = """
S: Patient is a 45-year-old male with chest pain for 2 hours.
O: BP 140/90, HR 88, T 98.6. EKG shows normal sinus rhythm. Troponin negative.
A: Atypical chest pain, likely musculoskeletal.
P: Discharge home with ibuprofen, return precautions, follow up in 1 week.
"""


class TestSynopsisAgentInit:
    def test_creates_with_defaults(self):
        agent = SynopsisAgent()
        assert agent is not None

    def test_default_config_name(self):
        agent = SynopsisAgent()
        assert agent.config.name == "SynopsisAgent"

    def test_custom_config_accepted(self):
        config = AgentConfig(name="CustomSynopsis", description="test", system_prompt="test", model="gpt-3")
        agent = SynopsisAgent(config=config)
        assert agent.config.name == "CustomSynopsis"

    def test_accepts_ai_caller(self):
        caller = MockAICaller("test response")
        agent = SynopsisAgent(ai_caller=caller)
        assert agent is not None


class TestSynopsisExecute:
    def test_returns_agent_response(self):
        caller = MockAICaller("Brief clinical summary.")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(make_task(SAMPLE_SOAP))
        assert isinstance(result, AgentResponse)

    def test_empty_soap_note_returns_failure(self):
        caller = MockAICaller("Should not be called")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(make_task(""))
        assert not result.success
        assert result.error is not None

    def test_missing_soap_note_key_returns_failure(self):
        caller = MockAICaller("Should not be called")
        agent = SynopsisAgent(ai_caller=caller)
        # input_data has no 'soap_note' key
        task = AgentTask(task_description="Generate synopsis", input_data={})
        result = agent.execute(task)
        assert not result.success

    def test_successful_execution_returns_synopsis(self):
        caller = MockAICaller("Patient is a 45-year-old male with atypical chest pain.")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(make_task(SAMPLE_SOAP))
        assert result.success
        assert result.result != ""

    def test_metadata_includes_word_count(self):
        caller = MockAICaller("Short synopsis with five words here.")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(make_task(SAMPLE_SOAP))
        assert result.success
        assert "word_count" in result.metadata

    def test_metadata_includes_soap_length(self):
        caller = MockAICaller("Synopsis text.")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(make_task(SAMPLE_SOAP))
        assert "soap_length" in result.metadata
        assert result.metadata["soap_length"] == len(SAMPLE_SOAP)

    def test_long_synopsis_gets_truncated(self):
        # 210-word response should be truncated to 200
        long_response = " ".join(["word"] * 210) + "."
        caller = MockAICaller(long_response)
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(make_task(SAMPLE_SOAP))
        assert result.success
        word_count = len(result.result.split())
        assert word_count <= 201  # Allow +1 for ellipsis word

    def test_exception_returns_failure(self):
        caller = MagicMock()
        caller.call.side_effect = Exception("AI timeout")
        agent = SynopsisAgent(ai_caller=caller)
        result = agent.execute(make_task(SAMPLE_SOAP))
        assert not result.success
        assert "AI timeout" in result.error

    def test_execution_adds_to_history(self):
        caller = MockAICaller("Synopsis.")
        agent = SynopsisAgent(ai_caller=caller)
        agent.execute(make_task(SAMPLE_SOAP))
        assert len(agent.history) > 0


class TestBuildPrompt:
    def test_prompt_contains_soap_note(self):
        agent = SynopsisAgent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert "chest pain" in prompt

    def test_prompt_contains_synopsis_request(self):
        agent = SynopsisAgent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert "synopsis" in prompt.lower()

    def test_prompt_with_context_includes_context(self):
        agent = SynopsisAgent()
        prompt = agent._build_prompt(SAMPLE_SOAP, context="Patient is diabetic")
        assert "Patient is diabetic" in prompt

    def test_prompt_without_context_has_no_context_label(self):
        agent = SynopsisAgent()
        prompt = agent._build_prompt(SAMPLE_SOAP, context=None)
        assert "Additional Context:" not in prompt

    def test_prompt_ends_with_synopsis_label(self):
        agent = SynopsisAgent()
        prompt = agent._build_prompt(SAMPLE_SOAP)
        assert prompt.strip().endswith("Synopsis:")


class TestCleanSynopsis:
    def test_strips_whitespace(self):
        agent = SynopsisAgent()
        result = agent._clean_synopsis("  hello world  ")
        assert result == "hello world"

    def test_removes_bold_markdown(self):
        agent = SynopsisAgent()
        result = agent._clean_synopsis("**Important** finding")
        assert "**" not in result

    def test_removes_italic_markdown(self):
        agent = SynopsisAgent()
        result = agent._clean_synopsis("*italics* here")
        assert "*" not in result

    def test_removes_synopsis_prefix(self):
        agent = SynopsisAgent()
        result = agent._clean_synopsis("Synopsis: Patient has chest pain.")
        assert not result.startswith("Synopsis:")

    def test_removes_summary_prefix(self):
        agent = SynopsisAgent()
        result = agent._clean_synopsis("Summary: Patient has chest pain.")
        assert not result.startswith("Summary:")

    def test_removes_clinical_synopsis_prefix(self):
        agent = SynopsisAgent()
        result = agent._clean_synopsis("Clinical Synopsis: Patient has chest pain.")
        assert not result.startswith("Clinical Synopsis:")

    def test_no_prefix_returns_unchanged(self):
        agent = SynopsisAgent()
        text = "Patient is a 45-year-old male."
        result = agent._clean_synopsis(text)
        assert result == text


class TestTruncateToWordLimit:
    def test_short_text_not_truncated(self):
        agent = SynopsisAgent()
        text = "Short text with five words."
        result = agent._truncate_to_word_limit(text, 200)
        assert result == text

    def test_long_text_truncated(self):
        agent = SynopsisAgent()
        text = " ".join(["word"] * 250)
        result = agent._truncate_to_word_limit(text, 200)
        assert len(result.split()) <= 201  # word + possible ellipsis

    def test_truncation_ends_at_sentence_boundary(self):
        agent = SynopsisAgent()
        # 10 sentences of 25 words each = 250 words total
        sentence = "This is a complete sentence with exactly ten words here. "
        text = sentence * 25
        result = agent._truncate_to_word_limit(text, 200)
        # Should end with a period
        assert result.endswith(".")

    def test_no_sentence_boundary_adds_ellipsis(self):
        agent = SynopsisAgent()
        # Words without any punctuation
        text = " ".join(["word"] * 250)
        result = agent._truncate_to_word_limit(text, 200)
        assert result.endswith("...")

    def test_question_mark_is_valid_sentence_end(self):
        agent = SynopsisAgent()
        words = " ".join(["word"] * 190) + "? " + " ".join(["word"] * 60)
        result = agent._truncate_to_word_limit(words, 200)
        assert result.endswith("?")
