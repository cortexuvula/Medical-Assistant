"""
Tests for src/managers/data_folder_manager.py

Covers DataFolderManager path properties, folder creation, migrate_existing_files,
and macOS bundle migration (_migrate_from_bundle).
"""

import os
import sys
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


# ---------------------------------------------------------------------------
# Helper — create a fresh DataFolderManager pointed at tmp_path
# ---------------------------------------------------------------------------

def _make_manager(tmp_path, frozen=False, platform="linux"):
    """Create a DataFolderManager with AppData inside tmp_path."""
    app_data = tmp_path / "AppData"

    # Patch sys.frozen and platform to control which code path is taken.
    frozen_attrs = {"frozen": True} if frozen else {}

    def fake_sys_getattr(name, default=None):
        return frozen_attrs.get(name, getattr(sys, name) if hasattr(sys, name) else default)

    with patch("managers.data_folder_manager.sys") as mock_sys, \
         patch("managers.data_folder_manager.get_logger", return_value=MagicMock()):
        mock_sys.frozen = frozen
        mock_sys.platform = platform
        mock_sys.executable = str(tmp_path / "MedicalAssistant")
        # Simulate __file__ chain from the module perspective
        from managers.data_folder_manager import DataFolderManager
        mgr = DataFolderManager.__new__(DataFolderManager)
        mgr._app_data_folder = app_data
        mgr._ensure_folders_exist()
    return mgr


# ===========================================================================
# Basic path properties
# ===========================================================================

class TestDataFolderManagerPaths:
    @pytest.fixture
    def mgr(self, tmp_path):
        return _make_manager(tmp_path)

    def test_app_data_folder_is_path(self, mgr):
        assert isinstance(mgr.app_data_folder, Path)

    def test_env_file_path_filename(self, mgr):
        assert mgr.env_file_path.name == ".env"
        assert mgr.env_file_path.parent == mgr.app_data_folder

    def test_settings_file_path_filename(self, mgr):
        assert mgr.settings_file_path.name == "settings.json"

    def test_vocabulary_file_path_filename(self, mgr):
        assert mgr.vocabulary_file_path.name == "vocabulary.json"

    def test_database_file_path_filename(self, mgr):
        assert mgr.database_file_path.name == "medical_assistant.db"

    def test_config_folder_name(self, mgr):
        assert mgr.config_folder.name == "config"
        assert mgr.config_folder.parent == mgr.app_data_folder

    def test_logs_folder_name(self, mgr):
        assert mgr.logs_folder.name == "logs"

    def test_data_folder_name(self, mgr):
        assert mgr.data_folder.name == "data"


# ===========================================================================
# _ensure_folders_exist
# ===========================================================================

class TestEnsureFoldersExist:
    @pytest.fixture
    def mgr(self, tmp_path):
        return _make_manager(tmp_path)

    def test_app_data_folder_created(self, mgr):
        assert mgr.app_data_folder.exists()
        assert mgr.app_data_folder.is_dir()

    def test_config_subfolder_created(self, mgr):
        assert mgr.config_folder.exists()

    def test_logs_subfolder_created(self, mgr):
        assert mgr.logs_folder.exists()

    def test_data_subfolder_created(self, mgr):
        assert mgr.data_folder.exists()


# ===========================================================================
# migrate_existing_files
# ===========================================================================

class TestMigrateExistingFiles:
    def _setup_manager_with_old_files(self, tmp_path):
        """Create a manager and put old-style files next to the module path."""
        mgr = _make_manager(tmp_path)
        # The old_dir in migrate_existing_files for non-frozen mode is
        # Path(__file__).parent — we need to mock __file__ to point to tmp_path.
        return mgr

    def test_migrates_env_file(self, tmp_path):
        mgr = _make_manager(tmp_path)
        old_dir = tmp_path / "old_location"
        old_dir.mkdir()
        old_env = old_dir / ".env"
        old_env.write_text("KEY=VALUE")
        new_env = mgr.app_data_folder / ".env"
        assert not new_env.exists()

        # Simulate migration by calling method with patched __file__
        with patch("managers.data_folder_manager.__file__", str(old_dir / "data_folder_manager.py")):
            # Patch sys.frozen to ensure it uses script path
            with patch("managers.data_folder_manager.sys") as mock_sys:
                mock_sys.frozen = False
                mgr.migrate_existing_files()

        # File should have been moved
        assert new_env.exists()
        assert not old_env.exists()

    def test_does_not_overwrite_existing_file(self, tmp_path):
        mgr = _make_manager(tmp_path)
        old_dir = tmp_path / "old_location"
        old_dir.mkdir()
        old_env = old_dir / ".env"
        old_env.write_text("OLD=VALUE")
        new_env = mgr.app_data_folder / ".env"
        new_env.write_text("NEW=VALUE")  # Already exists

        with patch("managers.data_folder_manager.__file__", str(old_dir / "data_folder_manager.py")), \
             patch("managers.data_folder_manager.sys") as mock_sys:
            mock_sys.frozen = False
            mgr.migrate_existing_files()

        # Existing file should be preserved unchanged
        assert new_env.read_text() == "NEW=VALUE"

    def test_migrates_config_folder_json_files(self, tmp_path):
        mgr = _make_manager(tmp_path)
        old_dir = tmp_path / "old_location"
        old_dir.mkdir()
        old_config = old_dir / "config"
        old_config.mkdir()
        cfg_file = old_config / "settings.json"
        cfg_file.write_text('{"key": "value"}')

        with patch("managers.data_folder_manager.__file__", str(old_dir / "data_folder_manager.py")), \
             patch("managers.data_folder_manager.sys") as mock_sys:
            mock_sys.frozen = False
            mgr.migrate_existing_files()

        new_cfg = mgr.config_folder / "settings.json"
        assert new_cfg.exists()


