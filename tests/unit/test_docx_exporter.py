"""
Tests for src/exporters/docx_exporter.py
No network, no Tkinter. Uses python-docx which is installed.
"""
import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from exporters.docx_exporter import DocxExporter, get_docx_exporter
from exporters.base_exporter import BaseExporter


# ---------------------------------------------------------------------------
# TestDocxExporterInit
# ---------------------------------------------------------------------------

class TestDocxExporterInit:
    """DocxExporter construction tests."""

    def test_creates_with_no_args(self):
        exp = DocxExporter()
        assert exp is not None

    def test_default_clinic_name_is_empty(self):
        exp = DocxExporter()
        assert exp.clinic_name == ""

    def test_default_doctor_name_is_empty(self):
        exp = DocxExporter()
        assert exp.doctor_name == ""

    def test_stores_clinic_name(self):
        exp = DocxExporter(clinic_name="Sunrise Clinic")
        assert exp.clinic_name == "Sunrise Clinic"

    def test_stores_doctor_name(self):
        exp = DocxExporter(doctor_name="Dr. Adams")
        assert exp.doctor_name == "Dr. Adams"

    def test_stores_both_names(self):
        exp = DocxExporter(clinic_name="River Clinic", doctor_name="Dr. River")
        assert exp.clinic_name == "River Clinic"
        assert exp.doctor_name == "Dr. River"

    def test_is_base_exporter_subclass(self):
        exp = DocxExporter()
        assert isinstance(exp, BaseExporter)

    def test_last_error_is_none_on_init(self):
        exp = DocxExporter()
        assert exp.last_error is None

    def test_clinic_name_empty_string_preserved(self):
        exp = DocxExporter(clinic_name="")
        assert exp.clinic_name == ""

    def test_doctor_name_empty_string_preserved(self):
        exp = DocxExporter(doctor_name="")
        assert exp.doctor_name == ""

    def test_unicode_clinic_name_stored(self):
        exp = DocxExporter(clinic_name="Clínica Médica")
        assert exp.clinic_name == "Clínica Médica"

    def test_unicode_doctor_name_stored(self):
        exp = DocxExporter(doctor_name="Dr. Müller")
        assert exp.doctor_name == "Dr. Müller"


# ---------------------------------------------------------------------------
# TestSetLetterhead
# ---------------------------------------------------------------------------

class TestSetLetterhead:
    """DocxExporter.set_letterhead tests."""

    def test_updates_clinic_name(self):
        exp = DocxExporter()
        exp.set_letterhead("Updated Clinic", "")
        assert exp.clinic_name == "Updated Clinic"

    def test_updates_doctor_name(self):
        exp = DocxExporter()
        exp.set_letterhead("", "Dr. Updated")
        assert exp.doctor_name == "Dr. Updated"

    def test_updates_both_at_once(self):
        exp = DocxExporter()
        exp.set_letterhead("Both Clinic", "Dr. Both")
        assert exp.clinic_name == "Both Clinic"
        assert exp.doctor_name == "Dr. Both"

    def test_overwrites_existing_clinic_name(self):
        exp = DocxExporter(clinic_name="Old Clinic")
        exp.set_letterhead("New Clinic", "Dr. X")
        assert exp.clinic_name == "New Clinic"

    def test_overwrites_existing_doctor_name(self):
        exp = DocxExporter(doctor_name="Old Doctor")
        exp.set_letterhead("Clinic", "New Doctor")
        assert exp.doctor_name == "New Doctor"

    def test_can_clear_names_with_empty_strings(self):
        exp = DocxExporter(clinic_name="Clinic", doctor_name="Doctor")
        exp.set_letterhead("", "")
        assert exp.clinic_name == ""
        assert exp.doctor_name == ""

    def test_returns_none(self):
        exp = DocxExporter()
        result = exp.set_letterhead("Clinic", "Doctor")
        assert result is None

    def test_multiple_calls_last_one_wins(self):
        exp = DocxExporter()
        exp.set_letterhead("First", "First Doctor")
        exp.set_letterhead("Second", "Second Doctor")
        assert exp.clinic_name == "Second"
        assert exp.doctor_name == "Second Doctor"


# ---------------------------------------------------------------------------
# TestParseSoapText
# ---------------------------------------------------------------------------

