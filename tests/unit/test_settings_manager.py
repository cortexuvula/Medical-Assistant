"""
Tests for src/settings/settings_manager.py

Covers:
- Singleton pattern enforcement
- get() and set() for basic keys
- get_nested() and set_nested() for dot-notation path access
- Default value fallback when key doesn't exist
- Type-specific accessors (AI provider, STT provider, theme, etc.)
- Agent configuration accessors
- Feature flag accessors
- Window state accessors
- Settings persistence (save/reload)
"""

import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock


def _patch_sm_get_logger():
    """Patch get_logger on the actual settings_manager module (not the instance).

    settings.__init__.py shadows the submodule name with the singleton instance,
    so patch("settings.settings_manager.get_logger") resolves to the instance.
    Use sys.modules to get the real module.
    """
    mod = sys.modules.get("settings.settings_manager")
    if mod is None:
        import settings.settings_manager  # noqa: F811
        mod = sys.modules["settings.settings_manager"]
    return patch.object(mod, "get_logger", return_value=MagicMock())


class TestSettingsManagerSingleton(unittest.TestCase):
    """Tests for the singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Two instantiations should return the same object."""
        from settings.settings_manager import SettingsManager

        # Reset singleton for test isolation
        SettingsManager._instance = None

        with _patch_sm_get_logger():
            mgr1 = SettingsManager()
            mgr2 = SettingsManager()
            self.assertIs(mgr1, mgr2)

        # Clean up
        SettingsManager._instance = None

    def test_singleton_initialized_once(self):
        """__init__ body should only run once."""
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            mgr = SettingsManager()
            first_initialized = mgr._initialized
            self.assertTrue(first_initialized)

            # Second call should not re-initialize
            mgr2 = SettingsManager()
            self.assertTrue(mgr2._initialized)
            self.assertIs(mgr, mgr2)

        SettingsManager._instance = None


class TestSettingsManagerBasicAccess(unittest.TestCase):
    """Tests for get(), set(), get_all()."""

    def setUp(self):
        """Create a SettingsManager with a mock underlying SETTINGS dict."""
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            self.mgr = SettingsManager()

        # Inject a mock settings dict directly
        self.mock_settings = {
            "ai_provider": "openai",
            "stt_provider": "groq",
            "theme": "darkly",
            "quick_continue_mode": True,
            "window_width": 1200,
            "window_height": 800,
            "soap_note": {
                "model": "gpt-4",
                "temperature": 0.4,
            },
            "agent_config": {
                "diagnostic": {
                    "enabled": True,
                    "model": "gpt-4",
                },
                "synopsis": {
                    "enabled": False,
                },
            },
        }
        self.mgr._settings_module = self.mock_settings
        self.mgr._save = MagicMock()

    def tearDown(self):
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

    def test_get_existing_key(self):
        self.assertEqual(self.mgr.get("ai_provider"), "openai")

    def test_get_missing_key_returns_default(self):
        self.assertIsNone(self.mgr.get("nonexistent"))

    def test_get_missing_key_returns_custom_default(self):
        self.assertEqual(self.mgr.get("nonexistent", "fallback"), "fallback")

    def test_set_key(self):
        self.mgr.set("ai_provider", "anthropic")
        self.assertEqual(self.mock_settings["ai_provider"], "anthropic")
        self.mgr._save.assert_called_once()

    def test_set_key_without_auto_save(self):
        self.mgr.set("ai_provider", "anthropic", auto_save=False)
        self.assertEqual(self.mock_settings["ai_provider"], "anthropic")
        self.mgr._save.assert_not_called()

    def test_set_new_key(self):
        self.mgr.set("new_key", "new_value")
        self.assertEqual(self.mock_settings["new_key"], "new_value")

    def test_get_all_returns_settings_dict(self):
        result = self.mgr.get_all()
        self.assertIs(result, self.mock_settings)


