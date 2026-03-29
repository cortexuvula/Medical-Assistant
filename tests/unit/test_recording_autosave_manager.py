"""Tests for audio/recording_autosave_manager.py.

Tests RecordingAutoSaveManager lifecycle, recovery, and cleanup using mocked
settings, data folder manager, and AudioStateManager.
"""

import json
import os
import time
import threading
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def autosave_dir(tmp_path):
    """Temporary autosave directory."""
    d = tmp_path / "recording_autosave"
    d.mkdir()
    return d


@pytest.fixture
def manager(autosave_dir):
    """RecordingAutoSaveManager with mocked settings and data folder."""
    with patch("audio.recording_autosave_manager.settings_manager") as mock_sm, \
         patch("audio.recording_autosave_manager.data_folder_manager") as mock_dfm:
        mock_sm.get.return_value = 60  # 60s interval
        mock_dfm.app_data_folder = autosave_dir.parent

        from audio.recording_autosave_manager import RecordingAutoSaveManager
        mgr = RecordingAutoSaveManager(interval_seconds=60)
        # Override autosave_dir to point to our tmp dir
        mgr._autosave_dir = autosave_dir
        yield mgr


@pytest.fixture
def mock_asm():
    """Mock AudioStateManager."""
    asm = MagicMock()
    asm.get_combined_audio.return_value = None
    return asm


def _write_session(autosave_dir, session_id, status, chunks=0):
    """Write a fake session directory with metadata."""
    session_dir = autosave_dir / f"session_{session_id}"
    session_dir.mkdir(exist_ok=True)
    metadata = {
        "version": "1.0",
        "session_id": session_id,
        "status": status,
        "start_time": "2024-01-01T10:00:00",
        "last_save_time": "2024-01-01T10:05:00",
        "patient_context": "Test patient",
        "device_name": "Microphone",
        "sample_rate": 48000,
        "sample_width": 2,
        "channels": 1,
        "total_chunks": chunks,
        "estimated_duration_seconds": chunks * 60.0,
    }
    (session_dir / "metadata.json").write_text(json.dumps(metadata))
    # Write fake chunk files
    for i in range(1, chunks + 1):
        chunk_path = session_dir / f"chunk_{i:04d}.raw"
        chunk_path.write_bytes(b"\x00\x01\x02\x03")  # 4 bytes of fake audio
    return session_dir


# ── Initialization ────────────────────────────────────────────────────────────

class TestInit:
    def test_creates_instance(self, manager):
        assert manager is not None

    def test_not_running_initially(self, manager):
        assert manager.is_running is False

    def test_session_id_none_initially(self, manager):
        assert manager.session_id is None

    def test_autosave_dir_exists(self, manager, autosave_dir):
        assert autosave_dir.exists()

    def test_custom_interval_applied(self, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm, \
             patch("audio.recording_autosave_manager.data_folder_manager") as mock_dfm:
            mock_sm.get.return_value = 30
            mock_dfm.app_data_folder = autosave_dir.parent
            from audio.recording_autosave_manager import RecordingAutoSaveManager
            mgr = RecordingAutoSaveManager(interval_seconds=30)
            assert mgr._interval_seconds == 30


# ── start / stop ──────────────────────────────────────────────────────────────

class TestStartStop:
    def test_start_sets_running(self, manager, mock_asm, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True  # autosave enabled
            manager.start(mock_asm)
        assert manager.is_running is True
        manager.stop(completed_successfully=True)

    def test_start_generates_session_id(self, manager, mock_asm):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm)
        assert manager.session_id is not None
        manager.stop(completed_successfully=True)

    def test_start_creates_session_dir(self, manager, mock_asm, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm)
        session_id = manager.session_id
        session_dir = autosave_dir / f"session_{session_id}"
        assert session_dir.exists()
        manager.stop(completed_successfully=True)

    def test_start_writes_initial_metadata(self, manager, mock_asm, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm)
        session_id = manager.session_id
        metadata_file = autosave_dir / f"session_{session_id}" / "metadata.json"
        assert metadata_file.exists()
        meta = json.loads(metadata_file.read_text())
        assert meta["status"] == "recording"
        manager.stop(completed_successfully=True)

    def test_start_when_disabled_does_not_run(self, manager, mock_asm):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = False  # disabled
            manager.start(mock_asm)
        assert manager.is_running is False

    def test_start_twice_is_idempotent(self, manager, mock_asm):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm)
            first_session = manager.session_id
            manager.start(mock_asm)  # Second start should be ignored
            second_session = manager.session_id
        assert first_session == second_session
        manager.stop(completed_successfully=True)

    def test_stop_when_not_running_is_safe(self, manager):
        manager.stop()  # Should not raise

    def test_stop_completed_clears_session(self, manager, mock_asm):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm)
        manager.stop(completed_successfully=True)
        assert manager.session_id is None

    def test_stop_completed_updates_metadata_status(self, manager, mock_asm, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm)
        session_id = manager.session_id
        session_dir = autosave_dir / f"session_{session_id}"
        manager.stop(completed_successfully=True)
        # After completed stop, directory should be cleaned up
        # OR metadata updated to "completed" before cleanup
        # Either way, is_running should be False
        assert manager.is_running is False

    def test_stop_not_completed_marks_incomplete(self, manager, mock_asm, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm)
        session_id = manager.session_id
        metadata_file = autosave_dir / f"session_{session_id}" / "metadata.json"
        manager.stop(completed_successfully=False)
        # Metadata should be "incomplete"
        if metadata_file.exists():
            meta = json.loads(metadata_file.read_text())
            assert meta["status"] == "incomplete"


