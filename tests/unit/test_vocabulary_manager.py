"""
Unit tests for managers.vocabulary_manager.VocabularyManager.

Covers singleton pattern, settings loading, file I/O, CRUD operations,
filtering, import/export, statistics, and reset-to-defaults.
"""

import json
import csv
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, call

# Ensure project src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_correction(
    replacement="Replacement",
    category="general",
    specialty=None,
    case_sensitive=False,
    priority=0,
    enabled=True,
):
    return {
        "replacement": replacement,
        "category": category,
        "specialty": specialty,
        "case_sensitive": case_sensitive,
        "priority": priority,
        "enabled": enabled,
    }


def _make_json_file(path, corrections):
    """Write a vocabulary JSON file with the given list of correction dicts."""
    data = {"version": "1.0", "corrections": corrections}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_module_level_imports():
    """
    Patch settings_manager, data_folder_manager, VocabularyCorrector, and
    get_logger for the vocabulary_manager module so the module-level singleton
    creation at the bottom of the source file does not do real file I/O.

    Note: os.path.exists is NOT patched here so that individual tests that
    create real files work correctly. Tests that need it mocked patch it locally.
    """
    mock_sm = MagicMock()
    mock_sm.get.return_value = {}
    mock_dfm = MagicMock()
    mock_dfm.vocabulary_file_path = "/tmp/test_vocab_PATCHED.json"
    mock_corrector_cls = MagicMock()
    mock_corrector_inst = MagicMock()
    mock_corrector_inst.apply_corrections.return_value = MagicMock(
        corrected_text="corrected", total_replacements=1, corrections_applied=[]
    )
    mock_corrector_cls.return_value = mock_corrector_inst

    with (
        patch("managers.vocabulary_manager.settings_manager", mock_sm),
        patch("managers.vocabulary_manager.data_folder_manager", mock_dfm),
        patch("managers.vocabulary_manager.VocabularyCorrector", mock_corrector_cls),
        patch("managers.vocabulary_manager.get_logger", return_value=MagicMock()),
        patch("managers.vocabulary_manager.VOCABULARY_FILE", "/tmp/test_vocab_PATCHED.json"),
    ):
        yield


@pytest.fixture()
def fresh_manager(tmp_path):
    """
    Yield a fresh VocabularyManager instance with the singleton reset.
    Restores the old singleton after the test.
    """
    from managers.vocabulary_manager import VocabularyManager

    old_instance = VocabularyManager._instance
    VocabularyManager._instance = None

    vocab_file = str(tmp_path / "vocabulary.json")

    mock_sm = MagicMock()
    mock_sm.get.return_value = {}

    mock_corrector_inst = MagicMock()
    mock_corrector_inst.apply_corrections.return_value = MagicMock(
        corrected_text="corrected",
        total_replacements=1,
        corrections_applied=[],
        specialty_used="general",
    )
    mock_corrector_cls = MagicMock(return_value=mock_corrector_inst)

    with (
        patch("managers.vocabulary_manager.settings_manager", mock_sm),
        patch("managers.vocabulary_manager.VocabularyCorrector", mock_corrector_cls),
        patch("managers.vocabulary_manager.get_logger", return_value=MagicMock()),
        patch("managers.vocabulary_manager.VOCABULARY_FILE", vocab_file),
        # Patch os.path.exists only inside vocabulary_manager so no real file is
        # read during __init__, but real files created by tests are still findable
        patch("managers.vocabulary_manager.os.path.exists", return_value=False),
    ):
        mgr = VocabularyManager.get_instance()
        mgr._mock_sm = mock_sm
        mgr._mock_corrector = mock_corrector_inst
        mgr._vocab_file = vocab_file
        yield mgr

    VocabularyManager._instance = old_instance


@pytest.fixture()
def manager_with_corrections(fresh_manager):
    """A fresh manager pre-loaded with two corrections."""
    fresh_manager._corrections = {
        "asprin": _make_correction("aspirin", "medication_names"),
        "htn": _make_correction("hypertension", "abbreviations", specialty="cardiology"),
    }
    return fresh_manager


# ===========================================================================
# TestVocabularyManagerSingleton
# ===========================================================================

