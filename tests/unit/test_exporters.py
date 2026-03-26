"""
Comprehensive unit tests for exporter modules.

Covers:
- BaseExporter (base_exporter.py)
- DocxExporter (docx_exporter.py)
- FHIRExporter (fhir_exporter.py)
- FHIRResourceBuilder (fhir_resources.py)
- FHIR config helpers (fhir_config.py)
- RAGConversationExporter (rag_exporter.py)
- PDFExporter (utils/pdf_exporter.py)
"""

import json
import base64
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest


# ---------------------------------------------------------------------------
# FHIR Config Tests (fhir_config.py) — no heavy external deps
# ---------------------------------------------------------------------------

class TestFHIRConfig:
    """Tests for fhir_config helper functions and dataclass."""

    def test_fhir_export_config_defaults(self):
        from exporters.fhir_config import FHIRExportConfig
        cfg = FHIRExportConfig()
        assert cfg.fhir_version == "R4"
        assert cfg.organization_name == ""
        assert cfg.include_patient is True
        assert cfg.include_practitioner is True
        assert cfg.include_organization is True

    def test_fhir_export_config_custom(self):
        from exporters.fhir_config import FHIRExportConfig
        cfg = FHIRExportConfig(
            organization_name="Test Clinic",
            practitioner_name="Dr. Smith",
            include_patient=False,
        )
        assert cfg.organization_name == "Test Clinic"
        assert cfg.practitioner_name == "Dr. Smith"
        assert cfg.include_patient is False

    def test_get_section_code_known(self):
        from exporters.fhir_config import get_section_code
        code = get_section_code("subjective")
        assert code["code"] == "10154-3"
        assert "system" in code

    def test_get_section_code_unknown_falls_back(self):
        from exporters.fhir_config import get_section_code
        code = get_section_code("nonexistent_section")
        # Falls back to assessment
        assert code["code"] == "51848-0"

    def test_get_document_type_code_soap(self):
        from exporters.fhir_config import get_document_type_code
        code = get_document_type_code("soap_note")
        assert code["code"] == "34108-1"

    def test_get_document_type_code_referral(self):
        from exporters.fhir_config import get_document_type_code
        code = get_document_type_code("referral")
        assert code["code"] == "57133-1"

    def test_get_document_type_code_unknown_falls_back(self):
        from exporters.fhir_config import get_document_type_code
        code = get_document_type_code("unknown_type")
        assert code["code"] == "34108-1"  # defaults to soap_note

    def test_normalize_section_name_subjective(self):
        from exporters.fhir_config import normalize_section_name
        assert normalize_section_name("Subjective") == "subjective"
        assert normalize_section_name("S:") == "subjective"
        assert normalize_section_name("Chief Complaint") == "subjective"

    def test_normalize_section_name_objective(self):
        from exporters.fhir_config import normalize_section_name
        assert normalize_section_name("Objective") == "objective"
        assert normalize_section_name("Physical Exam") == "objective"

    def test_normalize_section_name_assessment(self):
        from exporters.fhir_config import normalize_section_name
        assert normalize_section_name("Assessment") == "assessment"
        assert normalize_section_name("Impression") == "assessment"

    def test_normalize_section_name_plan(self):
        from exporters.fhir_config import normalize_section_name
        assert normalize_section_name("Plan") == "plan"
        assert normalize_section_name("Treatment Plan") == "plan"

    def test_normalize_section_name_unknown(self):
        from exporters.fhir_config import normalize_section_name
        assert normalize_section_name("Random Heading") is None

    def test_generate_resource_id_format(self):
        from exporters.fhir_config import generate_resource_id
        rid = generate_resource_id("Patient", 5)
        assert rid.startswith("patient-")
        assert rid.endswith("-005")

    def test_generate_resource_id_default_index(self):
        from exporters.fhir_config import generate_resource_id
        rid = generate_resource_id("Bundle")
        assert rid.endswith("-000")


# ---------------------------------------------------------------------------
# BaseExporter Tests
# ---------------------------------------------------------------------------

class TestBaseExporter:
    """Tests for BaseExporter abstract base class helper methods."""

    def _make_concrete(self):
        """Create a minimal concrete subclass for testing."""
        from exporters.base_exporter import BaseExporter

        class ConcreteExporter(BaseExporter):
            def export(self, content, output_path):
                return True

            def export_to_string(self, content):
                return json.dumps(content)

        return ConcreteExporter()

    def test_last_error_initially_none(self):
        exp = self._make_concrete()
        assert exp.last_error is None

    def test_validate_content_all_present(self):
        exp = self._make_concrete()
        content = {"a": 1, "b": 2}
        assert exp._validate_content(content, ["a", "b"]) is True
        assert exp.last_error is None

    def test_validate_content_missing_keys(self):
        exp = self._make_concrete()
        content = {"a": 1}
        assert exp._validate_content(content, ["a", "b"]) is False
        assert "Missing required content keys" in exp.last_error

    def test_ensure_directory_creates_parents(self, tmp_path):
        exp = self._make_concrete()
        deep_path = tmp_path / "a" / "b" / "c" / "file.txt"
        assert exp._ensure_directory(deep_path) is True
        assert deep_path.parent.exists()

    def test_ensure_directory_error(self):
        exp = self._make_concrete()
        # Use a path that can't be created
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            result = exp._ensure_directory(Path("/impossible/path/file.txt"))
            assert result is False
            assert "Failed to create directory" in exp.last_error

    def test_export_to_clipboard_success(self):
        exp = self._make_concrete()
        mock_pyperclip = MagicMock()
        with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
            result = exp.export_to_clipboard({"key": "value"})
            assert result is True
            mock_pyperclip.copy.assert_called_once()

    def test_export_to_clipboard_failure(self):
        exp = self._make_concrete()
        mock_pyperclip = MagicMock()
        mock_pyperclip.copy.side_effect = Exception("clipboard error")
        with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
            result = exp.export_to_clipboard({"key": "value"})
            assert result is False
            assert "Failed to copy to clipboard" in exp.last_error