class TestSettingsManagerNestedAccess(unittest.TestCase):
    """Tests for get_nested() and set_nested()."""

    def setUp(self):
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            self.mgr = SettingsManager()

        self.mock_settings = {
            "soap_note": {
                "model": "gpt-4",
                "temperature": 0.4,
            },
            "agent_config": {
                "diagnostic": {
                    "enabled": True,
                    "model": "gpt-4",
                    "temperature": 0.1,
                },
            },
        }
        self.mgr._settings_module = self.mock_settings
        self.mgr._save = MagicMock()

    def tearDown(self):
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

    def test_get_nested_one_level(self):
        result = self.mgr.get_nested("soap_note.model")
        self.assertEqual(result, "gpt-4")

    def test_get_nested_two_levels(self):
        result = self.mgr.get_nested("agent_config.diagnostic.enabled")
        self.assertTrue(result)

    def test_get_nested_three_levels(self):
        result = self.mgr.get_nested("agent_config.diagnostic.temperature")
        self.assertEqual(result, 0.1)

    def test_get_nested_missing_returns_default(self):
        result = self.mgr.get_nested("nonexistent.path", "default_val")
        self.assertEqual(result, "default_val")

    def test_get_nested_missing_intermediate_returns_default(self):
        result = self.mgr.get_nested("soap_note.missing.deep", "fallback")
        self.assertEqual(result, "fallback")

    def test_get_nested_missing_leaf_returns_default(self):
        result = self.mgr.get_nested("soap_note.nonexistent_key", "nope")
        self.assertEqual(result, "nope")

    def test_set_nested_existing_path(self):
        self.mgr.set_nested("soap_note.temperature", 0.8)
        self.assertEqual(self.mock_settings["soap_note"]["temperature"], 0.8)
        self.mgr._save.assert_called_once()

    def test_set_nested_creates_intermediate_dicts(self):
        self.mgr.set_nested("new_section.subsection.value", 42)
        self.assertEqual(self.mock_settings["new_section"]["subsection"]["value"], 42)

    def test_set_nested_without_auto_save(self):
        self.mgr.set_nested("soap_note.temperature", 0.9, auto_save=False)
        self.assertEqual(self.mock_settings["soap_note"]["temperature"], 0.9)
        self.mgr._save.assert_not_called()

    def test_set_nested_deep_path(self):
        self.mgr.set_nested("agent_config.diagnostic.enabled", False)
        self.assertFalse(self.mock_settings["agent_config"]["diagnostic"]["enabled"])

    def test_get_nested_with_none_value_returns_default(self):
        """If a key exists but value is None, get_nested should return the default."""
        self.mock_settings["soap_note"]["model"] = None
        result = self.mgr.get_nested("soap_note.model", "default_model")
        self.assertEqual(result, "default_model")


class TestSettingsManagerProviderAccessors(unittest.TestCase):
    """Tests for typed provider accessors."""

    def setUp(self):
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            self.mgr = SettingsManager()

        self.mock_settings = {
            "ai_provider": "anthropic",
            "stt_provider": "deepgram",
            "theme": "slate",
        }
        self.mgr._settings_module = self.mock_settings
        self.mgr._save = MagicMock()

    def tearDown(self):
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

    def test_get_ai_provider(self):
        self.assertEqual(self.mgr.get_ai_provider(), "anthropic")

    def test_get_ai_provider_default(self):
        del self.mock_settings["ai_provider"]
        result = self.mgr.get_ai_provider()
        self.assertEqual(result, "openai")  # PROVIDER_OPENAI default

    def test_set_ai_provider(self):
        self.mgr.set_ai_provider("gemini")
        self.assertEqual(self.mock_settings["ai_provider"], "gemini")

    def test_get_stt_provider(self):
        self.assertEqual(self.mgr.get_stt_provider(), "deepgram")

    def test_get_stt_provider_default(self):
        del self.mock_settings["stt_provider"]
        result = self.mgr.get_stt_provider()
        self.assertEqual(result, "groq")  # STT_GROQ default

    def test_set_stt_provider(self):
        self.mgr.set_stt_provider("elevenlabs")
        self.assertEqual(self.mock_settings["stt_provider"], "elevenlabs")

    def test_get_theme(self):
        self.assertEqual(self.mgr.get_theme(), "slate")

    def test_get_theme_default(self):
        del self.mock_settings["theme"]
        self.assertEqual(self.mgr.get_theme(), "flatly")

    def test_set_theme(self):
        self.mgr.set_theme("darkly")
        self.assertEqual(self.mock_settings["theme"], "darkly")


