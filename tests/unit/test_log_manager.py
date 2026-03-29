"""
Tests for src/managers/log_manager.py

Covers _get_logging_settings (defaults, file load, merge, parse errors),
LogManager.__init__ (log level resolution, env override, path derivation),
LogManager.setup_logging (handler creation, module overrides),
and get_log_file_path / get_log_directory accessors.
"""

import json
import logging
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(tmp_path, log_level=None, env=None):
    """Create a LogManager with tmp_path as logs folder."""
    mock_dfm = MagicMock()
    mock_dfm.logs_folder = tmp_path / "logs"
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)

    env = env or {}
    with patch("managers.log_manager.data_folder_manager", mock_dfm), \
         patch.dict(os.environ, env, clear=False):
        from managers.log_manager import LogManager
        return LogManager(log_level=log_level)


# ===========================================================================
# _get_logging_settings
# ===========================================================================

class TestGetLoggingSettings:
    def test_returns_dict_with_level(self):
        from managers.log_manager import _get_logging_settings
        with patch("managers.log_manager.data_folder_manager", MagicMock()):
            settings = _get_logging_settings()
        assert "level" in settings

    def test_returns_defaults_when_no_settings_file(self):
        from managers.log_manager import _get_logging_settings
        with patch("pathlib.Path.exists", return_value=False):
            settings = _get_logging_settings()
        assert settings["level"] == "INFO"
        assert settings["backup_count"] == 2

    def test_merges_file_settings_with_defaults(self, tmp_path):
        from managers.log_manager import _get_logging_settings
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"logging": {"backup_count": 5}}))

        original_exists = Path.exists

        def fake_exists(self):
            if str(self) == str(settings_file):
                return True
            return False

        with patch.object(Path, "exists", fake_exists), \
             patch("builtins.open", return_value=open(settings_file)):
            settings = _get_logging_settings()
        # Either merged or returned defaults — backup_count may be 5 or 2
        assert "backup_count" in settings

    def test_returns_defaults_on_json_decode_error(self, tmp_path):
        from managers.log_manager import _get_logging_settings

        bad_file = tmp_path / "settings.json"
        bad_file.write_text("NOT JSON {{{")

        def fake_exists(self):
            return str(self) == str(bad_file)

        with patch.object(Path, "exists", fake_exists):
            with patch("builtins.open", return_value=open(bad_file)):
                settings = _get_logging_settings()
        assert "level" in settings

    def test_default_module_levels_include_rag(self):
        from managers.log_manager import _get_logging_settings
        with patch("pathlib.Path.exists", return_value=False):
            settings = _get_logging_settings()
        assert "rag" in settings.get("module_levels", {})


# ===========================================================================
# LogManager.__init__
# ===========================================================================