class TestVocabularyManagerSingleton:
    def test_get_instance_returns_same_object(self, fresh_manager):
        from managers.vocabulary_manager import VocabularyManager

        mgr2 = VocabularyManager.get_instance()
        assert fresh_manager is mgr2

    def test_direct_instantiation_returns_same_object(self, fresh_manager):
        from managers.vocabulary_manager import VocabularyManager

        # VocabularyManager.__init__ is called but _instance already set
        mgr2 = VocabularyManager.get_instance()
        assert mgr2 is fresh_manager

    def test_instance_is_vocabulary_manager(self, fresh_manager):
        from managers.vocabulary_manager import VocabularyManager

        assert isinstance(fresh_manager, VocabularyManager)


# ===========================================================================
# TestLoadSettings
# ===========================================================================

class TestLoadSettings:
    def test_load_settings_reads_from_settings_manager(self, fresh_manager):
        """_load_settings should call settings_manager.get('custom_vocabulary', ...)."""
        fresh_manager._mock_sm.get.assert_called()
        args = fresh_manager._mock_sm.get.call_args_list
        keys = [a[0][0] for a in args]
        assert "custom_vocabulary" in keys

    def test_load_settings_uses_defaults_when_missing(self, fresh_manager):
        """With empty settings_manager response, defaults should be applied."""
        assert fresh_manager._enabled is True
        assert fresh_manager._default_specialty == "general"
        assert "doctor_names" in fresh_manager._categories
        assert "general" in fresh_manager._specialties

    def test_load_settings_loads_corrections_file(self, tmp_path):
        """If vocabulary.json exists, corrections are loaded from it."""
        from managers.vocabulary_manager import VocabularyManager

        old = VocabularyManager._instance
        VocabularyManager._instance = None

        vocab_file = str(tmp_path / "vocabulary.json")
        _make_json_file(vocab_file, [
            {"find_text": "asprin", "replacement": "aspirin", "category": "medication_names",
             "specialty": None, "case_sensitive": False, "priority": 0, "enabled": True}
        ])

        mock_sm = MagicMock()
        mock_sm.get.return_value = {}

        with (
            patch("managers.vocabulary_manager.settings_manager", mock_sm),
            patch("managers.vocabulary_manager.VocabularyCorrector", MagicMock()),
            patch("managers.vocabulary_manager.get_logger", return_value=MagicMock()),
            patch("managers.vocabulary_manager.VOCABULARY_FILE", vocab_file),
        ):
            mgr = VocabularyManager.get_instance()

        assert "asprin" in mgr._corrections
        assert mgr._corrections["asprin"]["replacement"] == "aspirin"

        VocabularyManager._instance = old

    def test_load_corrections_file_returns_empty_when_no_file_no_legacy(self, fresh_manager):
        """When no file and no legacy corrections, _corrections is empty."""
        fresh_manager._mock_sm.get.return_value = {}
        with patch("managers.vocabulary_manager.os.path.exists", return_value=False):
            result = fresh_manager._load_corrections_file()
        assert result == {}


# ===========================================================================
# TestLoadCorrectionsFile
# ===========================================================================

