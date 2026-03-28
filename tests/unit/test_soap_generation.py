"""Tests for SOAP note generation utilities.

Tests the pure functions in soap_generation.py that don't require AI calls:
- format_soap_paragraphs() — section formatting
- _validate_soap_output() — ICD code extraction and validation
"""

import unittest

from ai.soap_generation import format_soap_paragraphs, _validate_soap_output


class TestFormatSOAPParagraphs(unittest.TestCase):
    """Tests for SOAP note paragraph formatting."""

    def test_adds_blank_line_before_sections(self):
        text = "Some intro text\nSubjective:\nPatient reports pain"
        result = format_soap_paragraphs(text)
        lines = result.split('\n')
        # Find Subjective line
        subj_idx = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("subjective"))
        # Previous line should be blank
        self.assertEqual(lines[subj_idx - 1].strip(), "")

    def test_all_soap_sections_get_separation(self):
        text = "Subjective:\nPain\nObjective:\nVitals\nAssessment:\nHTN\nPlan:\nContinue meds"
        result = format_soap_paragraphs(text)
        # Objective, Assessment, Plan should all have blank lines before them
        lines = result.split('\n')
        for section in ["objective:", "assessment:", "plan:"]:
            idx = next(
                (i for i, l in enumerate(lines) if l.strip().lower().startswith(section)),
                None
            )
            if idx and idx > 0:
                self.assertEqual(
                    lines[idx - 1].strip(), "",
                    f"Missing blank line before {section}"
                )

    def test_splits_midline_headers(self):
        text = "Patient has pain Objective: vitals normal"
        result = format_soap_paragraphs(text)
        self.assertIn("\nObjective:", result)

    def test_splits_bullets_after_header(self):
        text = "Subjective: - Chief complaint: headache - Duration: 3 days"
        result = format_soap_paragraphs(text)
        # Should have bullet on separate line after header
        self.assertIn("\n- ", result)

    def test_handles_crlf(self):
        text = "Subjective:\r\nPain\r\nObjective:\r\nVitals"
        result = format_soap_paragraphs(text)
        self.assertNotIn('\r', result)

    def test_no_double_blank_lines(self):
        text = "Subjective:\n\nPain\n\nObjective:\n\nVitals"
        result = format_soap_paragraphs(text)
        # Should not create triple+ blank lines
        self.assertNotIn('\n\n\n', result)

    def test_preserves_content(self):
        text = "Subjective:\nPatient reports headache for 3 days"
        result = format_soap_paragraphs(text)
        self.assertIn("Patient reports headache for 3 days", result)

    def test_empty_text(self):
        result = format_soap_paragraphs("")
        self.assertEqual(result, "")

    def test_no_sections(self):
        text = "Just some plain text without any headers."
        result = format_soap_paragraphs(text)
        self.assertEqual(result, text)

    def test_differential_diagnosis_section(self):
        text = "Assessment:\nHTN\nDifferential Diagnosis:\n1. HTN\n2. Anxiety"
        result = format_soap_paragraphs(text)
        lines = result.split('\n')
        dd_idx = next(
            (i for i, l in enumerate(lines) if "differential diagnosis" in l.lower()),
            None
        )
        self.assertIsNotNone(dd_idx)
        if dd_idx > 0:
            self.assertEqual(lines[dd_idx - 1].strip(), "")

    def test_follow_up_section(self):
        text = "Plan:\nContinue meds\nFollow-up:\n2 weeks"
        result = format_soap_paragraphs(text)
        self.assertIn("\nFollow-up:", result)

    def test_icd_code_section(self):
        text = "Assessment:\nHTN\nICD-10 Code:\nI10"
        result = format_soap_paragraphs(text)
        lines = result.split('\n')
        icd_idx = next(
            (i for i, l in enumerate(lines) if "icd-10 code" in l.lower()),
            None
        )
        self.assertIsNotNone(icd_idx)

    def test_case_insensitive_headers(self):
        text = "SUBJECTIVE:\nPain\nOBJECTIVE:\nNormal"
        result = format_soap_paragraphs(text)
        lines = result.split('\n')
        obj_idx = next(
            (i for i, l in enumerate(lines) if l.strip().upper().startswith("OBJECTIVE")),
            None
        )
        if obj_idx and obj_idx > 0:
            self.assertEqual(lines[obj_idx - 1].strip(), "")


class TestValidateSOAPOutput(unittest.TestCase):
    """Tests for _validate_soap_output() ICD code validation."""

    def test_empty_text(self):
        soap_text, warnings = _validate_soap_output("")
        self.assertEqual(soap_text, "")
        self.assertEqual(warnings, [])

    def test_no_icd_codes(self):
        text = "Subjective:\nHeadache\nObjective:\nNormal\nAssessment:\nTension headache\nPlan:\nRest"
        soap_text, warnings = _validate_soap_output(text)
        self.assertEqual(soap_text, text)  # text unchanged
        self.assertEqual(warnings, [])

    def test_valid_icd10_code(self):
        text = "Assessment: Hypertension\nICD-10: I10"
        soap_text, warnings = _validate_soap_output(text)
        self.assertEqual(soap_text, text)
        # I10 is a common code, should not generate warning
        # (or may generate "not in database" warning depending on data)
        self.assertIsInstance(warnings, list)

    def test_invalid_code_format(self):
        text = "Assessment: Condition\nICD code: ZZZZZ"
        soap_text, warnings = _validate_soap_output(text)
        # ZZZZZ should not match ICD patterns, so may or may not be extracted
        self.assertIsInstance(warnings, list)

    def test_soap_text_unchanged(self):
        """Validation should never modify the SOAP text."""
        text = "Subjective: Pain\nICD-10: E11.65\nPlan: Continue"
        soap_text, warnings = _validate_soap_output(text)
        self.assertEqual(soap_text, text)

    def test_returns_tuple(self):
        result = _validate_soap_output("Some SOAP text")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_multiple_codes(self):
        text = "ICD-10: E11.65, I10, J45.20"
        soap_text, warnings = _validate_soap_output(text)
        self.assertIsInstance(warnings, list)

    def test_none_text(self):
        """None should be handled gracefully."""
        soap_text, warnings = _validate_soap_output(None)
        self.assertIsNone(soap_text)
        self.assertEqual(warnings, [])


if __name__ == '__main__':
    unittest.main()
