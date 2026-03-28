"""Tests for utils.file_utils — file operation utilities."""

import os
import pytest
from unittest.mock import patch

from utils.file_utils import (
    temp_audio_file,
    temp_file,
    safe_delete_file,
    ensure_directory_exists,
    get_safe_filename,
)


class TestTempAudioFile:
    def test_creates_file_that_exists(self):
        with temp_audio_file() as path:
            assert os.path.exists(path)

    def test_file_deleted_after_context_exit(self):
        with temp_audio_file() as path:
            saved_path = path
        assert not os.path.exists(saved_path)

    def test_default_suffix_is_wav(self):
        with temp_audio_file() as path:
            assert path.endswith(".wav")

    def test_custom_suffix(self):
        with temp_audio_file(suffix=".mp3") as path:
            assert path.endswith(".mp3")

    def test_default_prefix(self):
        with temp_audio_file() as path:
            basename = os.path.basename(path)
            assert basename.startswith("medical_audio_")

    def test_cleanup_on_exception(self):
        saved_path = None
        with pytest.raises(ValueError):
            with temp_audio_file() as path:
                saved_path = path
                raise ValueError("deliberate error")
        assert saved_path is not None
        assert not os.path.exists(saved_path)


class TestTempFile:
    def test_creates_and_deletes(self):
        with temp_file(suffix=".txt") as path:
            saved_path = path
            assert os.path.exists(path)
        assert not os.path.exists(saved_path)

    def test_default_prefix(self):
        with temp_file() as path:
            basename = os.path.basename(path)
            assert basename.startswith("medical_temp_")


class TestSafeDeleteFile:
    def test_deletes_existing_file(self, tmp_path):
        f = tmp_path / "to_delete.txt"
        f.write_text("data")
        assert safe_delete_file(str(f)) is True
        assert not f.exists()

    def test_nonexistent_file_returns_true(self, tmp_path):
        assert safe_delete_file(str(tmp_path / "nope.txt")) is True

    def test_empty_path_returns_true(self):
        assert safe_delete_file("") is True

    @patch("utils.file_utils.os.remove", side_effect=OSError("perm"))
    @patch("utils.file_utils.os.path.exists", return_value=True)
    def test_os_error_returns_false(self, mock_exists, mock_remove):
        assert safe_delete_file("/some/file") is False

    @patch("utils.file_utils.os.remove", side_effect=OSError("perm"))
    @patch("utils.file_utils.os.path.exists", return_value=True)
    def test_os_error_with_log_errors_false(self, mock_exists, mock_remove):
        assert safe_delete_file("/some/file", log_errors=False) is False


class TestEnsureDirectoryExists:
    def test_creates_new_directory(self, tmp_path):
        new_dir = tmp_path / "subdir" / "nested"
        assert ensure_directory_exists(str(new_dir)) is True
        assert new_dir.is_dir()

    def test_existing_directory_returns_true(self, tmp_path):
        assert ensure_directory_exists(str(tmp_path)) is True

    @patch("utils.file_utils.os.makedirs", side_effect=OSError("fail"))
    def test_os_error_returns_false(self, mock_makedirs):
        assert ensure_directory_exists("/impossible/path") is False


class TestGetSafeFilename:
    def test_safe_filename_unchanged(self):
        assert get_safe_filename("report.pdf") == "report.pdf"

    def test_replaces_unsafe_characters(self):
        result = get_safe_filename('file<name>:with/bad|chars?.txt')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "/" not in result
        assert "|" not in result
        assert "?" not in result
        assert result.endswith(".txt")

    def test_truncates_preserving_extension(self):
        long_name = "a" * 300 + ".pdf"
        result = get_safe_filename(long_name, max_length=255)
        assert len(result) <= 255
        assert result.endswith(".pdf")

    def test_no_extension_truncates_plainly(self):
        long_name = "b" * 300
        result = get_safe_filename(long_name, max_length=100)
        assert len(result) <= 100

    def test_custom_max_length(self):
        result = get_safe_filename("a" * 50 + ".txt", max_length=20)
        assert len(result) <= 20
        assert result.endswith(".txt")