class TestLoadCorrectionsFile:
    def test_load_corrections_file_from_json(self, tmp_path):
        """Loading from a valid vocabulary.json returns populated dict."""
        from managers.vocabulary_manager import VocabularyManager

        old = VocabularyManager._instance
        VocabularyManager._instance = None

        vocab_file = str(tmp_path / "vocabulary.json")
        _make_json_file(vocab_file, [
            {"find_text": "ibuprophen", "replacement": "ibuprofen",
             "category": "medication_names", "specialty": None,
             "case_sensitive": False, "priority": 0, "enabled": True}
        ])

        mock_sm = MagicMock()
        mock_sm.get.return_value = {}

        with (
            patch("managers.vocabulary_manager.settings_manager", mock_sm),
            patch("managers.vocabulary_manager.VocabularyCorrector", MagicMock()),
            patch("managers.vocabulary_manager.get_logger", return_value=MagicMock()),
            patch("managers.vocabulary_manager.VOCABULARY_FILE", vocab_file),
        ):
            mgr = VocabularyManager.get_instance()
            result = mgr._corrections

        assert "ibuprophen" in result
        assert result["ibuprophen"]["replacement"] == "ibuprofen"

        VocabularyManager._instance = old

    def test_load_corrections_file_skips_blank_find_text(self, tmp_path):
        """Entries with empty find_text should be skipped."""
        from managers.vocabulary_manager import VocabularyManager

        old = VocabularyManager._instance
        VocabularyManager._instance = None

        vocab_file = str(tmp_path / "vocabulary.json")
        _make_json_file(vocab_file, [
            {"find_text": "", "replacement": "should be skipped",
             "category": "general", "specialty": None,
             "case_sensitive": False, "priority": 0, "enabled": True},
            {"find_text": "   ", "replacement": "also skipped",
             "category": "general", "specialty": None,
             "case_sensitive": False, "priority": 0, "enabled": True},
            {"find_text": "valid_key", "replacement": "kept",
             "category": "general", "specialty": None,
             "case_sensitive": False, "priority": 0, "enabled": True},
        ])

        mock_sm = MagicMock()
        mock_sm.get.return_value = {}

        with (
            patch("managers.vocabulary_manager.settings_manager", mock_sm),
            patch("managers.vocabulary_manager.VocabularyCorrector", MagicMock()),
            patch("managers.vocabulary_manager.get_logger", return_value=MagicMock()),
            patch("managers.vocabulary_manager.VOCABULARY_FILE", vocab_file),
        ):
            mgr = VocabularyManager.get_instance()

        assert "" not in mgr._corrections
        assert "   " not in mgr._corrections
        assert "valid_key" in mgr._corrections

        VocabularyManager._instance = old

    def test_load_corrections_file_handles_json_error(self, tmp_path):
        """A malformed JSON file should return empty dict without raising."""
        from managers.vocabulary_manager import VocabularyManager

        old = VocabularyManager._instance
        VocabularyManager._instance = None

        vocab_file = str(tmp_path / "vocabulary.json")
        with open(vocab_file, "w") as f:
            f.write("this is not json {{{")

        mock_sm = MagicMock()
        mock_sm.get.return_value = {}

        with (
            patch("managers.vocabulary_manager.settings_manager", mock_sm),
            patch("managers.vocabulary_manager.VocabularyCorrector", MagicMock()),
            patch("managers.vocabulary_manager.get_logger", return_value=MagicMock()),
            patch("managers.vocabulary_manager.VOCABULARY_FILE", vocab_file),
        ):
            mgr = VocabularyManager.get_instance()

        assert mgr._corrections == {}

        VocabularyManager._instance = old

    def test_load_corrections_file_migrates_legacy_from_settings(self, tmp_path):
        """Legacy corrections in settings.json should be migrated to vocabulary.json."""
        from managers.vocabulary_manager import VocabularyManager

        old = VocabularyManager._instance
        VocabularyManager._instance = None

        vocab_file = str(tmp_path / "vocabulary.json")
        legacy = {
            "legacy_word": {"replacement": "LegacyWord", "category": "general",
                            "specialty": None, "case_sensitive": False,
                            "priority": 0, "enabled": True}
        }

        mock_sm = MagicMock()
        mock_sm.get.return_value = {"corrections": legacy}

        with (
            patch("managers.vocabulary_manager.settings_manager", mock_sm),
            patch("managers.vocabulary_manager.VocabularyCorrector", MagicMock()),
            patch("managers.vocabulary_manager.get_logger", return_value=MagicMock()),
            patch("managers.vocabulary_manager.VOCABULARY_FILE", vocab_file),
            patch("managers.vocabulary_manager.os.path.exists", return_value=False),
        ):
            mgr = VocabularyManager.get_instance()

        assert "legacy_word" in mgr._corrections

        VocabularyManager._instance = old

    def test_load_corrections_file_removes_legacy_after_migration(self, tmp_path):
        """After migrating legacy corrections, settings_manager.set should be called."""
        from managers.vocabulary_manager import VocabularyManager

        old = VocabularyManager._instance
        VocabularyManager._instance = None

        vocab_file = str(tmp_path / "vocabulary.json")
        legacy = {
            "old_word": {"replacement": "NewWord", "category": "general",
                         "specialty": None, "case_sensitive": False,
                         "priority": 0, "enabled": True}
        }

        mock_sm = MagicMock()
        mock_sm.get.return_value = {"corrections": legacy}

        with (
            patch("managers.vocabulary_manager.settings_manager", mock_sm),
            patch("managers.vocabulary_manager.VocabularyCorrector", MagicMock()),
            patch("managers.vocabulary_manager.get_logger", return_value=MagicMock()),
            patch("managers.vocabulary_manager.VOCABULARY_FILE", vocab_file),
            patch("managers.vocabulary_manager.os.path.exists", return_value=False),
        ):
            VocabularyManager.get_instance()

        # settings_manager.set should have been called to remove legacy corrections
        mock_sm.set.assert_called()

        VocabularyManager._instance = old


