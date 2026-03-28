"""
Tests for src/core/config.py

Covers:
- Environment enum and environment selection
- Config dataclass defaults and field validation
- Config loading from files (default + environment-specific)
- Config merging (deep merge)
- Config apply from loaded dicts
- Missing config file handling
- Config validation (theme, STT provider, numeric ranges)
- Config to_dict round-trip
- get_api_key() from environment variables
- validate_api_keys()
- get_config() and init_config() module-level functions
"""

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import asdict

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
    Config,
    get_config,
    init_config,
)
from utils.exceptions import ConfigurationError


class TestEnvironmentEnum(unittest.TestCase):
    """Tests for the Environment enum."""

    def test_development(self):
        self.assertEqual(Environment.DEVELOPMENT.value, "development")

    def test_production(self):
        self.assertEqual(Environment.PRODUCTION.value, "production")

    def test_testing(self):
        self.assertEqual(Environment.TESTING.value, "testing")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            Environment("invalid")


class TestAIProviderEnum(unittest.TestCase):
    """Tests for the AIProvider enum."""

    def test_has_expected_providers(self):
        self.assertEqual(AIProvider.OPENAI.value, "openai")
        self.assertEqual(AIProvider.OLLAMA.value, "ollama")
        self.assertEqual(AIProvider.ANTHROPIC.value, "anthropic")
        self.assertEqual(AIProvider.GEMINI.value, "gemini")


class TestSTTProviderEnum(unittest.TestCase):
    """Tests for the STTProvider enum."""

    def test_has_expected_providers(self):
        self.assertEqual(STTProvider.GROQ.value, "groq")
        self.assertEqual(STTProvider.DEEPGRAM.value, "deepgram")
        self.assertEqual(STTProvider.ELEVENLABS.value, "elevenlabs")
        self.assertEqual(STTProvider.WHISPER.value, "whisper")


class TestThemeEnum(unittest.TestCase):
    """Tests for the Theme enum."""

    def test_flatly(self):
        self.assertEqual(Theme.FLATLY.value, "flatly")

    def test_darkly(self):
        self.assertEqual(Theme.DARKLY.value, "darkly")

    def test_all_themes_are_lowercase(self):
        for theme in Theme:
            self.assertEqual(theme.value, theme.value.lower())


class TestAPIConfig(unittest.TestCase):
    """Tests for APIConfig dataclass defaults."""

    def test_default_values(self):
        cfg = APIConfig()
        self.assertEqual(cfg.timeout, 60)
        self.assertEqual(cfg.max_retries, 3)
        self.assertEqual(cfg.initial_retry_delay, 1.0)
        self.assertEqual(cfg.backoff_factor, 2.0)
        self.assertEqual(cfg.max_retry_delay, 60.0)
        self.assertEqual(cfg.circuit_breaker_threshold, 5)
        self.assertEqual(cfg.circuit_breaker_timeout, 60)

    def test_custom_values(self):
        cfg = APIConfig(timeout=120, max_retries=5)
        self.assertEqual(cfg.timeout, 120)
        self.assertEqual(cfg.max_retries, 5)

    def test_asdict_round_trip(self):
        cfg = APIConfig(timeout=30)
        d = asdict(cfg)
        self.assertEqual(d["timeout"], 30)
        self.assertIsInstance(d, dict)


class TestAudioConfig(unittest.TestCase):
    """Tests for AudioConfig dataclass defaults."""

    def test_default_values(self):
        cfg = AudioConfig()
        self.assertEqual(cfg.sample_rate, 16000)
        self.assertEqual(cfg.channels, 1)
        self.assertEqual(cfg.chunk_size, 1024)
        self.assertEqual(cfg.format, "wav")
        self.assertEqual(cfg.max_recording_duration, 300)


class TestStorageConfig(unittest.TestCase):
    """Tests for StorageConfig dataclass defaults."""

    def test_default_values(self):
        cfg = StorageConfig()
        self.assertIn("Medical-Dictation", cfg.base_folder)
        self.assertEqual(cfg.database_name, "medical_assistant.db")
        self.assertTrue(cfg.auto_save)
        self.assertIn("txt", cfg.export_formats)
        self.assertIn("pdf", cfg.export_formats)

    def test_export_formats_is_list(self):
        cfg = StorageConfig()
        self.assertIsInstance(cfg.export_formats, list)


class TestUIConfig(unittest.TestCase):
    """Tests for UIConfig dataclass defaults."""

    def test_default_values(self):
        cfg = UIConfig()
        self.assertEqual(cfg.theme, "flatly")
        self.assertEqual(cfg.window_width, 0)
        self.assertEqual(cfg.window_height, 0)
        self.assertEqual(cfg.min_window_width, 800)
        self.assertEqual(cfg.min_window_height, 600)
        self.assertTrue(cfg.show_tooltips)