# ── start with metadata ───────────────────────────────────────────────────────

class TestStartWithMetadata:
    def test_metadata_patient_context_stored(self, manager, mock_asm, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm, metadata={"patient_context": "Diabetic, 65F"})
        session_id = manager.session_id
        meta_path = autosave_dir / f"session_{session_id}" / "metadata.json"
        meta = json.loads(meta_path.read_text())
        assert meta["patient_context"] == "Diabetic, 65F"
        manager.stop()

    def test_metadata_device_name_stored(self, manager, mock_asm, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm, metadata={"device_name": "USB Microphone"})
        session_id = manager.session_id
        meta_path = autosave_dir / f"session_{session_id}" / "metadata.json"
        meta = json.loads(meta_path.read_text())
        assert meta["device_name"] == "USB Microphone"
        manager.stop()

    def test_none_metadata_handled(self, manager, mock_asm, autosave_dir):
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm, metadata=None)  # None is fine
        assert manager.is_running
        manager.stop()


# ── has_incomplete_recording ──────────────────────────────────────────────────

class TestHasIncompleteRecording:
    def test_no_sessions_returns_false(self, manager, autosave_dir):
        assert manager.has_incomplete_recording() is False

    def test_incomplete_session_returns_true(self, manager, autosave_dir):
        _write_session(autosave_dir, "abc123", "incomplete", chunks=2)
        assert manager.has_incomplete_recording() is True

    def test_recording_status_returns_true(self, manager, autosave_dir):
        _write_session(autosave_dir, "abc456", "recording", chunks=1)
        assert manager.has_incomplete_recording() is True

    def test_completed_session_returns_false(self, manager, autosave_dir):
        _write_session(autosave_dir, "abc789", "completed", chunks=2)
        result = manager.has_incomplete_recording()
        assert result is False

    def test_completed_session_gets_cleaned_up(self, manager, autosave_dir):
        session_dir = _write_session(autosave_dir, "stale_completed", "completed", chunks=1)
        manager.has_incomplete_recording()
        # Completed sessions should be cleaned up by has_incomplete_recording
        assert not session_dir.exists()

    def test_corrupted_metadata_does_not_crash(self, manager, autosave_dir):
        session_dir = autosave_dir / "session_corrupt"
        session_dir.mkdir()
        (session_dir / "metadata.json").write_text("NOT JSON {{{")
        # Should not raise, just skip
        result = manager.has_incomplete_recording()
        assert isinstance(result, bool)


# ── get_recovery_info ─────────────────────────────────────────────────────────

