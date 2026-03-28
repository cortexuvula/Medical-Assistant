"""Tests for SOAP QA medication comparison and display mixin."""

import unittest
from unittest.mock import patch, Mock, MagicMock

from processing.soap_qa import compare_medications


class TestCompareMedications(unittest.TestCase):
    """Tests for compare_medications() pure function."""

    # --- Core matching ---

    def test_basic_omission(self):
        """Medication in transcript but not SOAP should be flagged."""
        transcript = "Patient takes metformin and lisinopril daily."
        soap = "Continue metformin 500mg twice daily."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 1)
        self.assertIn("lisinopril", warnings[0])

    def test_brand_generic_normalization(self):
        """Brand name in transcript matching generic in SOAP should not flag."""
        transcript = "Patient is on Zoloft for depression."
        soap = "Continue sertraline 50mg daily for depression."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 0)

    def test_generic_brand_normalization_reverse(self):
        """Generic in transcript matching brand in SOAP should not flag."""
        transcript = "Patient takes sertraline for anxiety."
        soap = "Continue Zoloft 50mg daily."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 0)

    def test_no_omissions(self):
        """Same medications in both should return empty list."""
        transcript = "Patient takes metformin and aspirin."
        soap = "Medications: metformin 500mg BID, aspirin 81mg daily."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 0)

    def test_multiple_omissions(self):
        """Multiple missing medications should each be flagged."""
        transcript = "Patient takes metformin, lisinopril, and atorvastatin."
        soap = "Assessment: Well controlled diabetes."
        warnings = compare_medications(transcript, soap)
        self.assertGreaterEqual(len(warnings), 2)

    def test_soap_only_medications_not_flagged(self):
        """Medications in SOAP but not transcript should NOT generate warnings."""
        transcript = "Patient complains of high blood pressure."
        soap = "Start lisinopril 10mg daily for hypertension."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 0)

    def test_no_medications_in_text(self):
        """Text with no medications should return empty list."""
        transcript = "Patient presents with headache and fatigue."
        soap = "Assessment: Tension headache. Plan: Rest and hydration."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 0)

    # --- Substring fallback ---

    def test_substring_fallback_normalized_name(self):
        """Normalized name appearing in SOAP raw text should not flag."""
        transcript = "Patient takes lisinopril daily."
        soap = "Plan: Continue lisinopril 20mg PO daily."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 0)

    def test_substring_fallback_original_text(self):
        """Original text from transcript appearing in SOAP should not flag."""
        # If NER extracts "Norvasc" from transcript (normalized: "amlodipine")
        # but SOAP says "Norvasc" literally without NER extracting it there,
        # the substring fallback on original text should catch it.
        transcript = "Patient was on Norvasc previously."
        soap = "Previously prescribed Norvasc, now discontinued."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 0)

    # --- Case handling ---

    def test_case_insensitivity(self):
        """Case differences should not cause false positives."""
        transcript = "METFORMIN prescribed for diabetes."
        soap = "Continue metformin for type 2 diabetes management."
        warnings = compare_medications(transcript, soap)
        self.assertEqual(len(warnings), 0)

    # --- Deduplication ---

    def test_multiple_mentions_single_warning(self):
        """Same medication mentioned multiple times should produce one warning."""
        transcript = (
            "Patient takes aspirin daily. "
            "Discussed aspirin dose. "
            "Continue aspirin 81mg."
        )
        soap = "No medications listed."
        warnings = compare_medications(transcript, soap)
        aspirin_warnings = [w for w in warnings if "aspirin" in w.lower()]
        self.assertEqual(len(aspirin_warnings), 1)

    # --- Edge cases / empty inputs ---

    def test_empty_transcript(self):
        """Empty transcript should return empty list."""
        warnings = compare_medications("", "Some SOAP note with metformin.")
        self.assertEqual(warnings, [])

    def test_empty_soap(self):
        """Empty SOAP should return empty list."""
        warnings = compare_medications("Patient takes metformin.", "")
        self.assertEqual(warnings, [])

    def test_both_empty(self):
        """Both empty should return empty list."""
        warnings = compare_medications("", "")
        self.assertEqual(warnings, [])

    def test_none_transcript(self):
        """None transcript should return empty list without crash."""
        warnings = compare_medications(None, "Some SOAP note.")
        self.assertEqual(warnings, [])

    def test_none_soap(self):
        """None SOAP should return empty list without crash."""
        warnings = compare_medications("Patient takes metformin.", None)
        self.assertEqual(warnings, [])

    # --- Warning format ---

    def test_warning_format_includes_medication_name(self):
        """Warning strings should include the medication name."""
        transcript = "Patient takes amlodipine for hypertension."
        soap = "Assessment: Hypertension. Plan: Follow up in 2 weeks."
        warnings = compare_medications(transcript, soap)
        self.assertTrue(len(warnings) > 0)
        self.assertTrue(any("amlodipine" in w.lower() for w in warnings))

    def test_warning_format_brand_shows_both_names(self):
        """When brand name differs from normalized, both should appear."""
        transcript = "Patient takes Norvasc daily."
        soap = "Assessment: Hypertension controlled."
        warnings = compare_medications(transcript, soap)
        # Should show original "Norvasc" and normalized "amlodipine"
        self.assertTrue(len(warnings) > 0)
        warning_text = warnings[0].lower()
        self.assertIn("norvasc", warning_text)
        self.assertIn("amlodipine", warning_text)

    def test_warning_format_generic_shows_single_name(self):
        """When original text matches normalized name, show once."""
        transcript = "Patient takes amlodipine daily."
        soap = "Assessment: Hypertension controlled."
        warnings = compare_medications(transcript, soap)
        self.assertTrue(len(warnings) > 0)
        # Should NOT show name twice
        self.assertIn("amlodipine", warnings[0].lower())

    def test_warnings_sorted_alphabetically(self):
        """Warnings should be in alphabetical order by medication name."""
        transcript = "Patient takes metformin, aspirin, and lisinopril."
        soap = "Assessment: No medications documented."
        warnings = compare_medications(transcript, soap)
        # Extract medication names and check sort order
        self.assertGreaterEqual(len(warnings), 2)
        med_names = [w.split('"')[1].lower() for w in warnings]
        self.assertEqual(med_names, sorted(med_names))

    # --- Error resilience ---

    def test_ner_failure_returns_empty(self):
        """If NER extractor fails, should return empty list gracefully."""
        with patch(
            'rag.medical_ner.get_medical_ner_extractor',
            side_effect=Exception("NER failed")
        ):
            warnings = compare_medications(
                "Patient takes metformin.", "Some SOAP note."
            )
            self.assertEqual(warnings, [])

    def test_extractor_returns_empty_entities(self):
        """If NER returns no entities for either text, no crash."""
        mock_extractor = Mock()
        mock_extractor._extract_medications.return_value = []
        with patch(
            'rag.medical_ner.get_medical_ner_extractor',
            return_value=mock_extractor
        ):
            warnings = compare_medications(
                "Some text without meds.", "Some SOAP without meds."
            )
            self.assertEqual(warnings, [])


