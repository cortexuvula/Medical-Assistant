"""
Tests for src/core/config.py — enums and dataclasses only.

Covers: Environment, AIProvider, STTProvider, Theme, APIConfig,
AudioConfig, StorageConfig, UIConfig, TranscriptionConfig,
AITaskConfig, DeepgramConfig, ElevenLabsConfig.

get_config() and init_config() are intentionally excluded because
they instantiate Config(), which touches the filesystem and network.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from core.config import (
    Environment,
    AIProvider,
    STTProvider,
    Theme,
    APIConfig,
    AudioConfig,
    StorageConfig,
    UIConfig,
    TranscriptionConfig,
    AITaskConfig,
    DeepgramConfig,
    ElevenLabsConfig,
)


# ---------------------------------------------------------------------------
# Environment enum
# ---------------------------------------------------------------------------

class TestEnvironmentEnum:
    """Tests for the Environment enum."""

    def test_has_three_members(self):
        assert len(Environment) == 3

    def test_development_value(self):
        assert Environment.DEVELOPMENT.value == "development"

    def test_production_value(self):
        assert Environment.PRODUCTION.value == "production"

    def test_testing_value(self):
        assert Environment.TESTING.value == "testing"

    def test_lookup_by_value_development(self):
        assert Environment("development") is Environment.DEVELOPMENT

    def test_lookup_by_value_production(self):
        assert Environment("production") is Environment.PRODUCTION

    def test_lookup_by_value_testing(self):
        assert Environment("testing") is Environment.TESTING

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            Environment("invalid")

    def test_members_are_distinct(self):
        members = list(Environment)
        assert len(set(m.value for m in members)) == 3


# ---------------------------------------------------------------------------
# AIProvider enum
# ---------------------------------------------------------------------------

class TestAIProviderEnum:
    """Tests for the AIProvider enum."""

    def test_has_four_members(self):
        assert len(AIProvider) == 4

    def test_openai_value(self):
        assert AIProvider.OPENAI.value == "openai"

    def test_anthropic_value(self):
        assert AIProvider.ANTHROPIC.value == "anthropic"

    def test_ollama_value(self):
        assert AIProvider.OLLAMA.value == "ollama"

    def test_gemini_value(self):
        assert AIProvider.GEMINI.value == "gemini"

    def test_lookup_openai(self):
        assert AIProvider("openai") is AIProvider.OPENAI

    def test_lookup_anthropic(self):
        assert AIProvider("anthropic") is AIProvider.ANTHROPIC

    def test_lookup_ollama(self):
        assert AIProvider("ollama") is AIProvider.OLLAMA

    def test_lookup_gemini(self):
        assert AIProvider("gemini") is AIProvider.GEMINI

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            AIProvider("unknown_provider")

    def test_all_values_are_lowercase_strings(self):
        for member in AIProvider:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()


# ---------------------------------------------------------------------------
# STTProvider enum
# ---------------------------------------------------------------------------

class TestSTTProviderEnum:
    """Tests for the STTProvider enum."""

    def test_has_four_members(self):
        assert len(STTProvider) == 4

    def test_groq_value(self):
        assert STTProvider.GROQ.value == "groq"

    def test_deepgram_value(self):
        assert STTProvider.DEEPGRAM.value == "deepgram"

    def test_elevenlabs_value(self):
        assert STTProvider.ELEVENLABS.value == "elevenlabs"

    def test_whisper_value(self):
        assert STTProvider.WHISPER.value == "whisper"

    def test_lookup_groq(self):
        assert STTProvider("groq") is STTProvider.GROQ

    def test_lookup_deepgram(self):
        assert STTProvider("deepgram") is STTProvider.DEEPGRAM

    def test_lookup_elevenlabs(self):
        assert STTProvider("elevenlabs") is STTProvider.ELEVENLABS

    def test_lookup_whisper(self):
        assert STTProvider("whisper") is STTProvider.WHISPER

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            STTProvider("azure")

    def test_all_values_are_lowercase_strings(self):
        for member in STTProvider:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()


# ---------------------------------------------------------------------------
# Theme enum
# ---------------------------------------------------------------------------

class TestThemeEnum:
    """Tests for the Theme enum."""

    def test_has_twelve_members(self):
        assert len(Theme) == 12

    def test_flatly_value(self):
        assert Theme.FLATLY.value == "flatly"

    def test_darkly_value(self):
        assert Theme.DARKLY.value == "darkly"

    def test_cosmo_value(self):
        assert Theme.COSMO.value == "cosmo"

    def test_journal_value(self):
        assert Theme.JOURNAL.value == "journal"

    def test_lumen_value(self):
        assert Theme.LUMEN.value == "lumen"

    def test_minty_value(self):
        assert Theme.MINTY.value == "minty"

    def test_pulse_value(self):
        assert Theme.PULSE.value == "pulse"

    def test_simplex_value(self):
        assert Theme.SIMPLEX.value == "simplex"

    def test_slate_value(self):
        assert Theme.SLATE.value == "slate"

    def test_solar_value(self):
        assert Theme.SOLAR.value == "solar"

    def test_superhero_value(self):
        assert Theme.SUPERHERO.value == "superhero"

    def test_united_value(self):
        assert Theme.UNITED.value == "united"

    def test_lookup_flatly(self):
        assert Theme("flatly") is Theme.FLATLY

    def test_lookup_darkly(self):
        assert Theme("darkly") is Theme.DARKLY

    def test_invalid_theme_raises(self):
        with pytest.raises(ValueError):
            Theme("bootstrap")

    def test_all_values_are_lowercase_strings(self):
        for member in Theme:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()


# ---------------------------------------------------------------------------
# APIConfig dataclass
# ---------------------------------------------------------------------------

class TestAPIConfigDefaults:
    """Tests for APIConfig default values."""

    def setup_method(self):
        self.cfg = APIConfig()

    def test_timeout_default(self):
        assert self.cfg.timeout == 60

    def test_max_retries_default(self):
        assert self.cfg.max_retries == 3

    def test_initial_retry_delay_default(self):
        assert self.cfg.initial_retry_delay == 1.0

    def test_backoff_factor_default(self):
        assert self.cfg.backoff_factor == 2.0

    def test_max_retry_delay_default(self):
        assert self.cfg.max_retry_delay == 60.0

    def test_circuit_breaker_threshold_default(self):
        assert self.cfg.circuit_breaker_threshold == 5

    def test_circuit_breaker_timeout_default(self):
        assert self.cfg.circuit_breaker_timeout == 60

    def test_timeout_is_int(self):
        assert isinstance(self.cfg.timeout, int)

    def test_initial_retry_delay_is_float(self):
        assert isinstance(self.cfg.initial_retry_delay, float)

    def test_backoff_factor_is_float(self):
        assert isinstance(self.cfg.backoff_factor, float)


class TestAPIConfigCustomValues:
    """Tests that APIConfig fields can be customised."""

    def test_custom_timeout(self):
        cfg = APIConfig(timeout=120)
        assert cfg.timeout == 120

    def test_custom_max_retries(self):
        cfg = APIConfig(max_retries=5)
        assert cfg.max_retries == 5

    def test_custom_initial_retry_delay(self):
        cfg = APIConfig(initial_retry_delay=0.5)
        assert cfg.initial_retry_delay == 0.5

    def test_custom_backoff_factor(self):
        cfg = APIConfig(backoff_factor=3.0)
        assert cfg.backoff_factor == 3.0

    def test_custom_max_retry_delay(self):
        cfg = APIConfig(max_retry_delay=30.0)
        assert cfg.max_retry_delay == 30.0

    def test_custom_circuit_breaker_threshold(self):
        cfg = APIConfig(circuit_breaker_threshold=10)
        assert cfg.circuit_breaker_threshold == 10

    def test_custom_circuit_breaker_timeout(self):
        cfg = APIConfig(circuit_breaker_timeout=120)
        assert cfg.circuit_breaker_timeout == 120

    def test_all_fields_custom(self):
        cfg = APIConfig(
            timeout=30,
            max_retries=1,
            initial_retry_delay=0.25,
            backoff_factor=1.5,
            max_retry_delay=10.0,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=30,
        )
        assert cfg.timeout == 30
        assert cfg.max_retries == 1
        assert cfg.initial_retry_delay == 0.25
        assert cfg.backoff_factor == 1.5
        assert cfg.max_retry_delay == 10.0
        assert cfg.circuit_breaker_threshold == 3
        assert cfg.circuit_breaker_timeout == 30


# ---------------------------------------------------------------------------
# AudioConfig dataclass
# ---------------------------------------------------------------------------

class TestAudioConfigDefaults:
    """Tests for AudioConfig default values."""

    def setup_method(self):
        self.cfg = AudioConfig()

    def test_sample_rate_default(self):
        assert self.cfg.sample_rate == 16000

    def test_channels_default(self):
        assert self.cfg.channels == 1

    def test_chunk_size_default(self):
        assert self.cfg.chunk_size == 1024

    def test_format_default(self):
        assert self.cfg.format == "wav"

    def test_silence_threshold_default(self):
        assert self.cfg.silence_threshold == 500

    def test_silence_duration_default(self):
        assert self.cfg.silence_duration == 1.0

    def test_max_recording_duration_default(self):
        assert self.cfg.max_recording_duration == 300

    def test_playback_speed_default(self):
        assert self.cfg.playback_speed == 1.0

    def test_buffer_size_default(self):
        assert self.cfg.buffer_size == 4096

    def test_format_is_string(self):
        assert isinstance(self.cfg.format, str)

    def test_sample_rate_is_int(self):
        assert isinstance(self.cfg.sample_rate, int)


class TestAudioConfigCustomValues:
    """Tests that AudioConfig fields can be customised."""

    def test_custom_sample_rate(self):
        cfg = AudioConfig(sample_rate=44100)
        assert cfg.sample_rate == 44100

    def test_custom_channels(self):
        cfg = AudioConfig(channels=2)
        assert cfg.channels == 2

    def test_custom_format(self):
        cfg = AudioConfig(format="mp3")
        assert cfg.format == "mp3"

    def test_custom_chunk_size(self):
        cfg = AudioConfig(chunk_size=2048)
        assert cfg.chunk_size == 2048

    def test_custom_playback_speed(self):
        cfg = AudioConfig(playback_speed=1.5)
        assert cfg.playback_speed == 1.5


# ---------------------------------------------------------------------------
# StorageConfig dataclass
# ---------------------------------------------------------------------------

class TestStorageConfigDefaults:
    """Tests for StorageConfig default values."""

    def setup_method(self):
        self.cfg = StorageConfig()

    def test_database_name_default(self):
        assert self.cfg.database_name == "medical_assistant.db"

    def test_auto_save_default(self):
        assert self.cfg.auto_save is True

    def test_auto_save_interval_default(self):
        assert self.cfg.auto_save_interval == 60

    def test_max_file_size_mb_default(self):
        assert self.cfg.max_file_size_mb == 100

    def test_export_formats_is_list(self):
        assert isinstance(self.cfg.export_formats, list)

    def test_export_formats_contains_txt(self):
        assert "txt" in self.cfg.export_formats

    def test_export_formats_contains_pdf(self):
        assert "pdf" in self.cfg.export_formats

    def test_export_formats_contains_docx(self):
        assert "docx" in self.cfg.export_formats

    def test_export_formats_length(self):
        assert len(self.cfg.export_formats) == 3

    def test_base_folder_is_string(self):
        assert isinstance(self.cfg.base_folder, str)

    def test_export_formats_independent_per_instance(self):
        """Mutable default must not be shared between instances."""
        cfg1 = StorageConfig()
        cfg2 = StorageConfig()
        cfg1.export_formats.append("xml")
        assert "xml" not in cfg2.export_formats


# ---------------------------------------------------------------------------
# UIConfig dataclass
# ---------------------------------------------------------------------------

class TestUIConfigDefaults:
    """Tests for UIConfig default values."""

    def setup_method(self):
        self.cfg = UIConfig()

    def test_theme_is_flatly_value(self):
        assert self.cfg.theme == Theme.FLATLY.value

    def test_theme_is_string(self):
        assert isinstance(self.cfg.theme, str)

    def test_theme_value_equals_flatly(self):
        assert self.cfg.theme == "flatly"

    def test_min_window_width_default(self):
        assert self.cfg.min_window_width == 800

    def test_min_window_height_default(self):
        assert self.cfg.min_window_height == 600

    def test_font_size_default(self):
        assert self.cfg.font_size == 10

    def test_font_family_default(self):
        assert self.cfg.font_family == "Segoe UI"

    def test_show_tooltips_default(self):
        assert self.cfg.show_tooltips is True

    def test_animation_speed_default(self):
        assert self.cfg.animation_speed == 200

    def test_autoscroll_transcript_default(self):
        assert self.cfg.autoscroll_transcript is True

    def test_window_width_default(self):
        assert self.cfg.window_width == 0

    def test_window_height_default(self):
        assert self.cfg.window_height == 0

    def test_theme_valid_in_enum(self):
        """Theme string stored on UIConfig must still resolve in the enum."""
        assert Theme(self.cfg.theme) is Theme.FLATLY


class TestUIConfigCustomValues:
    """Tests that UIConfig fields can be customised."""

    def test_custom_theme(self):
        cfg = UIConfig(theme=Theme.DARKLY.value)
        assert cfg.theme == "darkly"

    def test_custom_font_size(self):
        cfg = UIConfig(font_size=14)
        assert cfg.font_size == 14

    def test_custom_show_tooltips_false(self):
        cfg = UIConfig(show_tooltips=False)
        assert cfg.show_tooltips is False


# ---------------------------------------------------------------------------
# TranscriptionConfig dataclass
# ---------------------------------------------------------------------------

class TestTranscriptionConfigDefaults:
    """Tests for TranscriptionConfig default values and existence."""

    def setup_method(self):
        self.cfg = TranscriptionConfig()

    def test_creates_successfully(self):
        assert self.cfg is not None

    def test_has_default_provider_attribute(self):
        assert hasattr(self.cfg, "default_provider")

    def test_default_provider_is_elevenlabs(self):
        assert self.cfg.default_provider == STTProvider.ELEVENLABS.value

    def test_default_provider_is_string(self):
        assert isinstance(self.cfg.default_provider, str)

    def test_chunk_duration_seconds_default(self):
        assert self.cfg.chunk_duration_seconds == 30

    def test_overlap_seconds_default(self):
        assert self.cfg.overlap_seconds == 2

    def test_min_confidence_default(self):
        assert self.cfg.min_confidence == 0.7

    def test_enable_punctuation_default(self):
        assert self.cfg.enable_punctuation is True

    def test_enable_diarization_default(self):
        assert self.cfg.enable_diarization is False

    def test_max_alternatives_default(self):
        assert self.cfg.max_alternatives == 1

    def test_language_default(self):
        assert self.cfg.language == "en-US"

    def test_default_provider_valid_stt_enum_value(self):
        assert STTProvider(self.cfg.default_provider) is STTProvider.ELEVENLABS


# ---------------------------------------------------------------------------
# AITaskConfig dataclass
# ---------------------------------------------------------------------------

class TestAITaskConfigDefaults:
    """Tests for AITaskConfig creation and default values."""

    def test_creates_successfully_with_prompt(self):
        cfg = AITaskConfig(prompt="Do something.")
        assert cfg is not None

    def test_prompt_stored_correctly(self):
        cfg = AITaskConfig(prompt="Refine the text.")
        assert cfg.prompt == "Refine the text."

    def test_system_message_default_empty(self):
        cfg = AITaskConfig(prompt="x")
        assert cfg.system_message == ""

    def test_model_default(self):
        cfg = AITaskConfig(prompt="x")
        assert cfg.model == "gpt-3.5-turbo"

    def test_temperature_default(self):
        cfg = AITaskConfig(prompt="x")
        assert cfg.temperature == 0.7

    def test_max_tokens_default_none(self):
        cfg = AITaskConfig(prompt="x")
        assert cfg.max_tokens is None

    def test_provider_models_default_empty_dict(self):
        cfg = AITaskConfig(prompt="x")
        assert cfg.provider_models == {}

    def test_provider_temperatures_default_empty_dict(self):
        cfg = AITaskConfig(prompt="x")
        assert cfg.provider_temperatures == {}

    def test_custom_temperature(self):
        cfg = AITaskConfig(prompt="x", temperature=0.0)
        assert cfg.temperature == 0.0

    def test_custom_model(self):
        cfg = AITaskConfig(prompt="x", model="gpt-4o")
        assert cfg.model == "gpt-4o"

    def test_custom_max_tokens(self):
        cfg = AITaskConfig(prompt="x", max_tokens=512)
        assert cfg.max_tokens == 512

    def test_provider_models_independent_per_instance(self):
        cfg1 = AITaskConfig(prompt="x")
        cfg2 = AITaskConfig(prompt="y")
        cfg1.provider_models["openai"] = "gpt-4"
        assert "openai" not in cfg2.provider_models


# ---------------------------------------------------------------------------
# DeepgramConfig dataclass
# ---------------------------------------------------------------------------

class TestDeepgramConfigDefaults:
    """Tests for DeepgramConfig default values."""

    def setup_method(self):
        self.cfg = DeepgramConfig()

    def test_creates_successfully(self):
        assert self.cfg is not None

    def test_model_default(self):
        assert self.cfg.model == "nova-2-medical"

    def test_language_default(self):
        assert self.cfg.language == "en-US"

    def test_smart_format_default(self):
        assert self.cfg.smart_format is True

    def test_diarize_default(self):
        assert self.cfg.diarize is False

    def test_profanity_filter_default(self):
        assert self.cfg.profanity_filter is False

    def test_redact_default(self):
        assert self.cfg.redact is False

    def test_alternatives_default(self):
        assert self.cfg.alternatives == 1

    def test_custom_model(self):
        cfg = DeepgramConfig(model="nova-2")
        assert cfg.model == "nova-2"

    def test_custom_diarize(self):
        cfg = DeepgramConfig(diarize=True)
        assert cfg.diarize is True


# ---------------------------------------------------------------------------
# ElevenLabsConfig dataclass
# ---------------------------------------------------------------------------

class TestElevenLabsConfigDefaults:
    """Tests for ElevenLabsConfig default values."""

    def setup_method(self):
        self.cfg = ElevenLabsConfig()

    def test_creates_successfully(self):
        assert self.cfg is not None

    def test_model_id_default(self):
        assert self.cfg.model_id == "scribe_v1"

    def test_language_code_default_empty(self):
        assert self.cfg.language_code == ""

    def test_tag_audio_events_default(self):
        assert self.cfg.tag_audio_events is True

    def test_num_speakers_default_none(self):
        assert self.cfg.num_speakers is None

    def test_timestamps_granularity_default(self):
        assert self.cfg.timestamps_granularity == "word"

    def test_diarize_default(self):
        assert self.cfg.diarize is True

    def test_custom_model_id(self):
        cfg = ElevenLabsConfig(model_id="scribe_v2")
        assert cfg.model_id == "scribe_v2"

    def test_custom_language_code(self):
        cfg = ElevenLabsConfig(language_code="en")
        assert cfg.language_code == "en"

    def test_custom_num_speakers(self):
        cfg = ElevenLabsConfig(num_speakers=2)
        assert cfg.num_speakers == 2

    def test_custom_diarize_false(self):
        cfg = ElevenLabsConfig(diarize=False)
        assert cfg.diarize is False