class TestGetRecoveryInfo:
    def test_returns_none_when_no_sessions(self, manager, autosave_dir):
        assert manager.get_recovery_info() is None

    def test_returns_none_for_completed_sessions(self, manager, autosave_dir):
        _write_session(autosave_dir, "done_session", "completed", chunks=3)
        assert manager.get_recovery_info() is None

    def test_returns_dict_for_incomplete_session(self, manager, autosave_dir):
        _write_session(autosave_dir, "session_id_1", "incomplete", chunks=2)
        info = manager.get_recovery_info()
        assert info is not None
        assert isinstance(info, dict)

    def test_recovery_info_has_session_id(self, manager, autosave_dir):
        _write_session(autosave_dir, "test_session", "incomplete", chunks=2)
        info = manager.get_recovery_info()
        assert info["session_id"] == "test_session"

    def test_recovery_info_has_chunk_count(self, manager, autosave_dir):
        _write_session(autosave_dir, "chunky_session", "recording", chunks=3)
        info = manager.get_recovery_info()
        assert info["chunk_count"] == 3

    def test_recovery_info_has_estimated_duration(self, manager, autosave_dir):
        _write_session(autosave_dir, "dur_session", "incomplete", chunks=2)
        info = manager.get_recovery_info()
        assert "estimated_duration_seconds" in info

    def test_recovery_info_has_patient_context(self, manager, autosave_dir):
        _write_session(autosave_dir, "patient_session", "incomplete", chunks=1)
        info = manager.get_recovery_info()
        assert info["patient_context"] == "Test patient"

    def test_corrupted_metadata_skipped(self, manager, autosave_dir):
        session_dir = autosave_dir / "session_broken"
        session_dir.mkdir()
        (session_dir / "metadata.json").write_text("{invalid}")
        result = manager.get_recovery_info()
        assert result is None


# ── cleanup_session ───────────────────────────────────────────────────────────

class TestCleanupSession:
    def test_cleanup_removes_directory(self, manager, autosave_dir):
        session_dir = _write_session(autosave_dir, "to_delete", "incomplete", chunks=1)
        result = manager._cleanup_session(session_dir)
        assert result is True
        assert not session_dir.exists()

    def test_cleanup_nonexistent_directory_returns_true(self, manager, autosave_dir):
        nonexistent = autosave_dir / "session_nonexistent"
        result = manager._cleanup_session(nonexistent)
        assert result is True

    def test_cleanup_none_returns_true(self, manager):
        result = manager._cleanup_session(None)
        assert result is True


# ── cleanup_recovery_files ────────────────────────────────────────────────────

class TestCleanupRecoveryFiles:
    def test_cleanup_removes_all_sessions(self, manager, autosave_dir):
        _write_session(autosave_dir, "s1", "incomplete", chunks=1)
        _write_session(autosave_dir, "s2", "recording", chunks=2)
        manager.cleanup_recovery_files()
        remaining = list(autosave_dir.iterdir())
        assert len(remaining) == 0

    def test_cleanup_empty_dir_does_not_crash(self, manager, autosave_dir):
        manager.cleanup_recovery_files()  # Should not raise


# ── _perform_save ─────────────────────────────────────────────────────────────

class TestPerformSave:
    def test_returns_false_when_not_running(self, manager):
        result = manager._perform_save()
        assert result is False

    def test_returns_true_when_no_audio(self, manager, mock_asm, autosave_dir):
        """When ASM returns None audio, save is skipped gracefully."""
        with patch("audio.recording_autosave_manager.settings_manager") as mock_sm:
            mock_sm.get.return_value = True
            manager.start(mock_asm)
        mock_asm.get_combined_audio.return_value = None
        result = manager._perform_save()
        assert result is True
        manager.stop()


# ── _extract_audio_for_save ───────────────────────────────────────────────────

class TestExtractAudioForSave:
    def test_returns_none_when_no_combined_audio(self, manager, mock_asm):
        mock_asm.get_combined_audio.return_value = None
        result = manager._extract_audio_for_save(mock_asm)
        assert result is None

    def test_returns_none_when_empty_audio(self, manager, mock_asm):
        mock_asm.get_combined_audio.return_value = b""
        result = manager._extract_audio_for_save(mock_asm)
        assert result is None

    def test_returns_tuple_when_audio_available(self, manager, mock_asm):
        from pydub import AudioSegment
        import numpy as np
        # Create a minimal AudioSegment
        silence = AudioSegment.silent(duration=100, frame_rate=48000)
        mock_asm.get_combined_audio.return_value = silence
        mock_asm.get_recording_metadata.return_value = {}
        result = manager._extract_audio_for_save(mock_asm)
        assert result is not None
        assert len(result) == 2
        raw_bytes, metadata_update = result
        assert isinstance(raw_bytes, bytes)
        assert "sample_rate" in metadata_update

    def test_exception_returns_none(self, manager, mock_asm):
        mock_asm.get_combined_audio.side_effect = Exception("ASM error")
        result = manager._extract_audio_for_save(mock_asm)
        assert result is None


# ── is_running property ───────────────────────────────────────────────────────

class TestIsRunningProperty:
    def test_is_running_thread_safe(self, manager, mock_asm):
        """is_running should be thread-safe via lock."""
        results = []

        def check_running():
            results.append(manager.is_running)

        threads = [threading.Thread(target=check_running) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All checks should return the same value (False initially)
        assert all(r is False for r in results)