class TestSOAPQAGeneratorMixin(unittest.TestCase):
    """Tests for SOAPQAGeneratorMixin display mixin."""

    def _make_mixin(self, widget=None, has_ui=True):
        """Create a mixin instance with mocked app."""
        from processing.generators.soap_qa import SOAPQAGeneratorMixin

        class TestMixin(SOAPQAGeneratorMixin):
            def _update_analysis_panel(self, widget, content):
                self._last_panel_content = content

        mixin = TestMixin()
        mixin.app = Mock()
        mixin._last_panel_content = None

        if has_ui:
            mixin.app.ui = Mock()
            mixin.app.ui.components = {}
            if widget is not None:
                mixin.app.ui.components['soap_qa_text'] = widget
        else:
            # No ui attribute
            del mixin.app.ui

        return mixin

    def test_get_widget_returns_widget_when_present(self):
        """Widget retrieval returns the registered widget."""
        widget = Mock()
        mixin = self._make_mixin(widget=widget)
        result = mixin._get_soap_qa_widget()
        self.assertIs(result, widget)

    def test_get_widget_returns_none_when_missing(self):
        """Widget retrieval returns None if widget not registered."""
        mixin = self._make_mixin(widget=None)
        result = mixin._get_soap_qa_widget()
        self.assertIsNone(result)

    def test_get_widget_returns_none_when_no_ui(self):
        """Widget retrieval returns None if app has no ui attribute."""
        mixin = self._make_mixin(has_ui=False)
        result = mixin._get_soap_qa_widget()
        self.assertIsNone(result)

    def test_panel_no_warnings_shows_success_message(self):
        """Empty warnings list should show 'no omissions' message."""
        widget = Mock()
        mixin = self._make_mixin(widget=widget)
        mixin._run_soap_qa_to_panel([])
        self.assertIn("No medication omissions", mixin._last_panel_content)

    def test_panel_with_warnings_shows_numbered_list(self):
        """Warnings should be displayed as numbered list."""
        widget = Mock()
        mixin = self._make_mixin(widget=widget)
        warnings = ['"lisinopril" mentioned in transcript but not found in SOAP note']
        mixin._run_soap_qa_to_panel(warnings)
        self.assertIn("1.", mixin._last_panel_content)
        self.assertIn("lisinopril", mixin._last_panel_content)
        self.assertIn("Medication QA (1 potential omission(s))", mixin._last_panel_content)

    def test_panel_with_warnings_flashes_status_bar(self):
        """Warnings should trigger status bar warning."""
        widget = Mock()
        mixin = self._make_mixin(widget=widget)
        warnings = ['"lisinopril" mentioned in transcript but not found in SOAP note']
        mixin._run_soap_qa_to_panel(warnings)
        mixin.app.status_manager.warning.assert_called_once()
        call_msg = mixin.app.status_manager.warning.call_args[0][0]
        self.assertIn("1 potential omission", call_msg)

    def test_panel_no_warnings_no_status_warning(self):
        """Empty warnings should not trigger status bar warning."""
        widget = Mock()
        mixin = self._make_mixin(widget=widget)
        mixin._run_soap_qa_to_panel([])
        mixin.app.status_manager.warning.assert_not_called()

    def test_panel_missing_widget_returns_early(self):
        """If widget not found, method should return without error."""
        mixin = self._make_mixin(widget=None)
        # Should not raise
        mixin._run_soap_qa_to_panel(["some warning"])
        mixin.app.status_manager.warning.assert_not_called()

    def test_panel_multiple_warnings_count(self):
        """Multiple warnings should show correct count in header."""
        widget = Mock()
        mixin = self._make_mixin(widget=widget)
        warnings = [
            '"lisinopril" mentioned in transcript but not found in SOAP note',
            '"metformin" mentioned in transcript but not found in SOAP note',
            '"aspirin" mentioned in transcript but not found in SOAP note',
        ]
        mixin._run_soap_qa_to_panel(warnings)
        self.assertIn("3 potential omission(s)", mixin._last_panel_content)
        self.assertIn("3.", mixin._last_panel_content)


class TestSOAPQAComposition(unittest.TestCase):
    """Tests for SOAP QA integration into DocumentGenerators."""

    def test_document_generators_has_soap_qa_mixin(self):
        """DocumentGenerators should include SOAPQAGeneratorMixin methods."""
        from processing.generators import DocumentGenerators
        assert hasattr(DocumentGenerators, '_run_soap_qa_to_panel')
        assert hasattr(DocumentGenerators, '_get_soap_qa_widget')

    def test_soap_qa_import_in_generators_init(self):
        """SOAPQAGeneratorMixin should be importable from generators package."""
        from processing.generators import SOAPQAGeneratorMixin
        assert SOAPQAGeneratorMixin is not None

    def test_compare_medications_importable(self):
        """compare_medications should be importable from processing.soap_qa."""
        from processing.soap_qa import compare_medications
        assert callable(compare_medications)


if __name__ == '__main__':
    unittest.main()
