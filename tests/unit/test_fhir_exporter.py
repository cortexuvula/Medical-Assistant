"""
Tests for src/exporters/fhir_exporter.py
No network, no Tkinter.
"""
import sys
import json
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from exporters.fhir_exporter import FHIRExporter, get_fhir_exporter
from exporters.fhir_config import FHIRExportConfig
from exporters.base_exporter import BaseExporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bundle_content(**kwargs):
    """Minimal content dict that produces a valid FHIR Bundle (has practitioner)."""
    base = {
        "soap_data": {"subjective": "Test complaint"},
        "practitioner_info": {"name": "Dr. Test"},
    }
    base.update(kwargs)
    return base


def _docref_content(**kwargs):
    """Minimal content dict for DocumentReference export."""
    base = {
        "soap_data": "Simple clinical text.",
        "export_type": "document_reference",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# TestFHIRExporterInit
# ---------------------------------------------------------------------------

class TestFHIRExporterInit:
    """FHIRExporter construction tests."""

    def test_creates_with_no_args(self):
        exp = FHIRExporter()
        assert exp is not None

    def test_default_config_created_when_none_passed(self):
        exp = FHIRExporter()
        assert exp.config is not None

    def test_default_config_is_fhir_export_config(self):
        exp = FHIRExporter()
        assert isinstance(exp.config, FHIRExportConfig)

    def test_default_config_fhir_version_is_r4(self):
        exp = FHIRExporter()
        assert exp.config.fhir_version == "R4"

    def test_custom_config_stored(self):
        cfg = FHIRExportConfig(organization_name="TestOrg")
        exp = FHIRExporter(config=cfg)
        assert exp.config is cfg

    def test_custom_config_values_accessible(self):
        cfg = FHIRExportConfig(organization_name="Acme", practitioner_name="Dr. Acme")
        exp = FHIRExporter(config=cfg)
        assert exp.config.organization_name == "Acme"
        assert exp.config.practitioner_name == "Dr. Acme"

    def test_has_resource_builder_attribute(self):
        exp = FHIRExporter()
        assert hasattr(exp, "resource_builder")

    def test_resource_builder_is_not_none(self):
        exp = FHIRExporter()
        assert exp.resource_builder is not None

    def test_last_error_is_none_on_init(self):
        exp = FHIRExporter()
        assert exp.last_error is None

    def test_is_base_exporter_subclass(self):
        exp = FHIRExporter()
        assert isinstance(exp, BaseExporter)

    def test_two_instances_have_independent_configs(self):
        exp1 = FHIRExporter(config=FHIRExportConfig(organization_name="Org1"))
        exp2 = FHIRExporter(config=FHIRExportConfig(organization_name="Org2"))
        assert exp1.config.organization_name != exp2.config.organization_name


# ---------------------------------------------------------------------------
# TestExportToString
# ---------------------------------------------------------------------------

class TestExportToString:
    """FHIRExporter.export_to_string tests."""

    def test_returns_string(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_docref_content())
        assert isinstance(result, str)

    def test_result_is_valid_json(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_docref_content())
        # Should not raise
        parsed = json.loads(result)
        assert parsed is not None

    def test_default_export_type_is_bundle(self):
        exp = FHIRExporter()
        content = _bundle_content()
        result = exp.export_to_string(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "Bundle"

    def test_bundle_has_resource_type_key(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_bundle_content())
        parsed = json.loads(result)
        assert "resourceType" in parsed

    def test_bundle_contains_bundle_string(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_bundle_content())
        assert "Bundle" in result

    def test_export_type_document_reference_routes_correctly(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_docref_content())
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_with_practitioner_info_produces_bundle(self):
        exp = FHIRExporter()
        content = {
            "soap_data": {"subjective": "Test"},
            "practitioner_info": {"name": "Dr. Test"},
        }
        result = exp.export_to_string(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "Bundle"

    def test_bundle_type_is_document(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_bundle_content())
        parsed = json.loads(result)
        assert parsed["type"] == "document"

    def test_non_empty_result(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_docref_content())
        assert len(result) > 0

    def test_bundle_has_entry_array(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_bundle_content())
        parsed = json.loads(result)
        assert "entry" in parsed
        assert isinstance(parsed["entry"], list)

    def test_bundle_entry_not_empty(self):
        exp = FHIRExporter()
        result = exp.export_to_string(_bundle_content())
        parsed = json.loads(result)
        assert len(parsed["entry"]) >= 1


# ---------------------------------------------------------------------------
# TestExportAsBundle
# ---------------------------------------------------------------------------

class TestExportAsBundle:
    """FHIRExporter._export_as_bundle tests."""

    def test_returns_json_string(self):
        exp = FHIRExporter()
        result = exp._export_as_bundle(_bundle_content())
        assert isinstance(result, str)

    def test_parseable_as_json(self):
        exp = FHIRExporter()
        result = exp._export_as_bundle(_bundle_content())
        parsed = json.loads(result)
        assert parsed is not None

    def test_has_resource_type_bundle(self):
        exp = FHIRExporter()
        result = exp._export_as_bundle(_bundle_content())
        parsed = json.loads(result)
        assert parsed["resourceType"] == "Bundle"

    def test_soap_data_as_dict(self):
        exp = FHIRExporter()
        content = {
            "soap_data": {"subjective": "Dict data", "assessment": "Migraine"},
            "practitioner_info": {"name": "Dr. X"},
        }
        result = exp._export_as_bundle(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "Bundle"

    def test_soap_data_as_string_converted(self):
        exp = FHIRExporter()
        content = {
            "soap_data": "Full SOAP text as string.",
            "practitioner_info": {"name": "Dr. X"},
        }
        result = exp._export_as_bundle(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "Bundle"

    def test_custom_title_accepted(self):
        exp = FHIRExporter()
        content = _bundle_content(title="Custom SOAP Note")
        result = exp._export_as_bundle(content)
        # Title is present somewhere in JSON
        assert "Custom SOAP Note" in result

    def test_bundle_id_present(self):
        exp = FHIRExporter()
        result = exp._export_as_bundle(_bundle_content())
        parsed = json.loads(result)
        assert "id" in parsed

    def test_bundle_has_timestamp(self):
        exp = FHIRExporter()
        result = exp._export_as_bundle(_bundle_content())
        parsed = json.loads(result)
        assert "timestamp" in parsed

    def test_missing_soap_data_uses_empty_dict(self):
        exp = FHIRExporter()
        # No "soap_data" key — falls back to empty dict
        content = {"practitioner_info": {"name": "Dr. X"}}
        result = exp._export_as_bundle(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "Bundle"


# ---------------------------------------------------------------------------
# TestExportAsDocumentReference
# ---------------------------------------------------------------------------

class TestExportAsDocumentReference:
    """FHIRExporter._export_as_document_reference tests."""

    def test_returns_json_string(self):
        exp = FHIRExporter()
        result = exp._export_as_document_reference(_docref_content())
        assert isinstance(result, str)

    def test_parseable_as_json(self):
        exp = FHIRExporter()
        result = exp._export_as_document_reference(_docref_content())
        parsed = json.loads(result)
        assert parsed is not None

    def test_has_resource_type_document_reference(self):
        exp = FHIRExporter()
        result = exp._export_as_document_reference(_docref_content())
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_plain_text_soap_data_accepted(self):
        exp = FHIRExporter()
        content = {"soap_data": "Plain clinical text here."}
        result = exp._export_as_document_reference(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_with_content_key_in_soap_data(self):
        exp = FHIRExporter()
        content = {"soap_data": {"content": "Full SOAP note content."}}
        result = exp._export_as_document_reference(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_with_sections_dict_in_soap_data(self):
        exp = FHIRExporter()
        content = {
            "soap_data": {
                "subjective": "Chest pain.",
                "objective": "HR 90.",
                "assessment": "ACS rule out.",
                "plan": "ECG ordered.",
            }
        }
        result = exp._export_as_document_reference(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"

    def test_status_is_current(self):
        exp = FHIRExporter()
        result = exp._export_as_document_reference(_docref_content())
        parsed = json.loads(result)
        assert parsed["status"] == "current"

    def test_has_content_array(self):
        exp = FHIRExporter()
        result = exp._export_as_document_reference(_docref_content())
        parsed = json.loads(result)
        assert "content" in parsed
        assert isinstance(parsed["content"], list)
        assert len(parsed["content"]) >= 1

    def test_custom_title_stored_in_output(self):
        exp = FHIRExporter()
        content = {
            "soap_data": "Text.",
            "title": "My Custom Title",
        }
        result = exp._export_as_document_reference(content)
        assert "My Custom Title" in result

    def test_empty_soap_data_dict_produces_valid_output(self):
        exp = FHIRExporter()
        content = {"soap_data": {}}
        result = exp._export_as_document_reference(content)
        parsed = json.loads(result)
        assert parsed["resourceType"] == "DocumentReference"


# ---------------------------------------------------------------------------
# TestGetFhirExporter
# ---------------------------------------------------------------------------

class TestGetFhirExporter:
    """get_fhir_exporter factory function tests."""

    def test_returns_fhir_exporter_instance(self):
        result = get_fhir_exporter()
        assert isinstance(result, FHIRExporter)

    def test_default_config_created(self):
        result = get_fhir_exporter()
        assert result.config is not None

    def test_default_config_fhir_version_r4(self):
        result = get_fhir_exporter()
        assert result.config.fhir_version == "R4"

    def test_custom_config_passed_through(self):
        cfg = FHIRExportConfig(organization_name="Factory Org")
        result = get_fhir_exporter(config=cfg)
        assert result.config.organization_name == "Factory Org"

    def test_custom_config_is_same_object(self):
        cfg = FHIRExportConfig(practitioner_name="Dr. Factory")
        result = get_fhir_exporter(config=cfg)
        assert result.config is cfg

    def test_returns_new_instance_each_call(self):
        a = get_fhir_exporter()
        b = get_fhir_exporter()
        assert a is not b

    def test_is_base_exporter_subclass(self):
        result = get_fhir_exporter()
        assert isinstance(result, BaseExporter)

    def test_last_error_none_on_new_instance(self):
        result = get_fhir_exporter()
        assert result.last_error is None

    def test_none_config_uses_defaults(self):
        result = get_fhir_exporter(config=None)
        assert result.config.fhir_version == "R4"
        assert result.config.organization_name == ""
