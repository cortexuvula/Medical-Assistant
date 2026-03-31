"""
Tests for src/settings/settings_migration.py

Covers SettingsMigrator (migrate_from_dict, get_legacy_format) and
get_migrator singleton. Tests use isolated Config instances to avoid
state leaking between tests.
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import core.config as _config_module
from settings.settings_migration import SettingsMigrator, get_migrator


@pytest.fixture(autouse=True)
def reset_config():
    """Reset the global Config singleton before and after each test."""
    _config_module._config = None
    yield
    _config_module._config = None


# ===========================================================================
# SettingsMigrator — initialization
# ===========================================================================

class TestSettingsMigratorInit:
    def test_creates_successfully(self):
        m = SettingsMigrator()
        assert m is not None

    def test_has_config_attribute(self):
        m = SettingsMigrator()
        assert hasattr(m, "config")

    def test_config_is_not_none(self):
        m = SettingsMigrator()
        assert m.config is not None


# ===========================================================================
# get_legacy_format — structure
# ===========================================================================

class TestGetLegacyFormat:
    def test_returns_dict(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert isinstance(result, dict)

    def test_contains_refine_text(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "refine_text" in result

    def test_contains_improve_text(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "improve_text" in result

    def test_contains_soap_note(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "soap_note" in result

    def test_contains_referral(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "referral" in result

    def test_contains_deepgram(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "deepgram" in result

    def test_contains_ai_provider(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "ai_provider" in result

    def test_contains_stt_provider(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "stt_provider" in result

    def test_contains_theme(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "theme" in result

    def test_ai_task_has_prompt_key(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "prompt" in result["refine_text"]

    def test_ai_task_has_model_key(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "model" in result["soap_note"]

    def test_ai_task_has_temperature_key(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "temperature" in result["improve_text"]

    def test_deepgram_has_model_key(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "model" in result["deepgram"]

    def test_deepgram_has_smart_format_key(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert "smart_format" in result["deepgram"]

    def test_ai_provider_is_string(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert isinstance(result["ai_provider"], str)

    def test_theme_is_string(self):
        m = SettingsMigrator()
        result = m.get_legacy_format()
        assert isinstance(result["theme"], str)


# ===========================================================================
# migrate_from_dict — theme and UI settings
# ===========================================================================

class TestMigrateFromDictTheme:
    def test_migrate_theme(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"theme": "darkly"})
        assert m.config.ui.theme == "darkly"

    def test_migrate_window_width(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"window_width": 1600})
        assert m.config.ui.window_width == 1600

    def test_migrate_window_height(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"window_height": 900})
        assert m.config.ui.window_height == 900

    def test_empty_dict_no_error(self):
        m = SettingsMigrator()
        m.migrate_from_dict({})  # Should not raise

    def test_irrelevant_keys_no_error(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"unknown_key": "value", "another": 42})  # Should not raise


# ===========================================================================
# migrate_from_dict — STT provider
# ===========================================================================

class TestMigrateFromDictSTT:
    def test_migrate_stt_provider(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"stt_provider": "deepgram"})
        assert m.config.transcription.default_provider == "deepgram"

    def test_migrate_stt_provider_elevenlabs(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"stt_provider": "elevenlabs"})
        assert m.config.transcription.default_provider == "elevenlabs"


# ===========================================================================
# migrate_from_dict — storage
# ===========================================================================

class TestMigrateFromDictStorage:
    def test_migrate_storage_folder(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"storage_folder": "/tmp/test_recordings"})
        assert m.config.storage.base_folder == "/tmp/test_recordings"


# ===========================================================================
# migrate_from_dict — AI task settings
# ===========================================================================

class TestMigrateFromDictAITasks:
    def test_migrate_soap_note_model(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"soap_note": {"model": "gpt-4o"}})
        assert m.config.ai_tasks["soap_note"].model == "gpt-4o"

    def test_migrate_refine_text_temperature(self):
        m = SettingsMigrator()
        m.migrate_from_dict({"refine_text": {"temperature": 0.5}})
        assert m.config.ai_tasks["refine_text"].temperature == 0.5

    def test_migrate_improve_text_prompt(self):
        m = SettingsMigrator()
        test_prompt = "Improve the medical text below."
        m.migrate_from_dict({"improve_text": {"prompt": test_prompt}})
        assert m.config.ai_tasks["improve_text"].prompt == test_prompt

    def test_migrate_soap_note_system_message(self):
        m = SettingsMigrator()
        msg = "You are a medical assistant."
        m.migrate_from_dict({"soap_note": {"system_message": msg}})
        assert m.config.ai_tasks["soap_note"].system_message == msg


# ===========================================================================
# get_migrator singleton
# ===========================================================================

class TestGetMigrator:
    def test_returns_settings_migrator(self):
        m = get_migrator()
        assert isinstance(m, SettingsMigrator)

    def test_same_instance_each_call(self):
        m1 = get_migrator()
        m2 = get_migrator()
        assert m1 is m2

    def test_has_config(self):
        m = get_migrator()
        assert m.config is not None
