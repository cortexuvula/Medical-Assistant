"""
Dialog Boundary Tests

Tests that result dialogs can work with a narrow DocumentTargetProtocol
instead of requiring the full application object. These tests verify:
- _add_to_document works with mock document targets
- Fallback to self.parent when no document_target provided
- Each dialog subclass accepts document_target parameter

These tests are durable — they test the protocol boundary, not UI internals.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk


class MockDocumentTarget:
    """Minimal implementation of DocumentTargetProtocol for testing."""

    def __init__(self):
        self.soap_text = Mock()
        self.soap_text.get = Mock(return_value="existing content\n")
        self.soap_text.delete = Mock()
        self.soap_text.insert = Mock()

        self.letter_text = Mock()
        self.letter_text.get = Mock(return_value="")
        self.letter_text.delete = Mock()
        self.letter_text.insert = Mock()

        self.notebook = Mock()
        self.notebook.select = Mock()


class TestDocumentTargetCompliance:
    """Verify MockDocumentTarget satisfies the protocol."""

    def test_mock_satisfies_protocol(self):
        from core.interfaces import DocumentTargetProtocol
        target = MockDocumentTarget()
        assert isinstance(target, DocumentTargetProtocol)


class TestBaseResultsDialogBoundary:
    """Test BaseResultsDialog._add_to_document with document_target."""

    def test_add_to_soap_uses_document_target(self):
        """When document_target is provided, _add_to_document uses it instead of parent."""
        from ui.dialogs.base_results_dialog import BaseResultsDialog

        target = MockDocumentTarget()
        parent = Mock()

        # BaseResultsDialog is abstract, so we create a concrete subclass
        class TestDialog(BaseResultsDialog):
            def _get_dialog_title(self):
                return "Test Results"
            def _format_results(self, results, result_type):
                return str(results)
            def _get_pdf_filename(self):
                return "test.pdf"

        dialog = TestDialog(parent, document_target=target)
        dialog.results_text = "Test analysis content"
        dialog.dialog = Mock()  # Mock the Toplevel

        # Patch messagebox to prevent UI popup
        with patch('ui.dialogs.base_results_dialog.messagebox'):
            dialog._add_to_document("soap")

        # Should use target's soap_text, not parent's
        target.soap_text.get.assert_called_once()
        target.soap_text.delete.assert_called_once()
        target.soap_text.insert.assert_called_once()
        target.notebook.select.assert_called_once_with(1)

        # Parent's widgets should NOT have been touched
        assert not hasattr(parent, 'soap_text') or not parent.soap_text.get.called

    def test_add_to_letter_uses_document_target(self):
        """Letter insertion also uses document_target."""
        from ui.dialogs.base_results_dialog import BaseResultsDialog

        target = MockDocumentTarget()
        parent = Mock()

        class TestDialog(BaseResultsDialog):
            def _get_dialog_title(self):
                return "Test Results"
            def _format_results(self, results, result_type):
                return str(results)
            def _get_pdf_filename(self):
                return "test.pdf"

        dialog = TestDialog(parent, document_target=target)
        dialog.results_text = "Letter content"
        dialog.dialog = Mock()

        with patch('ui.dialogs.base_results_dialog.messagebox'):
            dialog._add_to_document("letter")

        target.letter_text.get.assert_called_once()
        target.notebook.select.assert_called_once_with(3)

    def test_falls_back_to_parent_when_no_target(self):
        """Without document_target, falls back to self.parent."""
        from ui.dialogs.base_results_dialog import BaseResultsDialog

        parent = MockDocumentTarget()  # Parent has the same interface

        class TestDialog(BaseResultsDialog):
            def _get_dialog_title(self):
                return "Test Results"
            def _format_results(self, results, result_type):
                return str(results)
            def _get_pdf_filename(self):
                return "test.pdf"

        dialog = TestDialog(parent)  # No document_target
        dialog.results_text = "Fallback content"
        dialog.dialog = Mock()

        with patch('ui.dialogs.base_results_dialog.messagebox'):
            dialog._add_to_document("soap")

        # Should have used parent directly
        parent.soap_text.get.assert_called_once()
        parent.notebook.select.assert_called_once_with(1)

    def test_get_document_target_returns_target_when_set(self):
        from ui.dialogs.base_results_dialog import BaseResultsDialog

        target = MockDocumentTarget()
        parent = Mock()

        class TestDialog(BaseResultsDialog):
            def _get_dialog_title(self): return "T"
            def _format_results(self, r, t): return ""
            def _get_pdf_filename(self): return "t.pdf"

        dialog = TestDialog(parent, document_target=target)
        assert dialog._get_document_target() is target

    def test_get_document_target_returns_parent_when_none(self):
        from ui.dialogs.base_results_dialog import BaseResultsDialog

        parent = Mock()

        class TestDialog(BaseResultsDialog):
            def _get_dialog_title(self): return "T"
            def _format_results(self, r, t): return ""
            def _get_pdf_filename(self): return "t.pdf"

        dialog = TestDialog(parent)
        assert dialog._get_document_target() is parent


class TestMedicationResultsDialogBoundary:
    """Test MedicationResultsDialog accepts document_target."""

    def test_accepts_document_target_parameter(self):
        from ui.dialogs.medication_results_dialog import MedicationResultsDialog
        target = MockDocumentTarget()
        parent = Mock()
        dialog = MedicationResultsDialog(parent, document_target=target)
        assert dialog._document_target is target

    def test_add_to_document_uses_target(self):
        from ui.dialogs.medication_results_dialog import MedicationResultsDialog
        target = MockDocumentTarget()
        parent = Mock()
        dialog = MedicationResultsDialog(parent, document_target=target)
        dialog.analysis_text = "Medication analysis"

        with patch('ui.dialogs.medication_results_dialog.messagebox'):
            dialog._add_to_document("soap")

        target.soap_text.get.assert_called_once()
        target.notebook.select.assert_called_once_with(1)


class TestComplianceResultsDialogBoundary:
    """Test ComplianceResultsDialog accepts document_target."""

    def test_accepts_document_target_parameter(self):
        from ui.dialogs.compliance_results_dialog import ComplianceResultsDialog
        target = MockDocumentTarget()
        parent = Mock()
        dialog = ComplianceResultsDialog(parent, document_target=target)
        assert dialog._document_target is target

    def test_add_to_document_uses_target(self):
        from ui.dialogs.compliance_results_dialog import ComplianceResultsDialog
        target = MockDocumentTarget()
        parent = Mock()
        dialog = ComplianceResultsDialog(parent, document_target=target)
        dialog.analysis_text = "Compliance analysis"
        dialog.dialog = Mock()

        with patch('ui.dialogs.compliance_results_dialog.messagebox'):
            dialog._add_to_document("soap")

        target.soap_text.get.assert_called_once()
        target.notebook.select.assert_called_once_with(1)


class TestDiagnosticResultsDialogBoundary:
    """Test DiagnosticResultsDialog accepts document_target."""

    def test_accepts_document_target_parameter(self):
        from ui.dialogs.diagnostic import DiagnosticResultsDialog
        target = MockDocumentTarget()
        parent = Mock()
        dialog = DiagnosticResultsDialog(parent, document_target=target)
        assert dialog._document_target is target

    def test_add_to_document_uses_target(self):
        from ui.dialogs.diagnostic import DiagnosticResultsDialog
        target = MockDocumentTarget()
        parent = Mock()
        dialog = DiagnosticResultsDialog(parent, document_target=target)
        dialog.analysis_text = "Diagnostic analysis"
        dialog.result_text = Mock()
        dialog.result_text.winfo_toplevel = Mock(return_value=Mock())

        with patch('ui.dialogs.diagnostic.export.messagebox'):
            dialog._add_to_document("soap")

        target.soap_text.get.assert_called_once()
        target.notebook.select.assert_called_once_with(1)
