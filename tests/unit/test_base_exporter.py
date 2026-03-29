"""
Tests for src/exporters/base_exporter.py
No network, no Tkinter, no I/O.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from exporters.base_exporter import BaseExporter


# ---------------------------------------------------------------------------
# Concrete subclass used throughout the test suite
# ---------------------------------------------------------------------------

class ConcreteExporter(BaseExporter):
    def export(self, content, output_path):
        return True

    def export_to_string(self, content):
        return str(content)


# ---------------------------------------------------------------------------
# TestBaseExporterInit
# ---------------------------------------------------------------------------

class TestBaseExporterInit:
    def test_last_error_is_none_on_init(self):
        exporter = ConcreteExporter()
        assert exporter.last_error is None

    def test_concrete_subclass_is_instantiable(self):
        exporter = ConcreteExporter()
        assert exporter is not None

    def test_abstract_base_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            BaseExporter()  # type: ignore[abstract]

    def test_last_error_property_accessible(self):
        exporter = ConcreteExporter()
        # Accessing the property should not raise
        _ = exporter.last_error

    def test_multiple_instances_have_independent_errors(self):
        e1 = ConcreteExporter()
        e2 = ConcreteExporter()
        e1._last_error = "some error"
        assert e2.last_error is None

    def test_export_method_returns_true_in_concrete(self):
        exporter = ConcreteExporter()
        assert exporter.export({}, Path("/tmp/out.txt")) is True

    def test_export_to_string_returns_string(self):
        exporter = ConcreteExporter()
        result = exporter.export_to_string({"key": "value"})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TestValidateContent
# ---------------------------------------------------------------------------

class TestValidateContent:
    def setup_method(self):
        self.exporter = ConcreteExporter()

    def test_all_required_keys_present_returns_true(self):
        content = {"a": 1, "b": 2, "c": 3}
        assert self.exporter._validate_content(content, ["a", "b", "c"]) is True

    def test_all_required_keys_present_last_error_unchanged(self):
        content = {"a": 1, "b": 2}
        self.exporter._validate_content(content, ["a", "b"])
        assert self.exporter.last_error is None

    def test_missing_one_key_returns_false(self):
        content = {"a": 1}
        assert self.exporter._validate_content(content, ["a", "b"]) is False

    def test_missing_one_key_sets_last_error(self):
        content = {"a": 1}
        self.exporter._validate_content(content, ["a", "b"])
        assert self.exporter.last_error is not None
        assert "b" in self.exporter.last_error

    def test_missing_multiple_keys_returns_false(self):
        content = {}
        assert self.exporter._validate_content(content, ["x", "y", "z"]) is False

    def test_missing_multiple_keys_sets_last_error(self):
        content = {}
        self.exporter._validate_content(content, ["x", "y", "z"])
        assert self.exporter.last_error is not None

    def test_missing_multiple_keys_error_mentions_missing(self):
        content = {}
        self.exporter._validate_content(content, ["x", "y"])
        error = self.exporter.last_error
        assert "x" in error or "y" in error

    def test_empty_required_keys_returns_true(self):
        content = {"a": 1}
        assert self.exporter._validate_content(content, []) is True

    def test_empty_required_keys_no_error_set(self):
        self.exporter._validate_content({}, [])
        assert self.exporter.last_error is None

    def test_empty_content_empty_required_returns_true(self):
        assert self.exporter._validate_content({}, []) is True

    def test_empty_content_with_required_keys_returns_false(self):
        assert self.exporter._validate_content({}, ["key"]) is False

    def test_extra_keys_in_content_still_passes(self):
        content = {"a": 1, "b": 2, "extra": 99}
        assert self.exporter._validate_content(content, ["a", "b"]) is True

    def test_validate_content_with_none_value_still_passes(self):
        # Key presence is what matters, not value truthiness
        content = {"a": None, "b": 0}
        assert self.exporter._validate_content(content, ["a", "b"]) is True

    def test_last_error_overwritten_on_repeated_failure(self):
        self.exporter._validate_content({}, ["first"])
        first_error = self.exporter.last_error
        self.exporter._validate_content({}, ["second"])
        second_error = self.exporter.last_error
        assert second_error != first_error
        assert "second" in second_error

    def test_error_message_contains_missing_keys_label(self):
        self.exporter._validate_content({}, ["alpha"])
        assert "Missing" in self.exporter.last_error or "missing" in self.exporter.last_error.lower()


# ---------------------------------------------------------------------------
# TestEnsureDirectory
# ---------------------------------------------------------------------------

class TestEnsureDirectory:
    def setup_method(self):
        self.exporter = ConcreteExporter()

    def test_creates_directory_for_valid_path(self, tmp_path):
        new_dir = tmp_path / "subdir" / "nested"
        output_file = new_dir / "output.txt"
        result = self.exporter._ensure_directory(output_file)
        assert result is True
        assert new_dir.exists()

    def test_last_error_none_on_success(self, tmp_path):
        output_file = tmp_path / "out.txt"
        self.exporter._ensure_directory(output_file)
        assert self.exporter.last_error is None

    def test_returns_true_on_success(self, tmp_path):
        output_file = tmp_path / "file.txt"
        assert self.exporter._ensure_directory(output_file) is True

    def test_handles_existing_directory(self, tmp_path):
        # tmp_path already exists; should still succeed
        output_file = tmp_path / "file.txt"
        result = self.exporter._ensure_directory(output_file)
        assert result is True

    def test_handles_existing_directory_no_error(self, tmp_path):
        output_file = tmp_path / "file.txt"
        self.exporter._ensure_directory(output_file)
        assert self.exporter.last_error is None

    def test_returns_false_on_os_error(self, tmp_path):
        output_file = tmp_path / "subdir" / "file.txt"
        with patch.object(Path, "mkdir", side_effect=OSError("permission denied")):
            result = self.exporter._ensure_directory(output_file)
        assert result is False

    def test_sets_last_error_on_os_error(self, tmp_path):
        output_file = tmp_path / "subdir" / "file.txt"
        with patch.object(Path, "mkdir", side_effect=OSError("permission denied")):
            self.exporter._ensure_directory(output_file)
        assert self.exporter.last_error is not None

    def test_error_message_contains_directory_info(self, tmp_path):
        output_file = tmp_path / "subdir" / "file.txt"
        with patch.object(Path, "mkdir", side_effect=OSError("no space left")):
            self.exporter._ensure_directory(output_file)
        assert "directory" in self.exporter.last_error.lower() or "create" in self.exporter.last_error.lower()

    def test_deeply_nested_path_created(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        output_file = deep / "output.json"
        result = self.exporter._ensure_directory(output_file)
        assert result is True
        assert deep.exists()

    def test_path_object_accepted(self, tmp_path):
        path = Path(tmp_path) / "sub" / "file.txt"
        result = self.exporter._ensure_directory(path)
        assert result is True


# ---------------------------------------------------------------------------
# TestExportToClipboard
# ---------------------------------------------------------------------------

class TestExportToClipboard:
    def setup_method(self):
        self.exporter = ConcreteExporter()
        self.content = {"patient": "John Doe", "note": "healthy"}

    def test_returns_true_on_success(self):
        with patch("pyperclip.copy") as mock_copy:
            result = self.exporter.export_to_clipboard(self.content)
        assert result is True

    def test_calls_pyperclip_copy(self):
        with patch("pyperclip.copy") as mock_copy:
            self.exporter.export_to_clipboard(self.content)
        mock_copy.assert_called_once()

    def test_copies_export_to_string_result(self):
        with patch("pyperclip.copy") as mock_copy:
            self.exporter.export_to_clipboard(self.content)
        expected = self.exporter.export_to_string(self.content)
        mock_copy.assert_called_once_with(expected)

    def test_last_error_none_on_success(self):
        with patch("pyperclip.copy"):
            self.exporter.export_to_clipboard(self.content)
        assert self.exporter.last_error is None

    def test_returns_false_when_pyperclip_raises(self):
        with patch("pyperclip.copy", side_effect=Exception("clipboard error")):
            result = self.exporter.export_to_clipboard(self.content)
        assert result is False

    def test_sets_last_error_when_pyperclip_raises(self):
        with patch("pyperclip.copy", side_effect=Exception("clipboard error")):
            self.exporter.export_to_clipboard(self.content)
        assert self.exporter.last_error is not None

    def test_last_error_mentions_clipboard_on_failure(self):
        with patch("pyperclip.copy", side_effect=Exception("not available")):
            self.exporter.export_to_clipboard(self.content)
        assert "clipboard" in self.exporter.last_error.lower()

    def test_last_error_contains_original_exception_message(self):
        with patch("pyperclip.copy", side_effect=Exception("xclip missing")):
            self.exporter.export_to_clipboard(self.content)
        assert "xclip missing" in self.exporter.last_error

    def test_pyperclip_import_error_returns_false(self):
        with patch.dict("sys.modules", {"pyperclip": None}):
            result = self.exporter.export_to_clipboard(self.content)
        assert result is False

    def test_empty_content_dict_clipboard_success(self):
        with patch("pyperclip.copy"):
            result = self.exporter.export_to_clipboard({})
        assert result is True

    def test_clipboard_copies_string_form_of_content(self):
        content = {"x": 42}
        captured = []
        with patch("pyperclip.copy", side_effect=lambda v: captured.append(v)):
            self.exporter.export_to_clipboard(content)
        assert len(captured) == 1
        assert isinstance(captured[0], str)


# ---------------------------------------------------------------------------
# TestLastError
# ---------------------------------------------------------------------------

class TestLastError:
    def setup_method(self):
        self.exporter = ConcreteExporter()

    def test_initially_none(self):
        assert self.exporter.last_error is None

    def test_validate_content_failure_sets_last_error(self):
        self.exporter._validate_content({}, ["required_key"])
        assert self.exporter.last_error is not None

    def test_validate_content_success_does_not_set_last_error(self):
        self.exporter._validate_content({"k": "v"}, ["k"])
        assert self.exporter.last_error is None

    def test_ensure_directory_failure_sets_last_error(self, tmp_path):
        output_file = tmp_path / "sub" / "file.txt"
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            self.exporter._ensure_directory(output_file)
        assert self.exporter.last_error is not None

    def test_ensure_directory_success_leaves_last_error_none(self, tmp_path):
        self.exporter._ensure_directory(tmp_path / "file.txt")
        assert self.exporter.last_error is None

    def test_clipboard_failure_sets_last_error(self):
        with patch("pyperclip.copy", side_effect=RuntimeError("fail")):
            self.exporter.export_to_clipboard({})
        assert self.exporter.last_error is not None

    def test_last_error_is_string_when_set(self):
        self.exporter._validate_content({}, ["k"])
        assert isinstance(self.exporter.last_error, str)

    def test_last_error_is_readable_message(self):
        self.exporter._validate_content({}, ["my_field"])
        error = self.exporter.last_error
        assert len(error) > 0

    def test_successive_failures_update_last_error(self):
        self.exporter._validate_content({}, ["first"])
        err1 = self.exporter.last_error
        self.exporter._validate_content({}, ["second"])
        err2 = self.exporter.last_error
        assert err1 != err2
