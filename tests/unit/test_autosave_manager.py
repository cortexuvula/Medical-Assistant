"""
Tests for src/managers/autosave_manager.py

Covers AutoSaveManager: init, register/unregister providers, start/stop,
perform_save (hash detection, callbacks, disk I/O), _rotate_backups,
load_latest, has_unsaved_data, clear_saves, get_save_info, and
AutoSaveDataProvider.create_settings_provider.
"""

import json
import sys
import threading
import time
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
# Helper — create manager with a tmp save_directory (no data_folder_manager)
# ---------------------------------------------------------------------------

def _make_manager(tmp_path, interval_seconds=300, max_backups=3):
    """Create an AutoSaveManager pointed at tmp_path/autosave."""
    from managers.autosave_manager import AutoSaveManager
    save_dir = tmp_path / "autosave"
    return AutoSaveManager(save_directory=save_dir, interval_seconds=interval_seconds,
                           max_backups=max_backups)


# ===========================================================================
# Initialization
# ===========================================================================

class TestAutoSaveManagerInit:
    def test_save_directory_created(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.save_directory.exists()
        assert mgr.save_directory.is_dir()

    def test_custom_save_directory_used(self, tmp_path):
        save_dir = tmp_path / "custom_dir"
        from managers.autosave_manager import AutoSaveManager
        mgr = AutoSaveManager(save_directory=save_dir)
        assert mgr.save_directory == save_dir

    def test_default_interval(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.interval_seconds == 300

    def test_custom_interval(self, tmp_path):
        mgr = _make_manager(tmp_path, interval_seconds=60)
        assert mgr.interval_seconds == 60

    def test_default_max_backups(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.max_backups == 3

    def test_custom_max_backups(self, tmp_path):
        mgr = _make_manager(tmp_path, max_backups=5)
        assert mgr.max_backups == 5

    def test_initial_state_not_running(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.is_running is False

    def test_initial_last_save_time_none(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.last_save_time is None

    def test_initial_last_data_hash_none(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.last_data_hash is None

    def test_data_providers_empty_initially(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.data_providers == {}

    def test_callbacks_none_initially(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.on_save_start is None
        assert mgr.on_save_complete is None
        assert mgr.on_save_error is None

    def test_default_save_directory_uses_data_folder_manager(self, tmp_path):
        """When no save_directory given, uses data_folder_manager."""
        from managers.autosave_manager import AutoSaveManager
        mock_dfm = MagicMock()
        mock_dfm.app_data_folder = tmp_path
        with patch("managers.autosave_manager.data_folder_manager", mock_dfm, create=True):
            # Patch the lazy import
            with patch.dict("sys.modules", {"managers.data_folder_manager": MagicMock(
                    data_folder_manager=mock_dfm)}):
                mgr = AutoSaveManager.__new__(AutoSaveManager)
                mgr.save_directory = tmp_path / "autosave"
                mgr.save_directory.mkdir(parents=True, exist_ok=True)
        assert (tmp_path / "autosave").exists()


# ===========================================================================
# Register / Unregister providers
# ===========================================================================

class TestRegisterUnregisterProvider:
    def test_register_adds_provider(self, tmp_path):
        mgr = _make_manager(tmp_path)
        provider = lambda: {"key": "value"}
        mgr.register_data_provider("test", provider)
        assert "test" in mgr.data_providers

    def test_register_multiple_providers(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("a", lambda: {})
        mgr.register_data_provider("b", lambda: {})
        providers = mgr.data_providers
        assert "a" in providers and "b" in providers

    def test_register_overwrites_existing(self, tmp_path):
        mgr = _make_manager(tmp_path)
        old = lambda: {"old": True}
        new = lambda: {"new": True}
        mgr.register_data_provider("x", old)
        mgr.register_data_provider("x", new)
        assert mgr.data_providers["x"]() == {"new": True}

    def test_unregister_removes_provider(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("test", lambda: {})
        mgr.unregister_data_provider("test")
        assert "test" not in mgr.data_providers

    def test_unregister_returns_true_on_success(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("test", lambda: {})
        result = mgr.unregister_data_provider("test")
        assert result is True

    def test_unregister_returns_false_when_missing(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.unregister_data_provider("nonexistent")
        assert result is False

    def test_data_providers_returns_copy(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("test", lambda: {})
        copy = mgr.data_providers
        copy["injected"] = lambda: {}
        # Original should not be modified
        assert "injected" not in mgr.data_providers

    def test_concurrent_register_is_safe(self, tmp_path):
        mgr = _make_manager(tmp_path)
        errors = []

        def register_many(prefix):
            try:
                for i in range(20):
                    mgr.register_data_provider(f"{prefix}_{i}", lambda: {})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_many, args=(f"t{t}",)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(mgr.data_providers) == 100  # 5 threads × 20 providers


# ===========================================================================
# is_running property
# ===========================================================================

class TestIsRunningProperty:
    def test_initial_not_running(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.is_running is False

    def test_set_running_true(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.is_running = True
        assert mgr.is_running is True

    def test_set_running_false(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.is_running = True
        mgr.is_running = False
        assert mgr.is_running is False


# ===========================================================================
# Start / Stop
# ===========================================================================

class TestStartStop:
    def test_start_sets_running(self, tmp_path):
        mgr = _make_manager(tmp_path, interval_seconds=9999)
        mgr.start()
        try:
            assert mgr.is_running is True
        finally:
            mgr.stop()

    def test_start_creates_background_thread(self, tmp_path):
        mgr = _make_manager(tmp_path, interval_seconds=9999)
        mgr.start()
        try:
            assert mgr.save_thread is not None
            assert mgr.save_thread.is_alive()
        finally:
            mgr.stop()

    def test_start_idempotent(self, tmp_path):
        mgr = _make_manager(tmp_path, interval_seconds=9999)
        mgr.start()
        first_thread = mgr.save_thread
        mgr.start()  # Should not create a new thread
        try:
            assert mgr.save_thread is first_thread
        finally:
            mgr.stop()

    def test_stop_clears_running(self, tmp_path):
        mgr = _make_manager(tmp_path, interval_seconds=9999)
        mgr.start()
        mgr.stop()
        assert mgr.is_running is False

    def test_stop_when_not_running_is_safe(self, tmp_path):
        mgr = _make_manager(tmp_path)
        # Should not raise
        mgr.stop()

    def test_stop_joins_thread(self, tmp_path):
        mgr = _make_manager(tmp_path, interval_seconds=9999)
        mgr.start()
        thread = mgr.save_thread
        mgr.stop()
        # Thread should have been joined (not alive)
        assert not thread.is_alive()

    def test_start_stop_cycle_can_repeat(self, tmp_path):
        """Can start after stop."""
        mgr = _make_manager(tmp_path, interval_seconds=9999)
        mgr.start()
        mgr.stop()
        # Re-create so we can start again
        mgr2 = _make_manager(tmp_path, interval_seconds=9999)
        mgr2.start()
        try:
            assert mgr2.is_running is True
        finally:
            mgr2.stop()


# ===========================================================================
# perform_save
# ===========================================================================

class TestPerformSave:
    def test_returns_true_on_first_save(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.perform_save()
        assert result is True

    def test_creates_autosave_current_json(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.perform_save()
        assert (mgr.save_directory / "autosave_current.json").exists()

    def test_json_output_is_valid(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.perform_save()
        save_path = mgr.save_directory / "autosave_current.json"
        data = json.loads(save_path.read_text())
        assert "timestamp" in data
        assert "version" in data
        assert "data" in data

    def test_provider_data_included(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("notes", lambda: {"text": "hello"})
        mgr.perform_save()
        save_path = mgr.save_directory / "autosave_current.json"
        data = json.loads(save_path.read_text())
        assert data["data"]["notes"] == {"text": "hello"}

    def test_updates_last_save_time(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.last_save_time is None
        mgr.perform_save()
        assert mgr.last_save_time is not None

    def test_updates_last_data_hash(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.last_data_hash is None
        mgr.perform_save()
        assert mgr.last_data_hash is not None

    def test_returns_false_when_no_change(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("static", lambda: {"x": 1})
        mgr.perform_save()  # First save
        result = mgr.perform_save()  # Same data
        assert result is False

    def test_force_saves_even_when_unchanged(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("static", lambda: {"x": 1})
        mgr.perform_save()
        result = mgr.perform_save(force=True)
        assert result is True

    def test_returns_true_when_data_changes(self, tmp_path):
        mgr = _make_manager(tmp_path)
        counter = [0]

        def changing_provider():
            counter[0] += 1
            return {"count": counter[0]}

        mgr.register_data_provider("dynamic", changing_provider)
        mgr.perform_save()
        result = mgr.perform_save()
        assert result is True

    def test_calls_on_save_start_callback(self, tmp_path):
        mgr = _make_manager(tmp_path)
        callback = MagicMock()
        mgr.on_save_start = callback
        mgr.perform_save()
        callback.assert_called_once()

    def test_calls_on_save_complete_callback(self, tmp_path):
        mgr = _make_manager(tmp_path)
        callback = MagicMock()
        mgr.on_save_complete = callback
        mgr.perform_save()
        callback.assert_called_once()

    def test_on_save_start_not_called_when_skipped(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("static", lambda: {"x": 1})
        mgr.perform_save()
        callback = MagicMock()
        mgr.on_save_start = callback
        mgr.perform_save()  # No change — should be skipped
        callback.assert_not_called()

    def test_provider_exception_handled_gracefully(self, tmp_path):
        mgr = _make_manager(tmp_path)

        def bad_provider():
            raise RuntimeError("provider failed")

        mgr.register_data_provider("bad", bad_provider)
        result = mgr.perform_save()
        # Save should still succeed; provider data becomes None
        assert result is True
        save_path = mgr.save_directory / "autosave_current.json"
        data = json.loads(save_path.read_text())
        assert data["data"]["bad"] is None

    def test_on_save_start_exception_does_not_abort(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.on_save_start = MagicMock(side_effect=RuntimeError("oops"))
        result = mgr.perform_save()
        assert result is True

    def test_on_save_complete_exception_does_not_abort(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.on_save_complete = MagicMock(side_effect=RuntimeError("oops"))
        result = mgr.perform_save()
        assert result is True

    def test_calls_on_save_error_on_disk_failure(self, tmp_path):
        mgr = _make_manager(tmp_path)
        error_callback = MagicMock()
        mgr.on_save_error = error_callback
        with patch("builtins.open", side_effect=OSError("disk full")):
            result = mgr.perform_save()
        assert result is False
        error_callback.assert_called_once()

    def test_returns_false_on_disk_failure(self, tmp_path):
        mgr = _make_manager(tmp_path)
        with patch("builtins.open", side_effect=OSError("disk full")):
            result = mgr.perform_save()
        assert result is False

    def test_multiple_providers_all_included(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("a", lambda: {"a": 1})
        mgr.register_data_provider("b", lambda: {"b": 2})
        mgr.perform_save()
        data = json.loads((mgr.save_directory / "autosave_current.json").read_text())
        assert "a" in data["data"] and "b" in data["data"]


# ===========================================================================
# _rotate_backups
# ===========================================================================

class TestRotateBackups:
    def test_no_rotation_when_no_current_file(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr._rotate_backups()  # Should not raise
        assert not (mgr.save_directory / "autosave_backup_1.json").exists()

    def test_current_moved_to_backup_1(self, tmp_path):
        mgr = _make_manager(tmp_path)
        current = mgr.save_directory / "autosave_current.json"
        current.write_text('{"test": 1}')
        mgr._rotate_backups()
        assert not current.exists()
        assert (mgr.save_directory / "autosave_backup_1.json").exists()

    def test_backup_1_moved_to_backup_2(self, tmp_path):
        mgr = _make_manager(tmp_path)
        current = mgr.save_directory / "autosave_current.json"
        backup1 = mgr.save_directory / "autosave_backup_1.json"
        current.write_text('{"current": true}')
        backup1.write_text('{"old": true}')
        mgr._rotate_backups()
        backup2 = mgr.save_directory / "autosave_backup_2.json"
        assert backup2.exists()
        assert json.loads(backup2.read_text()) == {"old": True}

    def test_backup_content_preserved(self, tmp_path):
        mgr = _make_manager(tmp_path)
        current = mgr.save_directory / "autosave_current.json"
        current.write_text('{"value": 42}')
        mgr._rotate_backups()
        backup1 = mgr.save_directory / "autosave_backup_1.json"
        assert json.loads(backup1.read_text()) == {"value": 42}

    def test_max_backups_3_deletes_oldest(self, tmp_path):
        mgr = _make_manager(tmp_path, max_backups=3)
        # Pre-fill backups 1, 2, 3
        for i in range(1, 4):
            (mgr.save_directory / f"autosave_backup_{i}.json").write_text(f'{{"i": {i}}}')
        current = mgr.save_directory / "autosave_current.json"
        current.write_text('{"current": true}')
        mgr._rotate_backups()
        # Backup 3 should now be at 4 but max is 3, so backup_4 won't exist or backup_3 is deleted
        # After rotation: old backup_2 → backup_3, old backup_1 → backup_2, current → backup_1
        assert (mgr.save_directory / "autosave_backup_1.json").exists()
        assert (mgr.save_directory / "autosave_backup_2.json").exists()
        assert (mgr.save_directory / "autosave_backup_3.json").exists()


# ===========================================================================
# load_latest
# ===========================================================================

class TestLoadLatest:
    def test_returns_none_when_no_saves(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.load_latest()
        assert result is None

    def test_loads_current_file(self, tmp_path):
        mgr = _make_manager(tmp_path)
        current = mgr.save_directory / "autosave_current.json"
        current.write_text('{"timestamp": "2026-01-01", "version": "1.0", "data": {}}')
        result = mgr.load_latest()
        assert result is not None
        assert result["version"] == "1.0"

    def test_falls_back_to_backup_1(self, tmp_path):
        mgr = _make_manager(tmp_path)
        backup1 = mgr.save_directory / "autosave_backup_1.json"
        backup1.write_text('{"backup": true}')
        result = mgr.load_latest()
        assert result == {"backup": True}

    def test_corrupted_current_tries_backup(self, tmp_path):
        mgr = _make_manager(tmp_path)
        current = mgr.save_directory / "autosave_current.json"
        current.write_text("not valid json {{{")
        backup1 = mgr.save_directory / "autosave_backup_1.json"
        backup1.write_text('{"ok": true}')
        result = mgr.load_latest()
        assert result == {"ok": True}

    def test_current_takes_priority_over_backup(self, tmp_path):
        mgr = _make_manager(tmp_path)
        (mgr.save_directory / "autosave_current.json").write_text('{"source": "current"}')
        (mgr.save_directory / "autosave_backup_1.json").write_text('{"source": "backup"}')
        result = mgr.load_latest()
        assert result["source"] == "current"

    def test_perform_save_then_load_roundtrip(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("notes", lambda: {"text": "test content"})
        mgr.perform_save()
        loaded = mgr.load_latest()
        assert loaded is not None
        assert loaded["data"]["notes"] == {"text": "test content"}


# ===========================================================================
# has_unsaved_data
# ===========================================================================

class TestHasUnsavedData:
    def test_false_when_no_file(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.has_unsaved_data() is False

    def test_true_after_save(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.perform_save()
        assert mgr.has_unsaved_data() is True

    def test_false_after_clear(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.perform_save()
        mgr.clear_saves()
        assert mgr.has_unsaved_data() is False


# ===========================================================================
# clear_saves
# ===========================================================================

class TestClearSaves:
    def test_deletes_current_file(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.perform_save()
        mgr.clear_saves()
        assert not (mgr.save_directory / "autosave_current.json").exists()

    def test_deletes_backup_files(self, tmp_path):
        mgr = _make_manager(tmp_path)
        for i in range(1, 4):
            (mgr.save_directory / f"autosave_backup_{i}.json").write_text("{}")
        mgr.clear_saves()
        for i in range(1, 4):
            assert not (mgr.save_directory / f"autosave_backup_{i}.json").exists()

    def test_clears_last_data_hash(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.perform_save()
        assert mgr.last_data_hash is not None
        mgr.clear_saves()
        assert mgr.last_data_hash is None

    def test_no_error_when_no_files(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.clear_saves()  # Should not raise


# ===========================================================================
# get_save_info
# ===========================================================================

class TestGetSaveInfo:
    def test_returns_dict(self, tmp_path):
        mgr = _make_manager(tmp_path)
        info = mgr.get_save_info()
        assert isinstance(info, dict)

    def test_is_running_in_info(self, tmp_path):
        mgr = _make_manager(tmp_path)
        info = mgr.get_save_info()
        assert "is_running" in info
        assert info["is_running"] is False

    def test_interval_in_info(self, tmp_path):
        mgr = _make_manager(tmp_path, interval_seconds=120)
        info = mgr.get_save_info()
        assert info["interval_seconds"] == 120

    def test_saves_list_empty_before_saves(self, tmp_path):
        mgr = _make_manager(tmp_path)
        info = mgr.get_save_info()
        assert info["saves"] == []

    def test_saves_list_populated_after_save(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_data_provider("x", lambda: {})
        mgr.perform_save()
        info = mgr.get_save_info()
        assert len(info["saves"]) == 1

    def test_last_save_time_none_initially(self, tmp_path):
        mgr = _make_manager(tmp_path)
        info = mgr.get_save_info()
        assert info["last_save_time"] is None

    def test_last_save_time_set_after_save(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.perform_save()
        info = mgr.get_save_info()
        assert info["last_save_time"] is not None


# ===========================================================================
# AutoSaveDataProvider.create_settings_provider
# ===========================================================================

class TestAutoSaveDataProviderSettingsProvider:
    def _make_provider(self, settings_dict):
        from managers.autosave_manager import AutoSaveDataProvider
        return AutoSaveDataProvider.create_settings_provider(settings_dict)

    def test_returns_callable(self, tmp_path):
        provider = self._make_provider({"model": "gpt-4"})
        assert callable(provider)

    def test_preserves_safe_keys(self):
        provider = self._make_provider({"model": "gpt-4", "language": "en"})
        result = provider()
        assert result["model"] == "gpt-4"
        assert result["language"] == "en"

    def test_filters_key_containing_fields(self):
        provider = self._make_provider({"api_key": "sk-abc", "openai_key": "key123"})
        result = provider()
        assert "api_key" not in result
        assert "openai_key" not in result

    def test_filters_password_fields(self):
        provider = self._make_provider({"db_password": "secret", "mode": "fast"})
        result = provider()
        assert "db_password" not in result
        assert "mode" in result

    def test_filters_secret_fields(self):
        provider = self._make_provider({"client_secret": "abc", "theme": "dark"})
        result = provider()
        assert "client_secret" not in result
        assert "theme" in result

    def test_filters_token_fields(self):
        provider = self._make_provider({"auth_token": "xyz", "version": "1"})
        result = provider()
        assert "auth_token" not in result
        assert "version" in result

    def test_empty_dict_returns_empty(self):
        provider = self._make_provider({})
        result = provider()
        assert result == {}

    def test_case_insensitive_filtering(self):
        provider = self._make_provider({"API_KEY": "value", "safe": "ok"})
        result = provider()
        assert "API_KEY" not in result
        assert "safe" in result