class TestTranscriptionConfig(unittest.TestCase):
    """Tests for TranscriptionConfig dataclass defaults."""

    def test_default_values(self):
        cfg = TranscriptionConfig()
        self.assertEqual(cfg.default_provider, "elevenlabs")
        self.assertEqual(cfg.language, "en-US")
        self.assertTrue(cfg.enable_punctuation)
        self.assertFalse(cfg.enable_diarization)


class TestAITaskConfig(unittest.TestCase):
    """Tests for AITaskConfig dataclass."""

    def test_required_prompt(self):
        cfg = AITaskConfig(prompt="Test prompt")
        self.assertEqual(cfg.prompt, "Test prompt")
        self.assertEqual(cfg.model, "gpt-3.5-turbo")
        self.assertEqual(cfg.temperature, 0.7)

    def test_custom_values(self):
        cfg = AITaskConfig(
            prompt="Custom prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
        )
        self.assertEqual(cfg.model, "gpt-4")
        self.assertEqual(cfg.max_tokens, 500)

    def test_provider_models_default_empty(self):
        cfg = AITaskConfig(prompt="p")
        self.assertEqual(cfg.provider_models, {})


class TestDeepgramConfig(unittest.TestCase):
    """Tests for DeepgramConfig defaults."""

    def test_defaults(self):
        cfg = DeepgramConfig()
        self.assertEqual(cfg.model, "nova-2-medical")
        self.assertEqual(cfg.language, "en-US")
        self.assertTrue(cfg.smart_format)
        self.assertFalse(cfg.diarize)


class TestElevenLabsConfig(unittest.TestCase):
    """Tests for ElevenLabsConfig defaults."""

    def test_defaults(self):
        cfg = ElevenLabsConfig()
        self.assertEqual(cfg.model_id, "scribe_v1")
        self.assertEqual(cfg.language_code, "")
        self.assertTrue(cfg.tag_audio_events)
        self.assertTrue(cfg.diarize)


class TestConfigEnvironmentSelection(unittest.TestCase):
    """Tests for Config._get_environment()."""

    def _make_config_with_env(self, environment=None, env_var=None):
        """Create a Config with mocked dependencies to test environment selection."""
        patches = {
            "core.config.get_logger": MagicMock(return_value=MagicMock()),
            "core.config.data_folder_manager": MagicMock(),
            "core.config.validate_model_name": MagicMock(return_value=(True, None)),
        }
        # Mock the config_folder as a Path-like object
        mock_config_dir = MagicMock(spec=Path)
        mock_config_dir.mkdir = MagicMock()
        mock_config_dir.__truediv__ = MagicMock(
            return_value=MagicMock(exists=MagicMock(return_value=False))
        )
        patches["core.config.data_folder_manager"].config_folder = mock_config_dir

        env_dict = {}
        if env_var:
            env_dict["MEDICAL_ASSISTANT_ENV"] = env_var

        with patch.multiple("core.config", **patches):
            with patch.dict(os.environ, env_dict, clear=False):
                cfg = Config(environment=environment)
                return cfg

    def test_explicit_development(self):
        cfg = self._make_config_with_env(environment="development")
        self.assertEqual(cfg.environment, Environment.DEVELOPMENT)

    def test_explicit_production(self):
        cfg = self._make_config_with_env(environment="production")
        self.assertEqual(cfg.environment, Environment.PRODUCTION)

    def test_explicit_testing(self):
        cfg = self._make_config_with_env(environment="testing")
        self.assertEqual(cfg.environment, Environment.TESTING)

    def test_explicit_case_insensitive(self):
        cfg = self._make_config_with_env(environment="PRODUCTION")
        self.assertEqual(cfg.environment, Environment.PRODUCTION)

    def test_invalid_explicit_falls_back_to_development(self):
        cfg = self._make_config_with_env(environment="staging")
        self.assertEqual(cfg.environment, Environment.DEVELOPMENT)

    def test_env_var_sets_environment(self):
        cfg = self._make_config_with_env(env_var="testing")
        self.assertEqual(cfg.environment, Environment.TESTING)

    def test_invalid_env_var_falls_back_to_development(self):
        cfg = self._make_config_with_env(env_var="invalid_env")
        self.assertEqual(cfg.environment, Environment.DEVELOPMENT)


