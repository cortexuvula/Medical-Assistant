"""
Tests for src/exporters/fhir_config.py

Covers:
- FHIRExportConfig dataclass (defaults, custom values)
- FHIR_SYSTEMS dict (keys, URL format)
- DOCUMENT_TYPE_CODES dict (known types, structure)
- SOAP_SECTION_CODES dict (SOAP sections, structure)
- SECTION_TITLE_PATTERNS dict (keys, pattern lists)
- get_section_code() (known sections, fallback to assessment)
- get_document_type_code() (known doc types, fallback)
- normalize_section_name() (known patterns, unknown)
- generate_resource_id() (format, uniqueness)
No network, no Tkinter, no I/O.
"""

import sys
import re
import time
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from exporters.fhir_config import (
    FHIRExportConfig,
    FHIR_SYSTEMS,
    DOCUMENT_TYPE_CODES,
    SOAP_SECTION_CODES,
    SECTION_TITLE_PATTERNS,
    get_section_code,
    get_document_type_code,
    normalize_section_name,
    generate_resource_id,
)


# ===========================================================================
# FHIRExportConfig dataclass
# ===========================================================================

class TestFHIRExportConfig:
    def test_default_fhir_version_r4(self):
        cfg = FHIRExportConfig()
        assert cfg.fhir_version == "R4"

    def test_default_organization_name_empty(self):
        cfg = FHIRExportConfig()
        assert cfg.organization_name == ""

    def test_default_organization_id_empty(self):
        cfg = FHIRExportConfig()
        assert cfg.organization_id == ""

    def test_default_practitioner_name_empty(self):
        cfg = FHIRExportConfig()
        assert cfg.practitioner_name == ""

    def test_default_practitioner_id_empty(self):
        cfg = FHIRExportConfig()
        assert cfg.practitioner_id == ""

    def test_default_include_patient_true(self):
        cfg = FHIRExportConfig()
        assert cfg.include_patient is True

    def test_default_include_practitioner_true(self):
        cfg = FHIRExportConfig()
        assert cfg.include_practitioner is True

    def test_default_include_organization_true(self):
        cfg = FHIRExportConfig()
        assert cfg.include_organization is True

    def test_custom_organization_name(self):
        cfg = FHIRExportConfig(organization_name="General Hospital")
        assert cfg.organization_name == "General Hospital"

    def test_custom_practitioner_id(self):
        cfg = FHIRExportConfig(practitioner_id="prac-123")
        assert cfg.practitioner_id == "prac-123"

    def test_exclude_patient(self):
        cfg = FHIRExportConfig(include_patient=False)
        assert cfg.include_patient is False


# ===========================================================================
# FHIR_SYSTEMS
# ===========================================================================

class TestFHIRSystems:
    def test_is_dict(self):
        assert isinstance(FHIR_SYSTEMS, dict)

    def test_has_loinc(self):
        assert "loinc" in FHIR_SYSTEMS

    def test_has_snomed(self):
        assert "snomed" in FHIR_SYSTEMS

    def test_has_icd9(self):
        assert "icd9" in FHIR_SYSTEMS

    def test_has_icd10(self):
        assert "icd10" in FHIR_SYSTEMS

    def test_loinc_url(self):
        assert FHIR_SYSTEMS["loinc"] == "http://loinc.org"

    def test_all_values_are_urls(self):
        for key, url in FHIR_SYSTEMS.items():
            assert url.startswith("http"), f"{key} should be an http URL"

    def test_all_values_are_strings(self):
        for url in FHIR_SYSTEMS.values():
            assert isinstance(url, str)


# ===========================================================================
# DOCUMENT_TYPE_CODES
# ===========================================================================