class TestSettingsManagerAgentAccessors(unittest.TestCase):
    """Tests for agent configuration accessors."""

    def setUp(self):
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            self.mgr = SettingsManager()

        self.mock_settings = {
            "agent_config": {
                "diagnostic": {
                    "enabled": True,
                    "model": "gpt-4",
                    "temperature": 0.1,
                },
                "synopsis": {
                    "enabled": False,
                },
            },
        }
        self.mgr._settings_module = self.mock_settings
        self.mgr._save = MagicMock()

    def tearDown(self):
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

    def test_get_agent_config(self):
        config = self.mgr.get_agent_config("diagnostic")
        self.assertEqual(config["model"], "gpt-4")
        self.assertTrue(config["enabled"])

    def test_get_agent_config_missing_agent(self):
        config = self.mgr.get_agent_config("nonexistent")
        self.assertEqual(config, {})

    def test_set_agent_config(self):
        new_config = {"enabled": True, "model": "gpt-3.5-turbo", "temperature": 0.5}
        self.mgr.set_agent_config("medication", new_config)
        self.assertEqual(
            self.mock_settings["agent_config"]["medication"]["model"],
            "gpt-3.5-turbo",
        )
        self.mgr._save.assert_called_once()

    def test_set_agent_config_creates_agent_config_key(self):
        """If agent_config doesn't exist yet, it should be created."""
        del self.mock_settings["agent_config"]
        self.mgr.set_agent_config("workflow", {"enabled": True})
        self.assertTrue(self.mock_settings["agent_config"]["workflow"]["enabled"])

    def test_is_agent_enabled_true(self):
        self.assertTrue(self.mgr.is_agent_enabled("diagnostic"))

    def test_is_agent_enabled_false(self):
        self.assertFalse(self.mgr.is_agent_enabled("synopsis"))

    def test_is_agent_enabled_missing_agent(self):
        self.assertFalse(self.mgr.is_agent_enabled("nonexistent"))

    def test_set_agent_enabled(self):
        self.mgr.set_agent_enabled("synopsis", True)
        self.assertTrue(
            self.mock_settings["agent_config"]["synopsis"]["enabled"]
        )


class TestSettingsManagerModelConfig(unittest.TestCase):
    """Tests for model configuration accessors."""

    def setUp(self):
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            self.mgr = SettingsManager()

        self.mock_settings = {
            "soap_note": {
                "model": "gpt-4",
                "temperature": 0.4,
                "icd_code_version": "ICD-10",
            },
            "refine_text": {
                "model": "gpt-3.5-turbo",
                "temperature": 0.0,
            },
        }
        self.mgr._settings_module = self.mock_settings
        self.mgr._save = MagicMock()

    def tearDown(self):
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

    def test_get_model_config(self):
        config = self.mgr.get_model_config("refine_text")
        self.assertEqual(config["model"], "gpt-3.5-turbo")
        self.assertEqual(config["temperature"], 0.0)

    def test_get_model_config_missing_domain(self):
        config = self.mgr.get_model_config("nonexistent_domain")
        self.assertEqual(config, {})

    def test_set_model_config(self):
        self.mgr.set_model_config("refine_text", {"model": "gpt-4o", "temperature": 0.1})
        self.assertEqual(self.mock_settings["refine_text"]["model"], "gpt-4o")
        self.mgr._save.assert_called_once()

    def test_get_soap_config(self):
        config = self.mgr.get_soap_config()
        self.assertEqual(config["icd_code_version"], "ICD-10")

    def test_set_soap_config(self):
        self.mgr.set_soap_config({"model": "gpt-4o", "temperature": 0.3})
        self.assertEqual(self.mock_settings["soap_note"]["model"], "gpt-4o")