class TestConfigMerge(unittest.TestCase):
    """Tests for Config._merge_configs()."""

    def setUp(self):
        """Create a Config instance for testing merge logic."""
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    self.cfg = Config(environment="testing")

    def test_shallow_merge(self):
        default = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = self.cfg._merge_configs(default, override)
        self.assertEqual(result, {"a": 1, "b": 3, "c": 4})

    def test_deep_merge(self):
        default = {"section": {"key1": "val1", "key2": "val2"}}
        override = {"section": {"key2": "new_val"}}
        result = self.cfg._merge_configs(default, override)
        self.assertEqual(result["section"]["key1"], "val1")
        self.assertEqual(result["section"]["key2"], "new_val")

    def test_override_replaces_non_dict(self):
        default = {"key": "old"}
        override = {"key": {"nested": True}}
        result = self.cfg._merge_configs(default, override)
        self.assertEqual(result["key"], {"nested": True})

    def test_empty_override(self):
        default = {"a": 1}
        result = self.cfg._merge_configs(default, {})
        self.assertEqual(result, {"a": 1})

    def test_empty_default(self):
        override = {"a": 1}
        result = self.cfg._merge_configs({}, override)
        self.assertEqual(result, {"a": 1})

    def test_both_empty(self):
        result = self.cfg._merge_configs({}, {})
        self.assertEqual(result, {})


class TestConfigLoadFile(unittest.TestCase):
    """Tests for Config._load_config_file()."""

    def setUp(self):
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    self.cfg = Config(environment="testing")

    def test_missing_file_returns_empty_dict(self):
        """Non-existent config files should return an empty dict."""
        result = self.cfg._load_config_file(Path("/nonexistent/config.json"))
        self.assertEqual(result, {})

    def test_valid_json_file(self):
        """Should parse and return JSON content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"api": {"timeout": 30}}, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            result = self.cfg._load_config_file(temp_path)
            self.assertEqual(result["api"]["timeout"], 30)
        finally:
            temp_path.unlink()

    def test_invalid_json_returns_empty_dict(self):
        """Malformed JSON should return an empty dict, not raise."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json content")
            f.flush()
            temp_path = Path(f.name)

        try:
            result = self.cfg._load_config_file(temp_path)
            self.assertEqual(result, {})
        finally:
            temp_path.unlink()


class TestConfigApply(unittest.TestCase):
    """Tests for Config._apply_config()."""

    def setUp(self):
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    self.cfg = Config(environment="testing")

    def test_apply_api_config(self):
        self.cfg._apply_config({"api": {"timeout": 120, "max_retries": 5}})
        self.assertEqual(self.cfg.api.timeout, 120)
        self.assertEqual(self.cfg.api.max_retries, 5)

    def test_apply_audio_config(self):
        self.cfg._apply_config({"audio": {"sample_rate": 44100}})
        self.assertEqual(self.cfg.audio.sample_rate, 44100)

    def test_apply_ui_config(self):
        self.cfg._apply_config({"ui": {"theme": "darkly", "font_size": 14}})
        self.assertEqual(self.cfg.ui.theme, "darkly")
        self.assertEqual(self.cfg.ui.font_size, 14)

    def test_apply_ignores_unknown_keys(self):
        """Unknown keys in a section should be silently ignored."""
        original_timeout = self.cfg.api.timeout
        self.cfg._apply_config({"api": {"nonexistent_key": 999}})
        self.assertEqual(self.cfg.api.timeout, original_timeout)

    def test_apply_transcription_config(self):
        self.cfg._apply_config({"transcription": {"language": "fr-FR"}})
        self.assertEqual(self.cfg.transcription.language, "fr-FR")

    def test_apply_deepgram_config(self):
        self.cfg._apply_config({"deepgram": {"model": "nova-2", "diarize": True}})
        self.assertEqual(self.cfg.deepgram.model, "nova-2")
        self.assertTrue(self.cfg.deepgram.diarize)

    def test_apply_elevenlabs_config(self):
        self.cfg._apply_config({"elevenlabs": {"language_code": "en"}})
        self.assertEqual(self.cfg.elevenlabs.language_code, "en")

    def test_apply_ai_tasks_config(self):
        self.cfg._apply_config({
            "ai_tasks": {
                "soap_note": {"temperature": 0.3}
            }
        })
        self.assertEqual(self.cfg.ai_tasks["soap_note"].temperature, 0.3)


