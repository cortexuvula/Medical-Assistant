"""
Tests for src/managers/file_manager.py

Covers FileManager._validate_prompts_schema() (pure validation logic)
and get_recording_path() (filename generation).
No Tkinter dialogs are opened — only pure methods are exercised.
"""

import sys
import re
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


@pytest.fixture
def fm():
    from managers.file_manager import FileManager
    return FileManager()


# ===========================================================================
# _validate_prompts_schema
# ===========================================================================

class TestValidatePromptsSchema:
    def test_valid_soap_category(self, fm):
        data = {"soap": {"prompt": "Generate a SOAP note.", "temperature": 0.5}}
        assert fm._validate_prompts_schema(data) == []

    def test_non_dict_root_returns_error(self, fm):
        errors = fm._validate_prompts_schema(["not", "a", "dict"])
        assert len(errors) == 1
        assert "object" in errors[0].lower()

    def test_empty_dict_returns_error(self, fm):
        errors = fm._validate_prompts_schema({})
        assert len(errors) == 1
        assert "no prompt" in errors[0].lower() or "empty" in errors[0].lower() or "found" in errors[0].lower()

    def test_category_value_not_dict_returns_error(self, fm):
        data = {"soap": "should be a dict"}
        errors = fm._validate_prompts_schema(data)
        assert len(errors) == 1
        assert "object" in errors[0].lower()

    def test_prompt_not_string_returns_error(self, fm):
        data = {"soap": {"prompt": 12345}}
        errors = fm._validate_prompts_schema(data)
        assert len(errors) == 1
        assert "string" in errors[0].lower()

    def test_prompt_too_long_returns_error(self, fm):
        data = {"soap": {"prompt": "x" * 100001}}
        errors = fm._validate_prompts_schema(data)
        assert len(errors) == 1
        assert "long" in errors[0].lower() or "max" in errors[0].lower()

    def test_prompt_exactly_100000_chars_valid(self, fm):
        data = {"soap": {"prompt": "x" * 100000}}
        errors = fm._validate_prompts_schema(data)
        assert errors == []

    def test_temperature_not_number_returns_error(self, fm):
        data = {"soap": {"temperature": "warm"}}
        errors = fm._validate_prompts_schema(data)
        assert len(errors) == 1
        assert "number" in errors[0].lower()

    def test_temperature_below_zero_returns_error(self, fm):
        data = {"soap": {"temperature": -0.1}}
        errors = fm._validate_prompts_schema(data)
        assert len(errors) == 1
        assert "0.0" in errors[0] or "between" in errors[0].lower()

    def test_temperature_above_2_returns_error(self, fm):
        data = {"soap": {"temperature": 2.1}}
        errors = fm._validate_prompts_schema(data)
        assert len(errors) == 1
        assert "2.0" in errors[0] or "between" in errors[0].lower()

    def test_temperature_0_is_valid(self, fm):
        data = {"soap": {"temperature": 0.0}}
        assert fm._validate_prompts_schema(data) == []

    def test_temperature_2_is_valid(self, fm):
        data = {"soap": {"temperature": 2.0}}
        assert fm._validate_prompts_schema(data) == []

    def test_temperature_int_is_valid(self, fm):
        data = {"soap": {"temperature": 1}}
        assert fm._validate_prompts_schema(data) == []

    def test_category_name_too_long_returns_error(self, fm):
        long_name = "x" * 101
        data = {long_name: {"prompt": "x"}}
        errors = fm._validate_prompts_schema(data)
        assert len(errors) == 1
        assert "long" in errors[0].lower() or "too" in errors[0].lower()

    def test_category_name_100_chars_valid(self, fm):
        name = "x" * 100
        data = {name: {"prompt": "x"}}
        assert fm._validate_prompts_schema(data) == []

    def test_unknown_category_not_an_error(self, fm):
        data = {"unknown_custom_category": {"prompt": "some prompt"}}
        errors = fm._validate_prompts_schema(data)
        # Unknown category is not an error (just a debug log)
        assert errors == []

    def test_multiple_valid_categories(self, fm):
        data = {
            "soap": {"prompt": "SOAP note", "temperature": 0.3},
            "referral": {"prompt": "Referral letter"},
        }
        assert fm._validate_prompts_schema(data) == []

    def test_multiple_errors_all_reported(self, fm):
        data = {
            "soap": {"temperature": "wrong"},  # error 1
            "referral": {"temperature": 99.0},  # error 2
        }
        errors = fm._validate_prompts_schema(data)
        assert len(errors) == 2

    def test_returns_list(self, fm):
        result = fm._validate_prompts_schema({"soap": {"prompt": "x"}})
        assert isinstance(result, list)

    def test_no_prompt_or_temperature_is_valid(self, fm):
        # Empty category dict is a valid structure (no required fields)
        data = {"soap": {}}
        assert fm._validate_prompts_schema(data) == []

    def test_valid_prompt_categories_class_attribute(self, fm):
        from managers.file_manager import FileManager
        expected = {'refine', 'improve', 'soap', 'referral', 'advanced_analysis'}
        assert FileManager.VALID_PROMPT_CATEGORIES == expected


# ===========================================================================
# get_recording_path
# ===========================================================================

class TestGetRecordingPath:
    def test_returns_string(self, fm, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = fm.get_recording_path()
        assert isinstance(result, str)

    def test_default_type_is_soap(self, fm, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = fm.get_recording_path()
        assert "soap" in result

    def test_custom_type_in_path(self, fm, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = fm.get_recording_path("audio")
        assert "audio" in result

    def test_path_ends_with_mp3(self, fm, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = fm.get_recording_path()
        assert result.endswith(".mp3")

    def test_path_contains_recordings_dir(self, fm, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = fm.get_recording_path()
        assert "recordings" in result

    def test_path_contains_timestamp(self, fm, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = fm.get_recording_path()
        # Timestamp format: YYYYMMDD_HHMMSS (14 digits + underscore)
        assert re.search(r'\d{8}_\d{6}', result), f"No timestamp in: {result}"

    def test_creates_recordings_directory(self, fm, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fm.get_recording_path()
        assert (tmp_path / "recordings").exists()

    def test_two_calls_produce_different_paths_by_second(self, fm, tmp_path, monkeypatch):
        """If called at different seconds, paths should differ."""
        import time
        monkeypatch.chdir(tmp_path)
        path1 = fm.get_recording_path("soap")
        time.sleep(1.1)
        path2 = fm.get_recording_path("soap")
        assert path1 != path2