class TestParseSoapText:
    """DocxExporter._parse_soap_text tests."""

    def _exp(self):
        return DocxExporter()

    def test_full_soap_returns_dict_with_four_keys(self):
        text = (
            "Subjective\nPatient c/o headache.\n\n"
            "Objective\nBP 120/80.\n\n"
            "Assessment\nTension headache.\n\n"
            "Plan\nRest and fluids."
        )
        result = self._exp()._parse_soap_text(text)
        assert set(result.keys()) == {"subjective", "objective", "assessment", "plan"}

    def test_subjective_content_captured(self):
        text = "Subjective\nPatient reports fatigue.\n\nObjective\nAfebrile."
        result = self._exp()._parse_soap_text(text)
        assert "fatigue" in result["subjective"]

    def test_objective_content_captured(self):
        text = "Subjective\nCough.\n\nObjective\nChest clear on auscultation."
        result = self._exp()._parse_soap_text(text)
        assert "auscultation" in result["objective"]

    def test_assessment_content_captured(self):
        text = "Assessment\nType 2 Diabetes Mellitus.\n\nPlan\nMetformin 500mg."
        result = self._exp()._parse_soap_text(text)
        assert "Diabetes" in result["assessment"]

    def test_plan_content_captured(self):
        text = "Subjective\nFever.\n\nPlan\nAcetaminophen PRN."
        result = self._exp()._parse_soap_text(text)
        assert "Acetaminophen" in result["plan"]

    def test_no_headers_returns_text_in_subjective(self):
        text = "Random clinical notes without any section markers."
        result = self._exp()._parse_soap_text(text)
        assert result["subjective"] == text

    def test_no_headers_other_sections_empty(self):
        text = "No headers here."
        result = self._exp()._parse_soap_text(text)
        assert result["objective"] == ""
        assert result["assessment"] == ""
        assert result["plan"] == ""

    def test_empty_string_subjective_equals_empty(self):
        result = self._exp()._parse_soap_text("")
        # Empty text: all values empty but subjective gets assigned ""
        # The "if not any" branch fires; subjective = ""
        assert result["subjective"] == ""

    def test_short_header_s_colon(self):
        text = "S:\nShortness of breath.\n\nO:\nRR 18."
        result = self._exp()._parse_soap_text(text)
        assert "breath" in result["subjective"]

    def test_short_header_o_colon(self):
        text = "S:\nChest pain.\n\nO:\nHeart rate 90 bpm."
        result = self._exp()._parse_soap_text(text)
        assert "90" in result["objective"]

    def test_short_header_a_colon(self):
        text = "A:\nAngina pectoris.\n\nP:\nNitrates PRN."
        result = self._exp()._parse_soap_text(text)
        assert "Angina" in result["assessment"]

    def test_short_header_p_colon(self):
        text = "A:\nHypertension.\n\nP:\nLisinopril 10mg daily."
        result = self._exp()._parse_soap_text(text)
        assert "Lisinopril" in result["plan"]

    def test_case_insensitive_headers(self):
        text = "SUBJECTIVE\nCough productive.\n\nOBJECTIVE\nLungs clear."
        result = self._exp()._parse_soap_text(text)
        assert "productive" in result["subjective"]
        assert "clear" in result["objective"]

    def test_mixed_case_headers(self):
        text = "Subjective\nDizziness.\n\nassessment\nBPPV."
        result = self._exp()._parse_soap_text(text)
        assert "Dizziness" in result["subjective"]
        assert "BPPV" in result["assessment"]

    def test_returns_dict_type(self):
        result = self._exp()._parse_soap_text("Anything")
        assert isinstance(result, dict)

    def test_all_four_sections_always_present_as_keys(self):
        result = self._exp()._parse_soap_text("Only plan section\nPlan\nFollow up.")
        assert "subjective" in result
        assert "objective" in result
        assert "assessment" in result
        assert "plan" in result

    def test_multiline_section_content(self):
        text = (
            "Subjective\nLine 1.\nLine 2.\nLine 3.\n\n"
            "Assessment\nDiagnosis."
        )
        result = self._exp()._parse_soap_text(text)
        assert "Line 1" in result["subjective"]
        assert "Line 2" in result["subjective"]
        assert "Line 3" in result["subjective"]

    def test_chief_complaint_maps_to_subjective(self):
        text = "Chief Complaint\nPatient has knee pain."
        result = self._exp()._parse_soap_text(text)
        assert "knee pain" in result["subjective"]

    def test_plan_section_alone(self):
        text = "Plan\nFollow-up in 2 weeks."
        result = self._exp()._parse_soap_text(text)
        assert "Follow-up" in result["plan"]


# ---------------------------------------------------------------------------
# TestValidateContent
# ---------------------------------------------------------------------------