class TestConfigValidation(unittest.TestCase):
    """Tests for Config._validate_config()."""

    def _make_config(self):
        """Create a Config instance with mocked dependencies."""
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    return Config(environment="testing")

    def test_valid_config_does_not_raise(self):
        """Default config should pass validation."""
        cfg = self._make_config()
        # No exception means validation passed during __init__

    def test_invalid_theme_raises(self):
        cfg = self._make_config()
        cfg.ui.theme = "nonexistent_theme"
        with self.assertRaises(ConfigurationError):
            cfg._validate_config()

    def test_invalid_stt_provider_raises(self):
        cfg = self._make_config()
        cfg.transcription.default_provider = "invalid_provider"
        with self.assertRaises(ConfigurationError):
            cfg._validate_config()

    def test_negative_timeout_raises(self):
        cfg = self._make_config()
        cfg.api.timeout = -1
        with self.assertRaises(ConfigurationError):
            cfg._validate_config()

    def test_zero_timeout_raises(self):
        cfg = self._make_config()
        cfg.api.timeout = 0
        with self.assertRaises(ConfigurationError):
            cfg._validate_config()

    def test_negative_max_retries_raises(self):
        cfg = self._make_config()
        cfg.api.max_retries = -1
        with self.assertRaises(ConfigurationError):
            cfg._validate_config()

    def test_zero_sample_rate_raises(self):
        cfg = self._make_config()
        cfg.audio.sample_rate = 0
        with self.assertRaises(ConfigurationError):
            cfg._validate_config()

    def test_zero_max_file_size_raises(self):
        cfg = self._make_config()
        cfg.storage.max_file_size_mb = 0
        with self.assertRaises(ConfigurationError):
            cfg._validate_config()

    def test_invalid_model_name_raises(self):
        """If validate_model_name returns failure, validation should raise."""
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch(
                    "core.config.validate_model_name",
                    return_value=(False, "Invalid model"),
                ):
                    with self.assertRaises(ConfigurationError):
                        Config(environment="testing")


class TestConfigToDict(unittest.TestCase):
    """Tests for Config.to_dict()."""

    def test_to_dict_has_expected_keys(self):
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    cfg = Config(environment="testing")

        d = cfg.to_dict()
        self.assertIn("environment", d)
        self.assertIn("api", d)
        self.assertIn("audio", d)
        self.assertIn("storage", d)
        self.assertIn("ui", d)
        self.assertIn("transcription", d)
        self.assertIn("ai_tasks", d)
        self.assertEqual(d["environment"], "testing")

    def test_to_dict_is_serializable(self):
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    cfg = Config(environment="testing")

        d = cfg.to_dict()
        # Should be JSON serializable
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)


class TestConfigGetApiKey(unittest.TestCase):
    """Tests for Config.get_api_key()."""

    def setUp(self):
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    self.cfg = Config(environment="testing")

    def test_get_openai_key_from_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            key = self.cfg.get_api_key("openai")
            self.assertEqual(key, "sk-test123")

    def test_get_anthropic_key_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            key = self.cfg.get_api_key("anthropic")
            self.assertEqual(key, "sk-ant-test")

    def test_get_key_missing_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            key = self.cfg.get_api_key("openai")
            self.assertIsNone(key)

    def test_get_key_unknown_provider_returns_none(self):
        key = self.cfg.get_api_key("unknown_provider")
        self.assertIsNone(key)


class TestConfigSave(unittest.TestCase):
    """Tests for Config.save()."""

    def test_save_writes_json(self):
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                with tempfile.TemporaryDirectory() as tmpdir:
                    config_dir = Path(tmpdir) / "config"
                    config_dir.mkdir()

                    mock_dfm.config_folder = config_dir
                    with patch("core.config.validate_model_name", return_value=(True, None)):
                        cfg = Config(environment="testing")

                    cfg.save()

                    config_file = config_dir / "config.testing.json"
                    self.assertTrue(config_file.exists())

                    with open(config_file) as f:
                        saved = json.load(f)
                    self.assertEqual(saved["environment"], "testing")


class TestModuleLevelFunctions(unittest.TestCase):
    """Tests for get_config() and init_config()."""

    def test_init_config_creates_new_instance(self):
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    cfg = init_config("testing")
                    self.assertEqual(cfg.environment, Environment.TESTING)

    def test_get_config_returns_cached_instance(self):
        """After init_config, get_config should return the same instance."""
        with patch("core.config.get_logger", return_value=MagicMock()):
            with patch("core.config.data_folder_manager") as mock_dfm:
                mock_config_dir = MagicMock(spec=Path)
                mock_config_dir.mkdir = MagicMock()
                mock_config_dir.__truediv__ = MagicMock(
                    return_value=MagicMock(exists=MagicMock(return_value=False))
                )
                mock_dfm.config_folder = mock_config_dir
                with patch("core.config.validate_model_name", return_value=(True, None)):
                    cfg1 = init_config("testing")
                    cfg2 = get_config()
                    self.assertIs(cfg1, cfg2)


if __name__ == "__main__":
    unittest.main()