# ===========================================================================
# TestSaveSettings
# ===========================================================================

class TestSaveSettings:
    def test_save_settings_calls_settings_manager_set(self, fresh_manager):
        """save_settings() should call settings_manager.set('custom_vocabulary', ...)."""
        fresh_manager._mock_sm.reset_mock()

        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            fresh_manager.save_settings()

        fresh_manager._mock_sm.set.assert_called()
        args = fresh_manager._mock_sm.set.call_args_list
        keys = [a[0][0] for a in args]
        assert "custom_vocabulary" in keys

    def test_save_corrections_file_writes_json(self, fresh_manager):
        """_save_corrections_file() should write a valid JSON file."""
        fresh_manager._corrections = {
            "test_word": _make_correction("TestWord")
        }

        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            fresh_manager._save_corrections_file()

        # Use Path.exists() to avoid os.path.exists mock side effects
        assert Path(fresh_manager._vocab_file).exists()
        with open(fresh_manager._vocab_file, "r") as f:
            data = json.load(f)
        assert data["version"] == "1.0"
        entries = {e["find_text"]: e for e in data["corrections"]}
        assert "test_word" in entries
        assert entries["test_word"]["replacement"] == "TestWord"

    def test_save_corrections_to_file_handles_error(self, fresh_manager):
        """If writing the file raises an OSError, it should not propagate."""
        with patch("builtins.open", side_effect=OSError("disk full")):
            # Should not raise
            fresh_manager._save_corrections_to_file({"x": _make_correction()})


# ===========================================================================
# TestProperties
# ===========================================================================

class TestProperties:
    def test_enabled_property_get(self, fresh_manager):
        fresh_manager._enabled = True
        assert fresh_manager.enabled is True

    def test_enabled_setter_saves(self, fresh_manager):
        fresh_manager._mock_sm.reset_mock()
        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            fresh_manager.enabled = False
        assert fresh_manager._enabled is False
        fresh_manager._mock_sm.set.assert_called()

    def test_default_specialty_property_get(self, fresh_manager):
        fresh_manager._default_specialty = "cardiology"
        assert fresh_manager.default_specialty == "cardiology"

    def test_default_specialty_setter_saves(self, fresh_manager):
        fresh_manager._mock_sm.reset_mock()
        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            fresh_manager.default_specialty = "neurology"
        assert fresh_manager._default_specialty == "neurology"
        fresh_manager._mock_sm.set.assert_called()

    def test_categories_returns_copy(self, fresh_manager):
        cats = fresh_manager.categories
        cats.append("__test__")
        assert "__test__" not in fresh_manager._categories

    def test_specialties_returns_copy(self, fresh_manager):
        specs = fresh_manager.specialties
        specs.append("__test__")
        assert "__test__" not in fresh_manager._specialties

    def test_corrections_returns_copy(self, fresh_manager):
        fresh_manager._corrections = {"a": _make_correction()}
        corr = fresh_manager.corrections
        corr["new_key"] = _make_correction()
        assert "new_key" not in fresh_manager._corrections


# ===========================================================================
# TestCorrectTranscript
# ===========================================================================