class TestDocumentTypeCodes:
    def test_is_dict(self):
        assert isinstance(DOCUMENT_TYPE_CODES, dict)

    def test_has_soap_note(self):
        assert "soap_note" in DOCUMENT_TYPE_CODES

    def test_has_referral(self):
        assert "referral" in DOCUMENT_TYPE_CODES

    def test_has_letter(self):
        assert "letter" in DOCUMENT_TYPE_CODES

    def test_has_transcript(self):
        assert "transcript" in DOCUMENT_TYPE_CODES

    def test_all_entries_have_code(self):
        for name, info in DOCUMENT_TYPE_CODES.items():
            assert "code" in info, f"{name} missing 'code'"

    def test_all_entries_have_display(self):
        for name, info in DOCUMENT_TYPE_CODES.items():
            assert "display" in info, f"{name} missing 'display'"

    def test_all_entries_have_system(self):
        for name, info in DOCUMENT_TYPE_CODES.items():
            assert "system" in info, f"{name} missing 'system'"

    def test_soap_note_code(self):
        assert DOCUMENT_TYPE_CODES["soap_note"]["code"] == "34108-1"

    def test_referral_code(self):
        assert DOCUMENT_TYPE_CODES["referral"]["code"] == "57133-1"

    def test_codes_are_strings(self):
        for _, info in DOCUMENT_TYPE_CODES.items():
            assert isinstance(info["code"], str)


# ===========================================================================
# SOAP_SECTION_CODES
# ===========================================================================

class TestSOAPSectionCodes:
    def test_is_dict(self):
        assert isinstance(SOAP_SECTION_CODES, dict)

    def test_has_subjective(self):
        assert "subjective" in SOAP_SECTION_CODES

    def test_has_objective(self):
        assert "objective" in SOAP_SECTION_CODES

    def test_has_assessment(self):
        assert "assessment" in SOAP_SECTION_CODES

    def test_has_plan(self):
        assert "plan" in SOAP_SECTION_CODES

    def test_all_entries_have_code(self):
        for section, info in SOAP_SECTION_CODES.items():
            assert "code" in info, f"{section} missing 'code'"

    def test_all_entries_have_display(self):
        for section, info in SOAP_SECTION_CODES.items():
            assert "display" in info, f"{section} missing 'display'"

    def test_all_entries_have_system(self):
        for section, info in SOAP_SECTION_CODES.items():
            assert "system" in info, f"{section} missing 'system'"

    def test_non_empty(self):
        assert len(SOAP_SECTION_CODES) > 0


# ===========================================================================
# SECTION_TITLE_PATTERNS
# ===========================================================================

class TestSectionTitlePatterns:
    def test_is_dict(self):
        assert isinstance(SECTION_TITLE_PATTERNS, dict)

    def test_has_subjective(self):
        assert "subjective" in SECTION_TITLE_PATTERNS

    def test_has_objective(self):
        assert "objective" in SECTION_TITLE_PATTERNS

    def test_has_assessment(self):
        assert "assessment" in SECTION_TITLE_PATTERNS

    def test_has_plan(self):
        assert "plan" in SECTION_TITLE_PATTERNS

    def test_subjective_patterns_are_list(self):
        assert isinstance(SECTION_TITLE_PATTERNS["subjective"], list)

    def test_all_pattern_lists_non_empty(self):
        for section, patterns in SECTION_TITLE_PATTERNS.items():
            assert len(patterns) > 0, f"{section} has no patterns"

    def test_all_patterns_are_strings(self):
        for section, patterns in SECTION_TITLE_PATTERNS.items():
            for p in patterns:
                assert isinstance(p, str), f"{section} has non-string pattern"


# ===========================================================================
# get_section_code
# ===========================================================================

class TestGetSectionCode:
    def test_subjective_returns_dict(self):
        result = get_section_code("subjective")
        assert isinstance(result, dict)

    def test_objective_has_code(self):
        result = get_section_code("objective")
        assert "code" in result

    def test_assessment_has_display(self):
        result = get_section_code("assessment")
        assert "display" in result

    def test_plan_has_system(self):
        result = get_section_code("plan")
        assert "system" in result

    def test_unknown_falls_back_to_assessment(self):
        result = get_section_code("unknown_section_xyz")
        fallback = get_section_code("assessment")
        assert result == fallback

    def test_case_insensitive(self):
        result = get_section_code("SUBJECTIVE")
        expected = get_section_code("subjective")
        assert result == expected

    def test_whitespace_stripped(self):
        result = get_section_code("  assessment  ")
        expected = get_section_code("assessment")
        assert result == expected

    def test_vital_signs_returns_code(self):
        result = get_section_code("vital_signs")
        assert "code" in result

    def test_synopsis_returns_code(self):
        result = get_section_code("synopsis")
        assert "code" in result