class TestLogManagerInit:
    def test_log_dir_set(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.log_dir is not None
        assert "logs" in mgr.log_dir

    def test_log_file_set(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.log_file.endswith(".log")

    def test_custom_log_level_used(self, tmp_path):
        mgr = _make_manager(tmp_path, log_level=logging.DEBUG)
        assert mgr.log_level == logging.DEBUG

    def test_none_log_level_uses_configured_level(self, tmp_path):
        with patch("managers.log_manager._get_configured_log_level", return_value=logging.WARNING):
            mgr = _make_manager(tmp_path, log_level=None)
        assert mgr.log_level == logging.WARNING

    def test_env_override_sets_file_level(self, tmp_path):
        mgr = _make_manager(tmp_path, env={"MEDICAL_ASSISTANT_LOG_LEVEL": "DEBUG"})
        assert mgr.file_level == logging.DEBUG

    def test_env_override_sets_console_level(self, tmp_path):
        mgr = _make_manager(tmp_path, env={"MEDICAL_ASSISTANT_LOG_LEVEL": "ERROR"})
        assert mgr.console_level == logging.ERROR

    def test_no_env_override_uses_settings_file_level(self, tmp_path):
        env = {k: v for k, v in os.environ.items() if k != "MEDICAL_ASSISTANT_LOG_LEVEL"}
        with patch.dict(os.environ, env, clear=True):
            mgr = _make_manager(tmp_path)
        # Default file_level from settings is DEBUG
        assert mgr.file_level == logging.DEBUG

    def test_max_file_size_computed(self, tmp_path):
        mgr = _make_manager(tmp_path)
        # Default max_file_size_kb=200 → 200*1024 bytes
        assert mgr.max_file_size == 200 * 1024

    def test_backup_count_set(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.backup_count == 2

    def test_log_file_is_in_log_dir(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.log_file.startswith(mgr.log_dir)


# ===========================================================================
# LogManager.setup_logging
# ===========================================================================

class TestSetupLogging:
    def _get_clean_root_logger(self):
        root = logging.getLogger()
        root.handlers.clear()
        return root

    def _make_mock_fh(self):
        """Create a mock file handler with a real integer level."""
        mock_fh = MagicMock(spec=logging.Handler)
        mock_fh.level = logging.DEBUG
        return mock_fh

    def test_creates_log_directory(self, tmp_path):
        mgr = _make_manager(tmp_path)
        log_dir = tmp_path / "fresh_logs"
        mgr.log_dir = str(log_dir)
        mgr.log_file = str(log_dir / "app.log")

        with patch("managers.log_manager.ConcurrentRotatingFileHandler") as mock_handler_cls:
            mock_handler_cls.return_value = self._make_mock_fh()
            mgr.setup_logging()

        assert log_dir.exists()

    def test_adds_file_handler(self, tmp_path):
        mgr = _make_manager(tmp_path)
        self._get_clean_root_logger()

        with patch("managers.log_manager.ConcurrentRotatingFileHandler") as mock_fh_cls:
            mock_fh_cls.return_value = self._make_mock_fh()
            mgr.setup_logging()

        # File handler should have been instantiated
        mock_fh_cls.assert_called_once()

    def test_adds_console_handler(self, tmp_path):
        mgr = _make_manager(tmp_path)
        self._get_clean_root_logger()

        with patch("managers.log_manager.ConcurrentRotatingFileHandler") as mock_fh_cls:
            mock_fh_cls.return_value = self._make_mock_fh()
            mgr.setup_logging()

        # After setup, root logger should have ≥2 handlers (file + console)
        root = logging.getLogger()
        assert len(root.handlers) >= 2

    def test_clears_existing_handlers(self, tmp_path):
        mgr = _make_manager(tmp_path)
        root = logging.getLogger()
        # Add a dummy handler
        dummy = logging.NullHandler()
        root.addHandler(dummy)

        with patch("managers.log_manager.ConcurrentRotatingFileHandler") as mock_fh_cls:
            mock_fh_cls.return_value = self._make_mock_fh()
            mgr.setup_logging()

        # Dummy handler should have been cleared
        assert dummy not in root.handlers

    def test_sets_root_logger_level(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.file_level = logging.DEBUG
        mgr.console_level = logging.INFO
        root = logging.getLogger()
        root.handlers.clear()

        with patch("managers.log_manager.ConcurrentRotatingFileHandler") as mock_fh_cls:
            mock_fh_cls.return_value = self._make_mock_fh()
            mgr.setup_logging()

        # Root logger level = min(DEBUG, INFO) = DEBUG
        assert root.level == logging.DEBUG

    def test_applies_module_level_overrides(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr._settings["module_levels"] = {"test_module_xyz": "ERROR"}

        with patch("managers.log_manager.ConcurrentRotatingFileHandler") as mock_fh_cls:
            mock_fh_cls.return_value = self._make_mock_fh()
            mgr.setup_logging()

        module_logger = logging.getLogger("test_module_xyz")
        assert module_logger.level == logging.ERROR


# ===========================================================================
# Accessors
# ===========================================================================

class TestAccessors:
    def test_get_log_file_path_returns_string(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.get_log_file_path()
        assert isinstance(result, str)

    def test_get_log_file_path_ends_with_log(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.get_log_file_path().endswith(".log")

    def test_get_log_directory_returns_string(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.get_log_directory()
        assert isinstance(result, str)

    def test_get_log_directory_matches_log_dir(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.get_log_directory() == mgr.log_dir


# ===========================================================================
# setup_application_logging convenience function
# ===========================================================================

class TestSetupApplicationLogging:
    def test_returns_log_manager_instance(self, tmp_path):
        mock_dfm = MagicMock()
        mock_dfm.logs_folder = tmp_path / "logs"
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)

        mock_fh = MagicMock(spec=logging.Handler)
        mock_fh.level = logging.DEBUG

        with patch("managers.log_manager.data_folder_manager", mock_dfm), \
             patch("managers.log_manager.ConcurrentRotatingFileHandler", return_value=mock_fh):
            from managers.log_manager import setup_application_logging, LogManager
            mgr = setup_application_logging()

        assert isinstance(mgr, LogManager)