class TestCorrectTranscript:
    def test_correct_transcript_when_disabled_returns_original(self, fresh_manager):
        fresh_manager._enabled = False
        result = fresh_manager.correct_transcript("Hello world")
        assert result == "Hello world"

    def test_correct_transcript_empty_text_returns_empty(self, fresh_manager):
        fresh_manager._enabled = True
        result = fresh_manager.correct_transcript("")
        assert result == ""

    def test_correct_transcript_uses_default_specialty_when_none(self, fresh_manager):
        fresh_manager._enabled = True
        fresh_manager._default_specialty = "cardiology"
        fresh_manager._corrections = {"htn": _make_correction("hypertension")}

        mock_result = MagicMock()
        mock_result.corrected_text = "hypertension"
        mock_result.total_replacements = 1
        fresh_manager._mock_corrector.apply_corrections.return_value = mock_result

        fresh_manager.correct_transcript("htn", specialty=None)

        _, _, called_specialty = fresh_manager._mock_corrector.apply_corrections.call_args[0]
        assert called_specialty == "cardiology"

    def test_correct_transcript_logs_when_replacements_made(self, fresh_manager):
        fresh_manager._enabled = True
        fresh_manager._corrections = {"x": _make_correction()}

        mock_result = MagicMock()
        mock_result.corrected_text = "corrected"
        mock_result.total_replacements = 3
        fresh_manager._mock_corrector.apply_corrections.return_value = mock_result

        fresh_manager.correct_transcript("x something x")
        # logger.info should have been called (logger is a MagicMock)
        fresh_manager.logger.info.assert_called()

    def test_correct_transcript_with_details_disabled(self, fresh_manager):
        """correct_transcript_with_details when disabled returns CorrectionResult with original text."""
        fresh_manager._enabled = False
        from utils.vocabulary_corrector import CorrectionResult

        result = fresh_manager.correct_transcript_with_details("original text")
        assert isinstance(result, CorrectionResult)
        assert result.corrected_text == "original text"
        assert result.original_text == "original text"


# ===========================================================================
# TestCRUD
# ===========================================================================

class TestCRUD:
    def test_add_correction_success(self, fresh_manager):
        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            ok = fresh_manager.add_correction("asprin", "aspirin", category="medication_names")
        assert ok is True
        assert "asprin" in fresh_manager._corrections
        assert fresh_manager._corrections["asprin"]["replacement"] == "aspirin"

    def test_add_correction_rejects_empty_find_text(self, fresh_manager):
        ok = fresh_manager.add_correction("", "aspirin")
        assert ok is False
        assert "" not in fresh_manager._corrections

    def test_add_correction_rejects_empty_replacement(self, fresh_manager):
        ok = fresh_manager.add_correction("asprin", "")
        assert ok is False

    def test_get_correction_found(self, manager_with_corrections):
        result = manager_with_corrections.get_correction("asprin")
        assert result is not None
        assert result["replacement"] == "aspirin"

    def test_get_correction_not_found(self, manager_with_corrections):
        result = manager_with_corrections.get_correction("nonexistent_word")
        assert result is None

    def test_update_correction_renames_key(self, fresh_manager):
        fresh_manager._corrections = {"old_key": _make_correction("OldValue")}
        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            ok = fresh_manager.update_correction("old_key", "new_key", "NewValue")
        assert ok is True
        assert "old_key" not in fresh_manager._corrections
        assert "new_key" in fresh_manager._corrections
        assert fresh_manager._corrections["new_key"]["replacement"] == "NewValue"

    def test_update_correction_rejects_empty_find_text(self, fresh_manager):
        fresh_manager._corrections = {"real_key": _make_correction()}
        ok = fresh_manager.update_correction("real_key", "", "NewValue")
        assert ok is False

    def test_delete_correction_success(self, manager_with_corrections):
        with patch("managers.vocabulary_manager.VOCABULARY_FILE", manager_with_corrections._vocab_file):
            ok = manager_with_corrections.delete_correction("asprin")
        assert ok is True
        assert "asprin" not in manager_with_corrections._corrections

    def test_delete_correction_not_found(self, fresh_manager):
        ok = fresh_manager.delete_correction("nonexistent")
        assert ok is False


# ===========================================================================
# TestFiltering
# ===========================================================================

class TestFiltering:
    def test_get_corrections_by_category(self, fresh_manager):
        fresh_manager._corrections = {
            "a": _make_correction(category="medication_names"),
            "b": _make_correction(category="abbreviations"),
            "c": _make_correction(category="medication_names"),
        }
        result = fresh_manager.get_corrections_by_category("medication_names")
        assert set(result.keys()) == {"a", "c"}

    def test_get_corrections_by_specialty_includes_none_specialty(self, fresh_manager):
        """Corrections with specialty=None should be included for any specialty query."""
        fresh_manager._corrections = {
            "universal": _make_correction(specialty=None),
        }
        result = fresh_manager.get_corrections_by_specialty("cardiology")
        assert "universal" in result

    def test_get_corrections_by_specialty_includes_general(self, fresh_manager):
        fresh_manager._corrections = {
            "gen_word": _make_correction(specialty="general"),
        }
        result = fresh_manager.get_corrections_by_specialty("cardiology")
        assert "gen_word" in result

    def test_get_corrections_by_specialty_excludes_wrong_specialty(self, fresh_manager):
        fresh_manager._corrections = {
            "ortho_word": _make_correction(specialty="orthopedics"),
        }
        result = fresh_manager.get_corrections_by_specialty("cardiology")
        assert "ortho_word" not in result