class TestSettingsManagerFeatureFlags(unittest.TestCase):
    """Tests for feature flag accessors."""

    def setUp(self):
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            self.mgr = SettingsManager()

        self.mock_settings = {
            "quick_continue_mode": False,
            "autosave_enabled": True,
            "sidebar_collapsed": True,
        }
        self.mgr._settings_module = self.mock_settings
        self.mgr._save = MagicMock()

    def tearDown(self):
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

    def test_is_quick_continue_mode(self):
        self.assertFalse(self.mgr.is_quick_continue_mode())

    def test_is_quick_continue_mode_default(self):
        del self.mock_settings["quick_continue_mode"]
        self.assertTrue(self.mgr.is_quick_continue_mode())

    def test_get_quick_continue_mode_alias(self):
        self.assertFalse(self.mgr.get_quick_continue_mode())

    def test_set_quick_continue_mode(self):
        self.mgr.set_quick_continue_mode(True)
        self.assertTrue(self.mock_settings["quick_continue_mode"])

    def test_is_autosave_enabled(self):
        self.assertTrue(self.mgr.is_autosave_enabled())

    def test_set_autosave_enabled(self):
        self.mgr.set_autosave_enabled(False)
        self.assertFalse(self.mock_settings["autosave_enabled"])

    def test_is_sidebar_collapsed(self):
        self.assertTrue(self.mgr.is_sidebar_collapsed())

    def test_set_sidebar_collapsed(self):
        self.mgr.set_sidebar_collapsed(False)
        self.assertFalse(self.mock_settings["sidebar_collapsed"])


class TestSettingsManagerWindowState(unittest.TestCase):
    """Tests for window dimension accessors."""

    def setUp(self):
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            self.mgr = SettingsManager()

        self.mock_settings = {
            "window_width": 1400,
            "window_height": 900,
        }
        self.mgr._settings_module = self.mock_settings
        self.mgr._save = MagicMock()

    def tearDown(self):
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

    def test_get_window_dimensions(self):
        self.assertEqual(self.mgr.get_window_dimensions(), (1400, 900))

    def test_get_window_dimensions_default(self):
        self.mock_settings.clear()
        self.assertEqual(self.mgr.get_window_dimensions(), (0, 0))

    def test_set_window_dimensions(self):
        self.mgr.set_window_dimensions(1920, 1080)
        self.assertEqual(self.mock_settings["window_width"], 1920)
        self.assertEqual(self.mock_settings["window_height"], 1080)
        self.mgr._save.assert_called_once()


class TestSettingsManagerPersistence(unittest.TestCase):
    """Tests for save() and reload()."""

    def setUp(self):
        from settings.settings_manager import SettingsManager

        SettingsManager._instance = None

        with _patch_sm_get_logger():
            self.mgr = SettingsManager()

        self.mock_settings = {"ai_provider": "openai"}
        self.mgr._settings_module = self.mock_settings

    def tearDown(self):
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

    @patch("settings.settings_manager.SettingsManager._save")
    def test_save_calls_internal_save(self, mock_save):
        self.mgr.save()
        mock_save.assert_called_once()

    @patch("settings.settings.load_settings")
    def test_reload_resets_module_reference(self, mock_load):
        self.mgr.reload()
        mock_load.assert_called_once_with(force_refresh=True)
        self.assertIsNone(self.mgr._settings_module)

    def test_get_default_delegates_to_default_settings(self):
        """get_default should read from _DEFAULT_SETTINGS."""
        with patch("settings.settings._DEFAULT_SETTINGS", {"theme": "flatly"}):
            result = self.mgr.get_default("theme")
            self.assertEqual(result, "flatly")

    def test_get_default_missing_key(self):
        with patch("settings.settings._DEFAULT_SETTINGS", {}):
            result = self.mgr.get_default("nonexistent", "fallback")
            self.assertEqual(result, "fallback")


if __name__ == "__main__":
    unittest.main()