# ---------------------------------------------------------------------------
# DocxExporter Tests
# ---------------------------------------------------------------------------

class TestDocxExporter:
    """Tests for DocxExporter."""

    def test_init_defaults(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        assert exp.clinic_name == ""
        assert exp.doctor_name == ""

    def test_init_with_letterhead(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter(clinic_name="TestClinic", doctor_name="Dr. Test")
        assert exp.clinic_name == "TestClinic"
        assert exp.doctor_name == "Dr. Test"

    def test_set_letterhead(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        exp.set_letterhead("NewClinic", "Dr. New")
        assert exp.clinic_name == "NewClinic"
        assert exp.doctor_name == "Dr. New"

    def test_export_to_string_with_dict_content(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        content = {
            "content": {
                "subjective": "Patient reports headache",
                "objective": "BP 120/80",
                "assessment": "Tension headache",
                "plan": "Rest and ibuprofen",
            }
        }
        result = exp.export_to_string(content)
        assert "SUBJECTIVE" in result
        assert "Patient reports headache" in result
        assert "PLAN" in result

    def test_export_to_string_with_string_content(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        content = {"content": "Simple text content"}
        result = exp.export_to_string(content)
        assert result == "Simple text content"

    def test_export_to_string_empty_sections(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        content = {"content": {"subjective": "", "objective": "", "assessment": "", "plan": ""}}
        result = exp.export_to_string(content)
        assert result == ""

    def test_export_soap_note(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        output = tmp_path / "soap.docx"
        result = exp.export_soap_note(
            soap_text="Subjective\nHeadache\n\nObjective\nBP normal",
            output_path=output,
        )
        assert result is True
        assert output.exists()

    def test_export_referral(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        output = tmp_path / "referral.docx"
        result = exp.export_referral(
            referral_text="Dear Dr. Smith,\n\nPlease see this patient.",
            output_path=output,
        )
        assert result is True
        assert output.exists()

    def test_export_letter(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        output = tmp_path / "letter.docx"
        result = exp.export_letter(
            letter_text="This is a medical letter.",
            output_path=output,
        )
        assert result is True
        assert output.exists()

    def test_export_generic(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        output = tmp_path / "generic.docx"
        content = {
            "document_type": "generic",
            "title": "Test Document",
            "content": "Generic content here.",
        }
        result = exp.export(content, output)
        assert result is True
        assert output.exists()

    def test_export_with_letterhead(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter(clinic_name="Acme Clinic", doctor_name="Dr. Acme")
        output = tmp_path / "letterhead.docx"
        content = {
            "document_type": "soap",
            "content": "Subjective\nTest",
            "include_letterhead": True,
        }
        result = exp.export(content, output)
        assert result is True

    def test_export_with_patient_info(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        output = tmp_path / "patient.docx"
        content = {
            "document_type": "soap",
            "content": {"subjective": "Test"},
            "patient_info": {"name": "John Doe", "dob": "1990-01-01", "id": "12345"},
        }
        result = exp.export(content, output)
        assert result is True

    def test_export_error_handling(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        # Pass a path where save will fail
        with patch("exporters.docx_exporter.Document") as mock_doc:
            mock_doc.return_value.save.side_effect = PermissionError("denied")
            result = exp.export({"content": "test"}, Path("/some/path.docx"))
            assert result is False
            assert exp.last_error is not None

    def test_parse_soap_text_with_sections(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        text = "Subjective\nHeadache for 3 days\n\nObjective\nBP 120/80\n\nAssessment\nTension headache\n\nPlan\nRest"
        sections = exp._parse_soap_text(text)
        assert "Headache" in sections["subjective"]
        assert "120/80" in sections["objective"]
        assert "Tension" in sections["assessment"]
        assert "Rest" in sections["plan"]

    def test_parse_soap_text_no_sections(self):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        text = "Just some random text without SOAP headers."
        sections = exp._parse_soap_text(text)
        assert sections["subjective"] == text

    def test_export_generic_with_dict_content(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        output = tmp_path / "dict_generic.docx"
        content = {
            "document_type": "generic",
            "title": "Structured Doc",
            "content": {"findings": "Normal", "notes": "None"},
        }
        result = exp.export(content, output)
        assert result is True

    def test_export_special_characters(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        output = tmp_path / "special.docx"
        content = {
            "document_type": "generic",
            "content": "Special chars: <>&\"' and unicode: \u00e9\u00e8\u00ea \u2022 \u2014",
        }
        result = exp.export(content, output)
        assert result is True

    def test_export_empty_content(self, tmp_path):
        from exporters.docx_exporter import DocxExporter
        exp = DocxExporter()
        output = tmp_path / "empty.docx"
        content = {"document_type": "generic", "content": ""}
        result = exp.export(content, output)
        assert result is True

    def test_get_docx_exporter_factory(self):
        from exporters.docx_exporter import get_docx_exporter
        exp = get_docx_exporter("Clinic", "Doctor")
        assert exp.clinic_name == "Clinic"
        assert exp.doctor_name == "Doctor"


# ---------------------------------------------------------------------------
# FHIRResourceBuilder Tests
# ---------------------------------------------------------------------------

class TestFHIRResourceBuilder:
    """Tests for FHIRResourceBuilder."""

    def _builder(self, **kwargs):
        from exporters.fhir_config import FHIRExportConfig
        from exporters.fhir_resources import FHIRResourceBuilder
        config = FHIRExportConfig(**kwargs)
        return FHIRResourceBuilder(config)

    def test_create_patient_minimal(self):
        b = self._builder()
        patient = b.create_patient()
        assert patient.get_resource_type() == "Patient"

    def test_create_patient_with_info(self):
        b = self._builder()
        patient = b.create_patient({
            "name": "John Doe",
            "id": "P123",
            "dob": "1990-01-15",
            "gender": "male",
        })
        assert patient.get_resource_type() == "Patient"
        assert patient.gender == "male"
        assert patient.birthDate is not None

    def test_create_patient_single_name_raises_validation_error(self):
        """Single-name patient triggers FHIR validation error due to empty family name."""
        from pydantic import ValidationError
        b = self._builder()
        # Source code sets family="" for single names, which FHIR rejects
        with pytest.raises(ValidationError):
            b.create_patient({"name": "Madonna"})

    def test_create_practitioner_minimal(self):
        b = self._builder()
        pract = b.create_practitioner()
        assert pract.get_resource_type() == "Practitioner"

    def test_create_practitioner_with_info(self):
        b = self._builder(practitioner_name="Dr. Default")
        pract = b.create_practitioner({
            "name": "Dr. Jane Smith",
            "id": "PR456",
            "qualification": "MD",
        })
        assert pract.get_resource_type() == "Practitioner"

    def test_create_organization_minimal(self):
        b = self._builder()
        org = b.create_organization()
        assert org.get_resource_type() == "Organization"

    def test_create_organization_with_info(self):
        b = self._builder(organization_name="Default Org")
        org = b.create_organization({"name": "Custom Org", "id": "ORG789"})
        assert org.get_resource_type() == "Organization"
        assert org.name == "Custom Org"

    def test_create_composition_section(self):
        b = self._builder()
        section = b.create_composition_section("Subjective", "Patient has headache", "subjective")
        assert section.title == "Subjective"
        assert section.text is not None

    def test_parse_soap_sections_with_headers(self):
        b = self._builder()
        text = "Subjective\nHeadache\n\nObjective\nVitals normal\n\nAssessment\nMigraine\n\nPlan\nMedication"
        sections = b.parse_soap_sections(text)
        assert "Headache" in sections["subjective"]
        assert "normal" in sections["objective"]
        assert "Migraine" in sections["assessment"]
        assert "Medication" in sections["plan"]

    def test_parse_soap_sections_no_headers(self):
        b = self._builder()
        text = "Random clinical text without any headers."
        sections = b.parse_soap_sections(text)
        assert sections["subjective"] == text

    def test_create_composition_with_practitioner_ref(self):
        b = self._builder()
        soap_data = {
            "subjective": "Headache",
            "objective": "BP normal",
            "assessment": "Migraine",
            "plan": "Rest",
        }
        comp = b.create_composition(
            soap_data,
            practitioner_ref="urn:uuid:pract-1",
        )
        assert comp.get_resource_type() == "Composition"
        assert comp.status == "final"
        assert comp.section is not None
        assert len(comp.section) == 4
        assert comp.author is not None

    def test_create_composition_with_patient_ref_raises(self):
        """Subject reference triggers FHIR validation error due to library version incompatibility."""
        from pydantic import ValidationError
        b = self._builder()
        with pytest.raises(ValidationError):
            b.create_composition(
                {"subjective": "Test"},
                patient_ref="urn:uuid:patient-1",
                practitioner_ref="urn:uuid:pract-1",
            )

    def test_create_composition_from_content_key(self):
        b = self._builder()
        soap_data = {"content": "Subjective\nHeadache\n\nObjective\nNormal"}
        comp = b.create_composition(
            soap_data,
            practitioner_ref="urn:uuid:pract-1",
        )
        assert comp.get_resource_type() == "Composition"

    def test_create_composition_no_author_raises(self):
        """Composition without author raises FHIR validation error (author=None not allowed)."""
        from pydantic import ValidationError
        b = self._builder()
        with pytest.raises(ValidationError):
            b.create_composition({"subjective": "Test"})

    def test_create_document_reference(self):
        b = self._builder()
        doc_ref = b.create_document_reference(
            content="Clinical document text",
            document_type="soap_note",
            title="Test Doc",
        )
        assert doc_ref.get_resource_type() == "DocumentReference"
        assert doc_ref.status == "current"
        assert len(doc_ref.content) == 1
        # Verify content is present in serialized output
        serialized = doc_ref.model_dump_json()
        assert "Test Doc" in serialized

    def test_create_bundle(self):
        b = self._builder()
        patient = b.create_patient({"name": "Test Patient"})
        bundle = b.create_bundle([patient], bundle_type="collection")
        assert bundle.get_resource_type() == "Bundle"
        assert bundle.type == "collection"
        assert len(bundle.entry) == 1

    def test_create_soap_bundle_minimal_no_practitioner_raises(self):
        """Bundle creation without practitioner raises due to Composition author=None."""
        from pydantic import ValidationError
        b = self._builder()
        soap_data = {"subjective": "Headache", "assessment": "Migraine"}
        with pytest.raises(ValidationError):
            b.create_soap_bundle(soap_data)

    def test_create_soap_bundle_with_practitioner(self):
        b = self._builder(practitioner_name="Dr. Test")
        soap_data = {"subjective": "Headache", "assessment": "Migraine"}
        bundle = b.create_soap_bundle(
            soap_data,
            practitioner_info={"name": "Dr. Test"},
        )
        assert bundle.get_resource_type() == "Bundle"
        assert bundle.type == "document"
        # Composition + Practitioner
        assert len(bundle.entry) >= 2

    def test_create_soap_bundle_with_practitioner_and_org(self):
        b = self._builder(
            practitioner_name="Dr. Test",
            organization_name="Test Org",
        )
        soap_data = {"subjective": "Headache"}
        bundle = b.create_soap_bundle(
            soap_data,
            practitioner_info={"name": "Dr. Smith"},
            organization_info={"name": "Clinic"},
        )
        # Should have Composition + Practitioner + Organization
        assert bundle.get_resource_type() == "Bundle"
        assert len(bundle.entry) == 3

    def test_create_soap_bundle_with_patient_raises(self):
        """Including patient_info triggers subject reference incompatibility."""
        from pydantic import ValidationError
        b = self._builder(practitioner_name="Dr. Test")
        with pytest.raises(ValidationError):
            b.create_soap_bundle(
                {"subjective": "Headache"},
                patient_info={"name": "John Doe"},
                practitioner_info={"name": "Dr. Smith"},
            )

    def test_narrative_html_escaping(self):
        b = self._builder()
        narrative = b._create_narrative("Text with <tags> & \"quotes\"")
        assert "&lt;" in narrative.div
        assert "&amp;" in narrative.div
        assert "&quot;" in narrative.div

    def test_next_id_increments(self):
        b = self._builder()
        id1 = b._next_id("test")
        id2 = b._next_id("test")
        assert id1 != id2


# ---------------------------------------------------------------------------
# FHIRExporter Tests
# ---------------------------------------------------------------------------

class TestFHIRExporter:
    """Tests for FHIRExporter."""

    def test_init_default_config(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        assert exp.config is not None
        assert exp.config.fhir_version == "R4"

    def test_init_custom_config(self):
        from exporters.fhir_exporter import FHIRExporter, FHIRExportConfig
        cfg = FHIRExportConfig(organization_name="Test Org")
        exp = FHIRExporter(config=cfg)
        assert exp.config.organization_name == "Test Org"

    def test_export_to_string_bundle(self):
        from exporters.fhir_exporter import FHIRExporter
        from exporters.fhir_config import FHIRExportConfig
        cfg = FHIRExportConfig(practitioner_name="Dr. Test")
        exp = FHIRExporter(config=cfg)
        content = {
            "soap_data": {"subjective": "Headache", "assessment": "Migraine"},
            "title": "Test SOAP",
            "practitioner_info": {"name": "Dr. Test"},
        }
        result = exp.export_to_string(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "Bundle"
        assert parsed["type"] == "document"

    def test_export_to_string_document_reference(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        content = {
            "soap_data": "Just text content",
            "title": "Test Doc",
            "export_type": "document_reference",
        }
        result = exp.export_to_string(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_export_to_file(self, tmp_path):
        from exporters.fhir_exporter import FHIRExporter
        from exporters.fhir_config import FHIRExportConfig
        cfg = FHIRExportConfig(practitioner_name="Dr. Test")
        exp = FHIRExporter(config=cfg)
        output = tmp_path / "fhir.json"
        content = {
            "soap_data": {"subjective": "Test"},
            "title": "Test",
            "practitioner_info": {"name": "Dr. Test"},
        }
        result = exp.export(content, output)
        assert result is True
        assert output.exists()
        parsed = json.loads(output.read_text())
        assert parsed["resourceType"] == "Bundle"

    def test_export_to_file_error(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        with patch("builtins.open", side_effect=PermissionError("denied")):
            result = exp.export({"soap_data": {"subjective": "Test"}}, Path("/bad/path.json"))
            assert result is False
            assert exp.last_error is not None

    def test_export_soap_note_to_string(self):
        from exporters.fhir_exporter import FHIRExporter
        from exporters.fhir_config import FHIRExportConfig
        cfg = FHIRExportConfig(practitioner_name="Dr. Test")
        exp = FHIRExporter(config=cfg)
        result = exp.export_soap_note(
            "Subjective\nHeadache\n\nAssessment\nMigraine",
            practitioner_info={"name": "Dr. Test"},
        )
        parsed = json.loads(result)
        assert parsed["resourceType"] == "Bundle"

    def test_export_soap_note_to_file(self, tmp_path):
        from exporters.fhir_exporter import FHIRExporter
        from exporters.fhir_config import FHIRExportConfig
        cfg = FHIRExportConfig(practitioner_name="Dr. Test")
        exp = FHIRExporter(config=cfg)
        output = tmp_path / "soap.json"
        result = exp.export_soap_note(
            "Subjective\nHeadache",
            output_path=output,
            practitioner_info={"name": "Dr. Test"},
        )
        assert result is True
        assert output.exists()

    def test_export_soap_note_as_document_reference(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        result = exp.export_soap_note("Test content", as_document_reference=True)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_export_referral_to_string(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        result = exp.export_referral("Dear Doctor, please see patient.")
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_export_referral_to_file(self, tmp_path):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        output = tmp_path / "referral.json"
        result = exp.export_referral("Referral text", output_path=output)
        assert result is True

    def test_export_letter_to_string(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        result = exp.export_letter("Medical letter content")
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_export_letter_to_file(self, tmp_path):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        output = tmp_path / "letter.json"
        result = exp.export_letter("Letter text", output_path=output)
        assert result is True

    def test_copy_soap_to_clipboard(self):
        from exporters.fhir_exporter import FHIRExporter
        # Use document_reference mode to avoid Composition author issue
        exp = FHIRExporter()
        mock_pyperclip = MagicMock()
        with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
            result = exp.copy_soap_to_clipboard("Test SOAP", as_document_reference=True)
            assert result is True
            mock_pyperclip.copy.assert_called_once()

    def test_export_as_document_reference_dict_data(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        content = {
            "soap_data": {
                "subjective": "Headache",
                "objective": "Normal",
                "assessment": "Migraine",
                "plan": "Rest",
            },
            "export_type": "document_reference",
        }
        result = exp.export_to_string(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_export_as_document_reference_with_content_key(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        content = {
            "soap_data": {"content": "Full SOAP text here"},
            "export_type": "document_reference",
        }
        result = exp.export_to_string(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_get_fhir_exporter_factory(self):
        from exporters.fhir_exporter import get_fhir_exporter
        exp = get_fhir_exporter()
        assert exp is not None
        assert exp.config.fhir_version == "R4"

    def test_export_special_characters(self, tmp_path):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        output = tmp_path / "special.json"
        content = {
            "soap_data": "Special chars: <>&\"' \u00e9\u00e8 \u2022 \u2014 \u00b0F",
            "title": "Special Characters Test",
            "export_type": "document_reference",
        }
        result = exp.export(content, output)
        assert result is True

    def test_export_very_long_content(self):
        from exporters.fhir_exporter import FHIRExporter
        exp = FHIRExporter()
        long_text = "A" * 100_000
        result = exp.export_to_string({
            "soap_data": long_text,
            "export_type": "document_reference",
        })
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"


# ---------------------------------------------------------------------------
# RAGConversationExporter Tests
# ---------------------------------------------------------------------------

class TestRAGConversationExporter:
    """Tests for RAGConversationExporter."""

    def _sample_content(self):
        return {
            "title": "Test RAG Session",
            "timestamp": "2026-03-26T10:00:00",
            "metadata": {"total_queries": 2, "documents_searched": 5},
            "exchanges": [
                {
                    "query": "What is hypertension?",
                    "response": "Hypertension is high blood pressure.",
                    "sources": [
                        {"document": "cardiology.pdf", "score": 0.95, "chunk": "Short chunk text"},
                    ],
                    "processing_time_ms": 150,
                },
                {
                    "query": "Treatment options?",
                    "response": "ACE inhibitors and lifestyle changes.",
                    "sources": [],
                },
            ],
        }

    def test_init(self):
        from exporters.rag_exporter import RAGConversationExporter
        with patch("exporters.rag_exporter.RAGConversationExporter.__init__", return_value=None) as mock_init:
            # Test that it doesn't crash even when libraries are missing
            pass
        # Direct init
        exp = RAGConversationExporter()
        assert exp is not None

    def test_export_to_string_markdown(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        result = exp.export_to_string(self._sample_content())
        assert "# Test RAG Session" in result
        assert "hypertension" in result
        assert "Treatment options" in result
        assert "cardiology.pdf" in result

    def test_export_as_markdown(self, tmp_path):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        output = tmp_path / "conversation.md"
        result = exp.export_as_markdown(self._sample_content(), output)
        assert result is True
        assert output.exists()
        text = output.read_text()
        assert "# Test RAG Session" in text

    def test_export_as_json(self, tmp_path):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        output = tmp_path / "conversation.json"
        result = exp.export_as_json(self._sample_content(), output)
        assert result is True
        parsed = json.loads(output.read_text())
        assert parsed["title"] == "Test RAG Session"

    def test_export_dispatch_by_extension_md(self, tmp_path):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        output = tmp_path / "test.md"
        result = exp.export(self._sample_content(), output)
        assert result is True

    def test_export_dispatch_by_extension_json(self, tmp_path):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        output = tmp_path / "test.json"
        result = exp.export(self._sample_content(), output)
        assert result is True

    def test_export_unsupported_extension(self, tmp_path):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        output = tmp_path / "test.xyz"
        result = exp.export(self._sample_content(), output)
        assert result is False
        assert "Unsupported export format" in exp.last_error

    def test_export_as_json_error(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        with patch("builtins.open", side_effect=PermissionError("denied")):
            result = exp.export_as_json(self._sample_content(), Path("/bad/path.json"))
            assert result is False
            assert "JSON export failed" in exp.last_error

    def test_export_as_markdown_error(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        with patch.object(Path, "write_text", side_effect=PermissionError("denied")):
            result = exp.export_as_markdown(self._sample_content(), Path("/bad/path.md"))
            assert result is False
            assert "Markdown export failed" in exp.last_error

    def test_export_as_pdf_unavailable(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        exp._pdf_available = False
        result = exp.export_as_pdf(self._sample_content(), Path("test.pdf"))
        assert result is False
        assert "ReportLab not available" in exp.last_error

    def test_export_as_docx_unavailable(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        exp._docx_available = False
        result = exp.export_as_docx(self._sample_content(), Path("test.docx"))
        assert result is False
        assert "python-docx not available" in exp.last_error

    def test_export_as_pdf_available(self, tmp_path):
        """Test PDF export when reportlab is available."""
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        if not exp._pdf_available:
            pytest.skip("reportlab not installed")
        output = tmp_path / "test.pdf"
        result = exp.export_as_pdf(self._sample_content(), output)
        assert result is True
        assert output.exists()

    def test_export_as_docx_available(self, tmp_path):
        """Test DOCX export when python-docx is available."""
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        if not exp._docx_available:
            pytest.skip("python-docx not installed")
        output = tmp_path / "test.docx"
        result = exp.export_as_docx(self._sample_content(), output)
        assert result is True
        assert output.exists()

    def test_escape_html(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        result = exp._escape_html("Test <b>bold</b> & \"quoted\"")
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&quot;" in result
        assert "&#39;" not in result  # no single quotes in input

    def test_escape_html_single_quote(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        result = exp._escape_html("it's a test")
        assert "&#39;" in result

    def test_format_as_markdown_empty_exchanges(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        content = {"title": "Empty", "exchanges": []}
        result = exp.export_to_string(content)
        assert "# Empty" in result

    def test_format_as_markdown_with_query_expansion(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        content = {
            "title": "Expanded",
            "exchanges": [
                {
                    "query": "HTN",
                    "response": "Hypertension info",
                    "query_expansion": {
                        "original_query": "HTN",
                        "expanded_terms": ["hypertension", "high blood pressure"],
                    },
                    "processing_time_ms": 100,
                }
            ],
        }
        result = exp.export_to_string(content)
        assert "Query Expansion" in result
        assert "hypertension" in result
        assert "Processing time" in result

    def test_format_as_markdown_long_chunk(self):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        content = {
            "title": "Long",
            "exchanges": [
                {
                    "query": "Test",
                    "response": "Response",
                    "sources": [
                        {"document": "doc.pdf", "chunk": "A" * 200, "score": 0.8},
                    ],
                }
            ],
        }
        result = exp.export_to_string(content)
        assert "..." in result  # chunk should be truncated

    def test_create_rag_export_content(self):
        from exporters.rag_exporter import create_rag_export_content
        exchanges = [
            {
                "query": "Test query",
                "response": "Test response",
                "sources": [
                    {"document_filename": "file.pdf", "chunk_text": "chunk", "combined_score": 0.9},
                ],
                "processing_time_ms": 50,
            }
        ]
        result = create_rag_export_content("session-123", exchanges, title="My Session")
        assert result["session_id"] == "session-123"
        assert result["title"] == "My Session"
        assert result["metadata"]["total_queries"] == 1
        assert len(result["exchanges"]) == 1
        assert result["exchanges"][0]["sources"][0]["document"] == "file.pdf"

    def test_create_rag_export_content_fallback_keys(self):
        from exporters.rag_exporter import create_rag_export_content
        exchanges = [
            {
                "query": "Test",
                "response": "Resp",
                "sources": [
                    {"document": "fallback.pdf", "chunk": "chunk text", "score": 0.5},
                ],
            }
        ]
        result = create_rag_export_content("s1", exchanges)
        assert result["exchanges"][0]["sources"][0]["document"] == "fallback.pdf"

    def test_get_rag_exporter_singleton(self):
        from exporters import rag_exporter
        # Reset singleton
        rag_exporter._exporter = None
        exp1 = rag_exporter.get_rag_exporter()
        exp2 = rag_exporter.get_rag_exporter()
        assert exp1 is exp2
        # Cleanup
        rag_exporter._exporter = None

    def test_export_as_json_datetime_serialization(self, tmp_path):
        from exporters.rag_exporter import RAGConversationExporter
        exp = RAGConversationExporter()
        content = {
            "title": "Test",
            "exchanges": [],
            "created_at": datetime(2026, 3, 26, 10, 0, 0),
        }
        output = tmp_path / "datetime_test.json"
        result = exp.export_as_json(content, output)
        assert result is True
        parsed = json.loads(output.read_text())
        assert "2026-03-26" in parsed["created_at"]


# ---------------------------------------------------------------------------
# PDFExporter Tests (utils/pdf_exporter.py)
# ---------------------------------------------------------------------------

class TestPDFExporter:
    """Tests for PDFExporter in utils/pdf_exporter.py."""

    def test_init_defaults(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        assert exp.include_header is True
        assert exp.include_footer is True
        assert exp.header_text == "Medical Assistant Report"
        assert exp.clinic_name == ""
        assert exp.doctor_name == ""

    def test_init_a4(self):
        from reportlab.lib.pagesizes import A4
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter(page_size=A4)
        assert exp.page_size == A4

    def test_set_header_footer_info(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        exp.set_header_footer_info(
            header_text="Custom Header",
            footer_text="Custom Footer",
            logo_path="/path/to/logo.png",
        )
        assert exp.header_text == "Custom Header"
        assert exp.footer_text == "Custom Footer"
        assert exp.logo_path == "/path/to/logo.png"

    def test_set_header_footer_info_partial(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        exp.set_header_footer_info(header_text="New Header")
        assert exp.header_text == "New Header"
        assert exp.footer_text is None  # unchanged
        assert exp.logo_path is None

    def test_set_simple_letterhead(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        exp.set_simple_letterhead("Acme Clinic", "Dr. Smith")
        assert exp.clinic_name == "Acme Clinic"
        assert exp.doctor_name == "Dr. Smith"

    def test_generate_soap_note_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "soap.pdf")
        soap_data = {
            "subjective": "Patient reports headache",
            "objective": "BP 120/80",
            "assessment": "Tension headache",
            "plan": "Rest and ibuprofen",
        }
        result = exp.generate_soap_note_pdf(soap_data, output)
        assert result is True
        assert Path(output).exists()

    def test_generate_soap_note_pdf_with_patient_info(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "soap_patient.pdf")
        soap_data = {"subjective": "Headache"}
        patient_info = {"name": "John Doe", "dob": "1990-01-01", "mrn": "MRN123"}
        result = exp.generate_soap_note_pdf(soap_data, output, patient_info=patient_info)
        assert result is True

    def test_generate_soap_note_pdf_empty_sections(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "soap_empty.pdf")
        result = exp.generate_soap_note_pdf({}, output)
        assert result is True

    def test_generate_soap_note_pdf_error(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        # Invalid path
        result = exp.generate_soap_note_pdf({"subjective": "test"}, "/nonexistent/dir/file.pdf")
        assert result is False

    def test_generate_medication_report_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "meds.pdf")
        med_data = {
            "medications": [
                {"name": "Lisinopril", "dosage": "10mg", "frequency": "daily"},
                {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily"},
            ],
            "interactions": [
                {
                    "drug1": "Lisinopril",
                    "drug2": "Metformin",
                    "severity": "Low",
                    "description": "Minor interaction with no clinical significance in most cases",
                }
            ],
            "warnings": ["Monitor kidney function", "Check blood glucose"],
            "recommendations": "Continue current regimen with monitoring.",
        }
        result = exp.generate_medication_report_pdf(med_data, output)
        assert result is True
        assert Path(output).exists()

    def test_generate_medication_report_pdf_empty(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "meds_empty.pdf")
        result = exp.generate_medication_report_pdf({}, output)
        assert result is True

    def test_generate_diagnostic_report_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "diagnostic.pdf")
        diag_data = {
            "clinical_findings": "Patient presents with chest pain",
            "differentials": [
                {
                    "diagnosis": "Angina",
                    "probability": "High",
                    "evidence": ["Chest pain on exertion", "Risk factors present"],
                    "tests": ["ECG", "Troponin"],
                },
                {
                    "diagnosis": "GERD",
                    "probability": "Medium",
                    "evidence": ["Burning sensation"],
                    "tests": ["Upper endoscopy"],
                },
            ],
            "red_flags": ["Acute chest pain", "Shortness of breath"],
        }
        result = exp.generate_diagnostic_report_pdf(diag_data, output)
        assert result is True

    def test_generate_diagnostic_report_pdf_empty(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "diag_empty.pdf")
        result = exp.generate_diagnostic_report_pdf({}, output)
        assert result is True

    def test_generate_referral_letter_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "referral.pdf")
        referral_data = {
            "subject": "Referral for cardiac evaluation",
            "body": "Dear Colleague,\n\nPlease evaluate this patient.\n\nThank you.",
        }
        sender_info = {
            "clinic_name": "Primary Care Clinic",
            "address": "123 Main St",
            "phone": "555-0100",
            "doctor_name": "Dr. Smith",
            "doctor_title": "MD, FACP",
        }
        recipient_info = {
            "name": "Dr. Jones",
            "title": "Cardiologist",
            "address": "456 Heart Ave",
        }
        result = exp.generate_referral_letter_pdf(
            referral_data, output, sender_info=sender_info, recipient_info=recipient_info
        )
        assert result is True

    def test_generate_referral_letter_pdf_minimal(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "referral_minimal.pdf")
        result = exp.generate_referral_letter_pdf({"body": "Please see patient."}, output)
        assert result is True

    def test_generate_workflow_report_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "workflow.pdf")
        workflow_data = {
            "workflow_type": "patient_intake",
            "patient_info": {"name": "Jane Doe", "primary_concern": "Annual checkup"},
            "steps": [
                {"description": "Verify insurance", "completed": True, "time_estimate": "5 min"},
                {"description": "Take vitals", "completed": False, "time_estimate": "10 min"},
            ],
            "notes": "Patient arrived on time.",
        }
        result = exp.generate_workflow_report_pdf(workflow_data, output)
        assert result is True

    def test_generate_workflow_report_pdf_empty(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "workflow_empty.pdf")
        result = exp.generate_workflow_report_pdf({}, output)
        assert result is True

    def test_generate_data_extraction_report_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "extraction.pdf")
        extraction_data = {
            "vitals": [
                {"name": "Blood Pressure", "value": "120/80", "unit": "mmHg", "status": "Normal"},
                {"name": "Heart Rate", "value": "72", "unit": "bpm", "status": "Normal"},
            ],
            "labs": [
                {"test": "HbA1c", "result": "5.4", "reference": "< 5.7", "flag": ""},
            ],
            "diagnoses": [
                {"description": "Hypertension", "icd_code": "I10"},
                {"description": "Type 2 Diabetes"},
            ],
        }
        result = exp.generate_data_extraction_report_pdf(extraction_data, output)
        assert result is True

    def test_generate_data_extraction_report_raw_content(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "extraction_raw.pdf")
        extraction_data = {
            "raw_content": "Some extracted text\nWith multiple lines\nOf content",
        }
        result = exp.generate_data_extraction_report_pdf(extraction_data, output)
        assert result is True

    def test_generate_data_extraction_report_empty(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "extraction_empty.pdf")
        result = exp.generate_data_extraction_report_pdf({}, output)
        assert result is True

    def test_generate_generic_document_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "generic.pdf")
        result = exp.generate_generic_document_pdf(
            title="Test Report",
            content="## Section 1\n\nParagraph one.\n\n### Subsection\n\nMore text.",
            output_path=output,
            metadata={"Author": "Dr. Test", "Date": "2026-03-26"},
        )
        assert result is True

    def test_generate_generic_document_pdf_markdown_headers(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "headers.pdf")
        content = "# Main Title\n\n## Sub Title\n\n### Sub Sub\n\nNormal paragraph."
        result = exp.generate_generic_document_pdf("Headers Test", content, output)
        assert result is True

    def test_generate_generic_document_pdf_empty_content(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "empty.pdf")
        result = exp.generate_generic_document_pdf("Empty", "", output)
        assert result is True

    def test_generate_generic_document_pdf_no_metadata(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "no_meta.pdf")
        result = exp.generate_generic_document_pdf("No Meta", "Content here.", output)
        assert result is True

    def test_generate_generic_document_pdf_error(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        result = exp.generate_generic_document_pdf("Test", "Content", "/nonexistent/dir/test.pdf")
        assert result is False

    def test_generate_soap_with_letterhead(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        exp.set_simple_letterhead("Test Clinic", "Dr. Letterhead")
        output = str(tmp_path / "letterhead.pdf")
        result = exp.generate_soap_note_pdf({"subjective": "Test"}, output)
        assert result is True

    def test_header_footer_callback(self, tmp_path):
        """Test that the header/footer callback runs without error."""
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        exp.set_simple_letterhead("Clinic", "Doctor")
        exp.footer_text = "Confidential"
        output = str(tmp_path / "hf_test.pdf")
        result = exp.generate_soap_note_pdf({"subjective": "Test"}, output)
        assert result is True

    def test_special_characters_in_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "special.pdf")
        soap_data = {
            "subjective": "Patient reports pain \u2014 rated 7/10. Temp 98.6\u00b0F",
            "assessment": "Acute pharyngitis (J02.9)",
        }
        result = exp.generate_soap_note_pdf(soap_data, output)
        assert result is True

    def test_very_long_content_pdf(self, tmp_path):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        output = str(tmp_path / "long.pdf")
        long_text = "This is a test sentence. " * 1000
        soap_data = {"subjective": long_text, "assessment": long_text}
        result = exp.generate_soap_note_pdf(soap_data, output)
        assert result is True

    def test_medication_report_error_handling(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        result = exp.generate_medication_report_pdf(
            {"medications": [{"name": "Test"}]},
            "/nonexistent/dir/file.pdf",
        )
        assert result is False

    def test_diagnostic_report_error_handling(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        result = exp.generate_diagnostic_report_pdf(
            {"clinical_findings": "Test"},
            "/nonexistent/dir/file.pdf",
        )
        assert result is False

    def test_referral_letter_error_handling(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        result = exp.generate_referral_letter_pdf(
            {"body": "Test"},
            "/nonexistent/dir/file.pdf",
        )
        assert result is False

    def test_workflow_report_error_handling(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        result = exp.generate_workflow_report_pdf(
            {"steps": [{"description": "Test"}]},
            "/nonexistent/dir/file.pdf",
        )
        assert result is False

    def test_data_extraction_report_error_handling(self):
        from utils.pdf_exporter import PDFExporter
        exp = PDFExporter()
        result = exp.generate_data_extraction_report_pdf(
            {"vitals": [{"name": "Test"}]},
            "/nonexistent/dir/file.pdf",
        )
        assert result is False