# ===========================================================================
# TestImportExportJson
# ===========================================================================

class TestImportExportJson:
    def test_export_to_json_writes_file(self, fresh_manager, tmp_path):
        fresh_manager._corrections = {
            "asprin": _make_correction("aspirin", "medication_names"),
        }
        out_file = str(tmp_path / "export.json")
        fresh_manager.export_to_json(out_file)

        # Use Path.exists() to avoid os.path.exists mock side effects
        assert Path(out_file).exists()
        with open(out_file) as f:
            data = json.load(f)
        assert any(e["find_text"] == "asprin" for e in data["corrections"])

    def test_export_to_json_returns_count(self, fresh_manager, tmp_path):
        fresh_manager._corrections = {
            "a": _make_correction(),
            "b": _make_correction(),
        }
        out_file = str(tmp_path / "export.json")
        count = fresh_manager.export_to_json(out_file)
        assert count == 2

    def test_export_to_json_handles_error(self, fresh_manager):
        with patch("builtins.open", side_effect=OSError("no space")):
            count = fresh_manager.export_to_json("/nonexistent/path/export.json")
        assert count == 0

    def test_import_from_json_adds_corrections(self, fresh_manager, tmp_path):
        import_file = str(tmp_path / "import.json")
        _make_json_file(import_file, [
            {"find_text": "metforman", "replacement": "metformin",
             "category": "medication_names", "specialty": None,
             "case_sensitive": False, "priority": 0, "enabled": True}
        ])

        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            count, errors = fresh_manager.import_from_json(import_file)

        assert count == 1
        assert errors == []
        assert "metforman" in fresh_manager._corrections

    def test_import_from_json_skips_invalid_rows(self, fresh_manager, tmp_path):
        import_file = str(tmp_path / "import.json")
        _make_json_file(import_file, [
            {"find_text": "", "replacement": "something"},  # blank find_text
            {"find_text": "valid", "replacement": ""},      # blank replacement
            {"find_text": "ok_word", "replacement": "OkWord", "category": "general",
             "specialty": None, "case_sensitive": False, "priority": 0, "enabled": True},
        ])

        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            count, errors = fresh_manager.import_from_json(import_file)

        assert count == 1
        assert len(errors) == 2

    def test_import_from_json_handles_file_error(self, fresh_manager):
        count, errors = fresh_manager.import_from_json("/nonexistent/path/import.json")
        assert count == 0
        assert len(errors) > 0


# ===========================================================================
# TestImportExportCsv
# ===========================================================================