# ===========================================================================
# _migrate_from_bundle (macOS frozen mode)
# ===========================================================================

class TestMigrateFromBundle:
    def test_no_migration_when_old_dir_missing(self, tmp_path):
        """If old bundle AppData doesn't exist, no files are copied."""
        mgr = _make_manager(tmp_path)
        # Ensure no stale files show up
        new_env = mgr.app_data_folder / ".env"
        assert not new_env.exists()

        with patch("managers.data_folder_manager.sys") as mock_sys, \
             patch("managers.data_folder_manager.get_logger", return_value=MagicMock()):
            mock_sys.frozen = True
            mock_sys.platform = "darwin"
            mock_sys.executable = str(tmp_path / "FakeApp.app" / "Contents" / "MacOS" / "MedicalAssistant")
            mgr._migrate_from_bundle()

        # No files should have been created
        assert not new_env.exists()

    def test_migrates_files_from_old_bundle(self, tmp_path):
        """Files in old bundle AppData are copied to the new location."""
        exe_dir = tmp_path / "FakeApp.app" / "Contents" / "MacOS"
        exe_dir.mkdir(parents=True)
        old_appdata = exe_dir / "AppData"
        old_appdata.mkdir()
        old_env = old_appdata / ".env"
        old_env.write_text("MIGRATED=1")

        mgr = _make_manager(tmp_path)

        with patch("managers.data_folder_manager.sys") as mock_sys, \
             patch("managers.data_folder_manager.get_logger", return_value=MagicMock()):
            mock_sys.frozen = True
            mock_sys.platform = "darwin"
            mock_sys.executable = str(exe_dir / "MedicalAssistant")
            mgr._migrate_from_bundle()

        new_env = mgr.app_data_folder / ".env"
        assert new_env.exists()
        assert new_env.read_text() == "MIGRATED=1"

    def test_does_not_overwrite_existing_files(self, tmp_path):
        """Files that already exist in new location are not overwritten."""
        exe_dir = tmp_path / "FakeApp.app" / "Contents" / "MacOS"
        exe_dir.mkdir(parents=True)
        old_appdata = exe_dir / "AppData"
        old_appdata.mkdir()
        (old_appdata / ".env").write_text("OLD=1")

        mgr = _make_manager(tmp_path)
        # Pre-create the destination
        new_env = mgr.app_data_folder / ".env"
        new_env.write_text("EXISTING=1")

        with patch("managers.data_folder_manager.sys") as mock_sys, \
             patch("managers.data_folder_manager.get_logger", return_value=MagicMock()):
            mock_sys.frozen = True
            mock_sys.platform = "darwin"
            mock_sys.executable = str(exe_dir / "MedicalAssistant")
            mgr._migrate_from_bundle()

        assert new_env.read_text() == "EXISTING=1"


# ===========================================================================
# Singleton (module-level instance)
# ===========================================================================

class TestDataFolderManagerSingleton:
    def test_global_instance_exists(self):
        from managers.data_folder_manager import data_folder_manager
        assert data_folder_manager is not None

    def test_global_instance_is_data_folder_manager(self):
        from managers import data_folder_manager as module
        from managers.data_folder_manager import DataFolderManager
        assert isinstance(module.data_folder_manager, DataFolderManager)

    def test_global_instance_has_app_data_folder(self):
        from managers.data_folder_manager import data_folder_manager
        assert data_folder_manager.app_data_folder is not None
        assert isinstance(data_folder_manager.app_data_folder, Path)