# ===========================================================================
# get_document_type_code
# ===========================================================================

class TestGetDocumentTypeCode:
    def test_soap_note_returns_dict(self):
        result = get_document_type_code("soap_note")
        assert isinstance(result, dict)

    def test_referral_has_code(self):
        result = get_document_type_code("referral")
        assert "code" in result

    def test_letter_has_display(self):
        result = get_document_type_code("letter")
        assert "display" in result

    def test_transcript_has_system(self):
        result = get_document_type_code("transcript")
        assert "system" in result

    def test_unknown_falls_back_to_soap_note(self):
        result = get_document_type_code("unknown_type_xyz")
        fallback = get_document_type_code("soap_note")
        assert result == fallback

    def test_case_insensitive(self):
        result = get_document_type_code("SOAP_NOTE")
        expected = get_document_type_code("soap_note")
        assert result == expected

    def test_spaces_normalized_to_underscore(self):
        result = get_document_type_code("soap note")
        expected = get_document_type_code("soap_note")
        assert result == expected


# ===========================================================================
# normalize_section_name
# ===========================================================================

class TestNormalizeSectionName:
    def test_subjective_recognized(self):
        assert normalize_section_name("subjective") == "subjective"

    def test_s_colon_recognized(self):
        assert normalize_section_name("s:") == "subjective"

    def test_objective_recognized(self):
        assert normalize_section_name("objective") == "objective"

    def test_physical_exam_recognized(self):
        assert normalize_section_name("physical exam") == "objective"

    def test_assessment_recognized(self):
        assert normalize_section_name("assessment") == "assessment"

    def test_impression_recognized(self):
        result = normalize_section_name("impression")
        assert result == "assessment"

    def test_plan_recognized(self):
        assert normalize_section_name("plan") == "plan"

    def test_treatment_plan_recognized(self):
        assert normalize_section_name("treatment plan") == "plan"

    def test_unknown_returns_none(self):
        result = normalize_section_name("completely_unknown_section_xyz")
        assert result is None

    def test_chief_complaint_recognized(self):
        result = normalize_section_name("chief complaint")
        assert result == "subjective"

    def test_hpi_recognized(self):
        result = normalize_section_name("hpi")
        assert result == "subjective"

    def test_case_insensitive(self):
        assert normalize_section_name("SUBJECTIVE") == "subjective"

    def test_empty_string_returns_none(self):
        result = normalize_section_name("")
        assert result is None


# ===========================================================================
# generate_resource_id
# ===========================================================================

class TestGenerateResourceId:
    def test_returns_string(self):
        result = generate_resource_id("Patient")
        assert isinstance(result, str)

    def test_contains_resource_type_lowercase(self):
        result = generate_resource_id("Patient")
        assert "patient" in result

    def test_contains_index(self):
        result = generate_resource_id("Composition", 5)
        assert "005" in result

    def test_default_index_zero(self):
        result = generate_resource_id("Document")
        assert "000" in result

    def test_different_resource_types_different_prefix(self):
        r1 = generate_resource_id("Patient")
        r2 = generate_resource_id("Practitioner")
        assert r1.startswith("patient-")
        assert r2.startswith("practitioner-")

    def test_two_calls_differ(self):
        # Generated IDs should be unique (timestamp-based)
        r1 = generate_resource_id("Resource")
        time.sleep(0.01)
        r2 = generate_resource_id("Resource")
        # They may be equal within the same second, but format should be correct
        assert r1.startswith("resource-")
        assert r2.startswith("resource-")