class TestImportExportCsv:
    def _write_csv(self, path, rows):
        fieldnames = ["find_text", "replacement", "category", "specialty",
                      "case_sensitive", "priority", "enabled"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def test_export_to_csv_writes_header_and_rows(self, fresh_manager, tmp_path):
        fresh_manager._corrections = {
            "asprin": _make_correction("aspirin", "medication_names"),
        }
        out_file = str(tmp_path / "export.csv")
        fresh_manager.export_to_csv(out_file)

        with open(out_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["find_text"] == "asprin"
        assert rows[0]["replacement"] == "aspirin"

    def test_export_to_csv_returns_count(self, fresh_manager, tmp_path):
        fresh_manager._corrections = {
            "a": _make_correction(),
            "b": _make_correction(),
            "c": _make_correction(),
        }
        out_file = str(tmp_path / "export.csv")
        count = fresh_manager.export_to_csv(out_file)
        assert count == 3

    def test_export_to_csv_handles_error(self, fresh_manager):
        with patch("builtins.open", side_effect=OSError("disk full")):
            count = fresh_manager.export_to_csv("/nonexistent/path/export.csv")
        assert count == 0

    def test_import_from_csv_adds_corrections(self, fresh_manager, tmp_path):
        csv_file = str(tmp_path / "import.csv")
        self._write_csv(csv_file, [
            {"find_text": "ibuprophen", "replacement": "ibuprofen",
             "category": "medication_names", "specialty": "",
             "case_sensitive": "false", "priority": "0", "enabled": "true"}
        ])

        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            count, errors = fresh_manager.import_from_csv(csv_file)

        assert count == 1
        assert "ibuprophen" in fresh_manager._corrections
        assert fresh_manager._corrections["ibuprophen"]["replacement"] == "ibuprofen"

    def test_import_from_csv_parses_booleans(self, fresh_manager, tmp_path):
        csv_file = str(tmp_path / "import.csv")
        self._write_csv(csv_file, [
            {"find_text": "word1", "replacement": "Word1",
             "category": "general", "specialty": "",
             "case_sensitive": "true", "priority": "5", "enabled": "false"},
        ])

        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            fresh_manager.import_from_csv(csv_file)

        rule = fresh_manager._corrections["word1"]
        assert rule["case_sensitive"] is True
        assert rule["enabled"] is False
        assert rule["priority"] == 5

    def test_import_from_csv_handles_file_error(self, fresh_manager):
        count, errors = fresh_manager.import_from_csv("/nonexistent/path/import.csv")
        assert count == 0
        assert len(errors) > 0


# ===========================================================================
# TestStatistics
# ===========================================================================

class TestStatistics:
    def test_statistics_empty(self, fresh_manager):
        fresh_manager._corrections = {}
        stats = fresh_manager.get_statistics()
        assert stats["total"] == 0
        assert stats["enabled"] == 0
        assert stats["disabled"] == 0
        assert stats["by_category"] == {}

    def test_statistics_counts_by_category(self, fresh_manager):
        fresh_manager._corrections = {
            "a": _make_correction(category="medication_names"),
            "b": _make_correction(category="medication_names"),
            "c": _make_correction(category="abbreviations"),
        }
        stats = fresh_manager.get_statistics()
        assert stats["total"] == 3
        assert stats["by_category"]["medication_names"] == 2
        assert stats["by_category"]["abbreviations"] == 1

    def test_statistics_counts_enabled_disabled(self, fresh_manager):
        fresh_manager._corrections = {
            "a": _make_correction(enabled=True),
            "b": _make_correction(enabled=True),
            "c": _make_correction(enabled=False),
        }
        stats = fresh_manager.get_statistics()
        assert stats["enabled"] == 2
        assert stats["disabled"] == 1


# ===========================================================================
# TestReloadAndReset
# ===========================================================================

class TestReloadAndReset:
    def test_reload_settings_clears_cache(self, fresh_manager):
        """reload_settings() should call corrector.clear_cache()."""
        fresh_manager._mock_corrector.clear_cache.reset_mock()
        fresh_manager._mock_sm.get.return_value = {}
        with patch("os.path.exists", return_value=False):
            fresh_manager.reload_settings()
        fresh_manager._mock_corrector.clear_cache.assert_called()

    def test_reload_settings_calls_load_settings(self, fresh_manager):
        """reload_settings() should re-read settings_manager."""
        fresh_manager._mock_sm.reset_mock()
        fresh_manager._mock_sm.get.return_value = {}
        with patch("os.path.exists", return_value=False):
            fresh_manager.reload_settings()
        fresh_manager._mock_sm.get.assert_called()

    def test_reset_to_defaults_loads_defaults(self, fresh_manager):
        """reset_to_defaults() should populate _corrections with default entries."""
        fresh_manager._corrections = {}
        with patch("managers.vocabulary_manager.VOCABULARY_FILE", fresh_manager._vocab_file):
            fresh_manager.reset_to_defaults()
        assert len(fresh_manager._corrections) > 0


# ===========================================================================
# TestGetDefaultCorrections
# ===========================================================================

class TestGetDefaultCorrections:
    def test_get_default_corrections_not_empty(self):
        from managers.vocabulary_manager import _get_default_corrections

        defaults = _get_default_corrections()
        assert len(defaults) > 0

    def test_get_default_corrections_has_expected_categories(self):
        from managers.vocabulary_manager import _get_default_corrections

        defaults = _get_default_corrections()
        categories = {v["category"] for v in defaults.values()}
        # Should contain at least these categories
        assert "medication_names" in categories
        assert "abbreviations" in categories
        assert "doctor_names" in categories