class TestValidateContent:
    """DocxExporter._validate_content tests (inherited from BaseExporter)."""

    def _exp(self):
        return DocxExporter()

    def test_all_required_keys_present_returns_true(self):
        exp = self._exp()
        assert exp._validate_content({"a": 1, "b": 2}, ["a", "b"]) is True

    def test_all_required_keys_present_last_error_unchanged(self):
        exp = self._exp()
        exp._validate_content({"a": 1}, ["a"])
        assert exp.last_error is None

    def test_missing_key_returns_false(self):
        exp = self._exp()
        assert exp._validate_content({"a": 1}, ["a", "missing"]) is False

    def test_missing_key_sets_last_error(self):
        exp = self._exp()
        exp._validate_content({"a": 1}, ["a", "missing"])
        assert exp.last_error is not None
        assert "missing" in exp.last_error.lower() or "Missing" in exp.last_error

    def test_empty_content_with_required_key_returns_false(self):
        exp = self._exp()
        assert exp._validate_content({}, ["required"]) is False

    def test_empty_required_keys_list_returns_true(self):
        exp = self._exp()
        assert exp._validate_content({"any": "data"}, []) is True

    def test_multiple_missing_keys_returns_false(self):
        exp = self._exp()
        assert exp._validate_content({}, ["x", "y", "z"]) is False

    def test_last_error_mentions_missing_key_name(self):
        exp = self._exp()
        exp._validate_content({"a": 1}, ["a", "expected_key"])
        assert "expected_key" in exp.last_error


# ---------------------------------------------------------------------------
# TestExportToString
# ---------------------------------------------------------------------------

class TestExportToString:
    """DocxExporter.export_to_string tests."""

    def _exp(self):
        return DocxExporter()

    def test_returns_string(self):
        exp = self._exp()
        result = exp.export_to_string({"content": "hello"})
        assert isinstance(result, str)

    def test_plain_text_content_returned_as_is(self):
        exp = self._exp()
        result = exp.export_to_string({"content": "Simple plain text."})
        assert result == "Simple plain text."

    def test_dict_content_with_subjective_included(self):
        exp = self._exp()
        result = exp.export_to_string({
            "content": {"subjective": "S content", "objective": "", "assessment": "", "plan": ""}
        })
        assert "S content" in result

    def test_dict_content_with_all_sections(self):
        exp = self._exp()
        result = exp.export_to_string({
            "content": {
                "subjective": "Sub text",
                "objective": "Obj text",
                "assessment": "Ass text",
                "plan": "Plan text",
            }
        })
        assert "Sub text" in result
        assert "Obj text" in result
        assert "Ass text" in result
        assert "Plan text" in result

    def test_dict_content_section_headers_uppercased(self):
        exp = self._exp()
        result = exp.export_to_string({
            "content": {"subjective": "Some text", "objective": "", "assessment": "", "plan": ""}
        })
        assert "SUBJECTIVE" in result

    def test_dict_content_empty_sections_not_included(self):
        exp = self._exp()
        result = exp.export_to_string({
            "content": {"subjective": "", "objective": "", "assessment": "", "plan": ""}
        })
        assert result == ""

    def test_missing_content_key_returns_empty_string(self):
        exp = self._exp()
        result = exp.export_to_string({})
        assert result == ""

    def test_non_dict_non_string_content_converted(self):
        exp = self._exp()
        result = exp.export_to_string({"content": 42})
        assert result == "42"

    def test_dict_with_only_plan_returns_plan_only(self):
        exp = self._exp()
        result = exp.export_to_string({
            "content": {
                "subjective": "",
                "objective": "",
                "assessment": "",
                "plan": "Follow-up in 4 weeks.",
            }
        })
        assert "PLAN" in result
        assert "Follow-up" in result
        assert "SUBJECTIVE" not in result


# ---------------------------------------------------------------------------
# TestGetDocxExporter
# ---------------------------------------------------------------------------

class TestGetDocxExporter:
    """get_docx_exporter factory function tests."""

    def test_returns_docx_exporter_instance(self):
        result = get_docx_exporter()
        assert isinstance(result, DocxExporter)

    def test_default_clinic_name_empty(self):
        result = get_docx_exporter()
        assert result.clinic_name == ""

    def test_default_doctor_name_empty(self):
        result = get_docx_exporter()
        assert result.doctor_name == ""

    def test_with_clinic_name(self):
        result = get_docx_exporter(clinic_name="Valley Clinic")
        assert result.clinic_name == "Valley Clinic"

    def test_with_doctor_name(self):
        result = get_docx_exporter(doctor_name="Dr. Valley")
        assert result.doctor_name == "Dr. Valley"

    def test_with_both_names(self):
        result = get_docx_exporter(clinic_name="Peak Clinic", doctor_name="Dr. Peak")
        assert result.clinic_name == "Peak Clinic"
        assert result.doctor_name == "Dr. Peak"

    def test_returns_new_instance_each_call(self):
        a = get_docx_exporter()
        b = get_docx_exporter()
        assert a is not b

    def test_is_base_exporter_subclass(self):
        result = get_docx_exporter()
        assert isinstance(result, BaseExporter)

    def test_last_error_is_none_on_new_instance(self):
        result = get_docx_exporter()
        assert result.last_error is None
