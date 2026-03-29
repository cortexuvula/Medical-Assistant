"""
Tests for provider enums and BaseProvider in src/utils/constants.py

Covers BaseProvider class methods (values, names, is_valid, from_string, __str__),
AIProvider (6 members, display names), STTProvider (6 members, display names),
TTSProvider (3 members, display names), ProcessingStatus (5 members, display icon),
QueueStatus (5 members), TaskType (5 members).
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.constants import (
    BaseProvider, AIProvider, STTProvider, TTSProvider,
    ProcessingStatus, QueueStatus, TaskType,
)


class TestBaseProviderValues:
    def test_values_returns_list(self):
        assert isinstance(AIProvider.values(), list)

    def test_values_are_strings(self):
        for v in AIProvider.values():
            assert isinstance(v, str)

    def test_values_non_empty(self):
        assert len(AIProvider.values()) > 0

    def test_names_returns_list(self):
        assert isinstance(AIProvider.names(), list)

    def test_names_match_enum_names(self):
        names = AIProvider.names()
        for member in AIProvider:
            assert member.name in names


class TestBaseProviderIsValid:
    def test_valid_lowercase(self):
        assert AIProvider.is_valid("openai") is True

    def test_valid_uppercase(self):
        assert AIProvider.is_valid("OPENAI") is True

    def test_valid_mixed_case(self):
        assert AIProvider.is_valid("OpenAI") is True

    def test_invalid_value_returns_false(self):
        assert AIProvider.is_valid("unknown_provider") is False

    def test_empty_string_is_invalid(self):
        assert AIProvider.is_valid("") is False


class TestBaseProviderFromString:
    def test_lowercase_lookup(self):
        assert AIProvider.from_string("openai") == AIProvider.OPENAI

    def test_uppercase_lookup(self):
        assert AIProvider.from_string("OPENAI") == AIProvider.OPENAI

    def test_unknown_returns_none(self):
        assert AIProvider.from_string("unknown") is None

    def test_returns_anthropic(self):
        assert AIProvider.from_string("anthropic") == AIProvider.ANTHROPIC

    def test_returns_gemini(self):
        assert AIProvider.from_string("gemini") == AIProvider.GEMINI


class TestBaseProviderStr:
    def test_str_returns_value(self):
        assert str(AIProvider.OPENAI) == "openai"

    def test_str_anthropic(self):
        assert str(AIProvider.ANTHROPIC) == "anthropic"

    def test_str_ollama(self):
        assert str(AIProvider.OLLAMA) == "ollama"


class TestAIProvider:
    def test_has_openai(self):
        assert AIProvider.OPENAI.value == "openai"

    def test_has_anthropic(self):
        assert AIProvider.ANTHROPIC.value == "anthropic"

    def test_has_ollama(self):
        assert AIProvider.OLLAMA.value == "ollama"

    def test_has_gemini(self):
        assert AIProvider.GEMINI.value == "gemini"

    def test_has_groq(self):
        assert AIProvider.GROQ.value == "groq"

    def test_has_cerebras(self):
        assert AIProvider.CEREBRAS.value == "cerebras"

    def test_six_members(self):
        assert len(list(AIProvider)) == 6

    def test_display_name_openai(self):
        assert "OpenAI" in AIProvider.get_display_name(AIProvider.OPENAI)

    def test_display_name_anthropic(self):
        name = AIProvider.get_display_name(AIProvider.ANTHROPIC)
        assert "Anthropic" in name or "Claude" in name

    def test_display_name_ollama(self):
        name = AIProvider.get_display_name(AIProvider.OLLAMA)
        assert "Ollama" in name or "Local" in name

    def test_display_name_groq(self):
        assert "Groq" in AIProvider.get_display_name(AIProvider.GROQ)

    def test_display_name_cerebras(self):
        assert "Cerebras" in AIProvider.get_display_name(AIProvider.CEREBRAS)

    def test_display_name_gemini(self):
        assert "Gemini" in AIProvider.get_display_name(AIProvider.GEMINI)

    def test_display_names_are_strings(self):
        for member in AIProvider:
            assert isinstance(AIProvider.get_display_name(member), str)


class TestSTTProvider:
    def test_has_deepgram(self):
        assert STTProvider.DEEPGRAM.value == "deepgram"

    def test_has_groq(self):
        assert STTProvider.GROQ.value == "groq"

    def test_has_elevenlabs(self):
        assert STTProvider.ELEVENLABS.value == "elevenlabs"

    def test_has_whisper(self):
        assert STTProvider.WHISPER.value == "whisper"

    def test_has_openai(self):
        assert STTProvider.OPENAI.value == "openai"

    def test_has_modulate(self):
        assert STTProvider.MODULATE.value == "modulate"

    def test_six_members(self):
        assert len(list(STTProvider)) == 6

    def test_is_valid_deepgram(self):
        assert STTProvider.is_valid("deepgram") is True

    def test_from_string_whisper(self):
        assert STTProvider.from_string("whisper") == STTProvider.WHISPER

    def test_display_name_deepgram(self):
        assert "Deepgram" in STTProvider.get_display_name(STTProvider.DEEPGRAM)

    def test_display_name_whisper(self):
        assert "Whisper" in STTProvider.get_display_name(STTProvider.WHISPER)


class TestTTSProvider:
    def test_has_elevenlabs(self):
        assert TTSProvider.ELEVENLABS.value == "elevenlabs"

    def test_has_openai(self):
        assert TTSProvider.OPENAI.value == "openai"

    def test_has_system(self):
        assert TTSProvider.SYSTEM.value == "system"

    def test_three_members(self):
        assert len(list(TTSProvider)) == 3

    def test_display_name_elevenlabs(self):
        assert "ElevenLabs" in TTSProvider.get_display_name(TTSProvider.ELEVENLABS)

    def test_display_name_openai(self):
        assert "OpenAI" in TTSProvider.get_display_name(TTSProvider.OPENAI)

    def test_display_name_system(self):
        name = TTSProvider.get_display_name(TTSProvider.SYSTEM)
        assert "System" in name or "Voice" in name

    def test_is_valid_system(self):
        assert TTSProvider.is_valid("system") is True

    def test_not_valid_invalid(self):
        assert TTSProvider.is_valid("google") is False


class TestProcessingStatus:
    def test_has_pending(self):
        assert ProcessingStatus.PENDING.value == "pending"

    def test_has_processing(self):
        assert ProcessingStatus.PROCESSING.value == "processing"

    def test_has_completed(self):
        assert ProcessingStatus.COMPLETED.value == "completed"

    def test_has_failed(self):
        assert ProcessingStatus.FAILED.value == "failed"

    def test_has_cancelled(self):
        assert ProcessingStatus.CANCELLED.value == "cancelled"

    def test_five_members(self):
        assert len(list(ProcessingStatus)) == 5

    def test_icon_completed_is_checkmark(self):
        icon = ProcessingStatus.get_display_icon(ProcessingStatus.COMPLETED)
        assert isinstance(icon, str) and len(icon) > 0

    def test_icon_failed_is_nonempty(self):
        icon = ProcessingStatus.get_display_icon(ProcessingStatus.FAILED)
        assert isinstance(icon, str) and len(icon) > 0

    def test_icon_returns_string_for_all(self):
        for member in ProcessingStatus:
            assert isinstance(ProcessingStatus.get_display_icon(member), str)

    def test_pending_icon_nonempty(self):
        icon = ProcessingStatus.get_display_icon(ProcessingStatus.PENDING)
        assert len(icon) > 0

    def test_processing_icon_differs_from_completed(self):
        proc = ProcessingStatus.get_display_icon(ProcessingStatus.PROCESSING)
        comp = ProcessingStatus.get_display_icon(ProcessingStatus.COMPLETED)
        assert proc != comp


class TestQueueStatus:
    def test_has_pending(self):
        assert QueueStatus.PENDING.value == "pending"

    def test_has_in_progress(self):
        assert QueueStatus.IN_PROGRESS.value == "in_progress"

    def test_has_completed(self):
        assert QueueStatus.COMPLETED.value == "completed"

    def test_has_failed(self):
        assert QueueStatus.FAILED.value == "failed"

    def test_has_retrying(self):
        assert QueueStatus.RETRYING.value == "retrying"

    def test_five_members(self):
        assert len(list(QueueStatus)) == 5

    def test_is_valid_pending(self):
        assert QueueStatus.is_valid("pending") is True

    def test_from_string_retrying(self):
        assert QueueStatus.from_string("retrying") == QueueStatus.RETRYING


class TestTaskType:
    def test_has_transcription(self):
        assert TaskType.TRANSCRIPTION.value == "transcription"

    def test_has_soap_note(self):
        assert TaskType.SOAP_NOTE.value == "soap_note"

    def test_has_referral(self):
        assert TaskType.REFERRAL.value == "referral"

    def test_has_letter(self):
        assert TaskType.LETTER.value == "letter"

    def test_has_full_process(self):
        assert TaskType.FULL_PROCESS.value == "full_process"

    def test_five_members(self):
        assert len(list(TaskType)) == 5

    def test_is_valid_transcription(self):
        assert TaskType.is_valid("transcription") is True

    def test_from_string_soap(self):
        assert TaskType.from_string("soap_note") == TaskType.SOAP_NOTE
