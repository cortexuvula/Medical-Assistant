"""
Tests for src/utils/icd_validator.py

Covers: ICDCodeSystem enum, ICDValidationResult dataclass, regex patterns,
ICDValidator class methods, extract_icd_codes, and module-level convenience
functions.
"""

import sys
import re
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.icd_validator import (
    ICDCodeSystem,
    ICDValidationResult,
    ICDValidator,
    ICD10_PATTERN,
    ICD9_PATTERN,
    ICD9_ECODE_PATTERN,
    ICD9_VCODE_PATTERN,
    extract_icd_codes,
    validate_code,
    validate_codes,
    get_validator,
)
import utils.icd_validator as _icd_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_validator_singleton():
    """Reset the module-level validator singleton before/after each test."""
    _icd_module._default_validator = None
    yield
    _icd_module._default_validator = None


@pytest.fixture()
def validator():
    return ICDValidator()


@pytest.fixture()
def custom_validator():
    """Validator backed by small custom code dicts for predictable lookups."""
    icd10 = {"J06.9": "Acute upper respiratory infection, unspecified"}
    icd9 = {"250.00": "Diabetes mellitus without complication, type II"}
    return ICDValidator(icd10_codes=icd10, icd9_codes=icd9)


# ===========================================================================
# 1. ICDCodeSystem enum
# ===========================================================================

class TestICDCodeSystemEnum:
    def test_has_three_members(self):
        assert len(ICDCodeSystem) == 3

    def test_icd9_value(self):
        assert ICDCodeSystem.ICD9.value == "ICD-9"

    def test_icd10_value(self):
        assert ICDCodeSystem.ICD10.value == "ICD-10"

    def test_unknown_value(self):
        assert ICDCodeSystem.UNKNOWN.value == "Unknown"

    def test_members_are_enum(self):
        for member in ICDCodeSystem:
            assert isinstance(member, ICDCodeSystem)

    def test_access_by_name(self):
        assert ICDCodeSystem["ICD9"] is ICDCodeSystem.ICD9
        assert ICDCodeSystem["ICD10"] is ICDCodeSystem.ICD10
        assert ICDCodeSystem["UNKNOWN"] is ICDCodeSystem.UNKNOWN


# ===========================================================================
# 2. ICDValidationResult dataclass
# ===========================================================================

class TestICDValidationResult:
    def test_required_fields_stored(self):
        result = ICDValidationResult(
            code="J06.9",
            is_valid=True,
            code_system=ICDCodeSystem.ICD10,
        )
        assert result.code == "J06.9"
        assert result.is_valid is True
        assert result.code_system is ICDCodeSystem.ICD10

    def test_optional_fields_default_to_none(self):
        result = ICDValidationResult(
            code="J06.9",
            is_valid=True,
            code_system=ICDCodeSystem.ICD10,
        )
        assert result.description is None
        assert result.warning is None
        assert result.suggested_code is None

    def test_optional_fields_can_be_set(self):
        result = ICDValidationResult(
            code="J06.9",
            is_valid=True,
            code_system=ICDCodeSystem.ICD10,
            description="Some description",
            warning="Some warning",
            suggested_code="J07.0",
        )
        assert result.description == "Some description"
        assert result.warning == "Some warning"
        assert result.suggested_code == "J07.0"

    def test_is_valid_false(self):
        result = ICDValidationResult(
            code="INVALID",
            is_valid=False,
            code_system=ICDCodeSystem.UNKNOWN,
        )
        assert result.is_valid is False

    def test_fields_are_mutable(self):
        result = ICDValidationResult(
            code="J06.9",
            is_valid=True,
            code_system=ICDCodeSystem.ICD10,
        )
        result.warning = "post-construction warning"
        assert result.warning == "post-construction warning"


# ===========================================================================
# 3. ICD10_PATTERN regex
# ===========================================================================

class TestICD10Pattern:
    def test_matches_j069(self):
        assert ICD10_PATTERN.match("J06.9")

    def test_matches_e1165(self):
        assert ICD10_PATTERN.match("E11.65")

    def test_matches_m545(self):
        assert ICD10_PATTERN.match("M54.5")

    def test_matches_a00_no_decimal(self):
        assert ICD10_PATTERN.match("A00")

    def test_matches_lowercase(self):
        # IGNORECASE flag is set on the pattern
        assert ICD10_PATTERN.match("j06.9")

    def test_rejects_icd9_250(self):
        assert not ICD10_PATTERN.match("250.00")

    def test_rejects_invalid_string(self):
        assert not ICD10_PATTERN.match("INVALID")

    def test_rejects_only_digits(self):
        assert not ICD10_PATTERN.match("123.4")

    def test_matches_long_subcode(self):
        # Up to 4 digits after decimal is valid per the pattern
        assert ICD10_PATTERN.match("S72.0012")

    def test_rejects_two_leading_letters(self):
        assert not ICD10_PATTERN.match("AB1.2")


# ===========================================================================
# 4. ICD9_PATTERN regex
# ===========================================================================

class TestICD9Pattern:
    def test_matches_250_00(self):
        assert ICD9_PATTERN.match("250.00")

    def test_matches_401_9(self):
        assert ICD9_PATTERN.match("401.9")

    def test_matches_780_79(self):
        assert ICD9_PATTERN.match("780.79")

    def test_matches_three_digits_no_decimal(self):
        assert ICD9_PATTERN.match("401")

    def test_rejects_icd10_j069(self):
        assert not ICD9_PATTERN.match("J06.9")

    def test_rejects_letters(self):
        assert not ICD9_PATTERN.match("ABC")

    def test_rejects_too_many_decimal_digits(self):
        # Pattern allows only 1-2 digits after decimal
        assert not ICD9_PATTERN.match("250.001")


# ===========================================================================
# 5. ICD9_ECODE_PATTERN regex
# ===========================================================================

class TestICD9EcodePattern:
    def test_matches_e800(self):
        assert ICD9_ECODE_PATTERN.match("E800")

    def test_matches_e800_with_decimal(self):
        assert ICD9_ECODE_PATTERN.match("E800.0")

    def test_matches_lowercase_e(self):
        assert ICD9_ECODE_PATTERN.match("e800")

    def test_rejects_numeric_only(self):
        assert not ICD9_ECODE_PATTERN.match("800.0")

    def test_rejects_icd10_pattern(self):
        assert not ICD9_ECODE_PATTERN.match("J06.9")


# ===========================================================================
# 6. ICD9_VCODE_PATTERN regex
# ===========================================================================

class TestICD9VcodePattern:
    def test_matches_v10(self):
        assert ICD9_VCODE_PATTERN.match("V10")

    def test_matches_v10_1(self):
        assert ICD9_VCODE_PATTERN.match("V10.1")

    def test_matches_lowercase_v(self):
        assert ICD9_VCODE_PATTERN.match("v10.1")

    def test_rejects_numeric_only(self):
        assert not ICD9_VCODE_PATTERN.match("10.1")

    def test_rejects_icd10_pattern(self):
        assert not ICD9_VCODE_PATTERN.match("J06.9")


# ===========================================================================
# 7. ICDValidator constructor
# ===========================================================================

class TestICDValidatorConstructor:
    def test_creates_with_defaults(self, validator):
        assert validator is not None

    def test_default_icd10_codes_non_empty(self, validator):
        assert len(validator.icd10_codes) > 0

    def test_default_icd9_codes_non_empty(self, validator):
        assert len(validator.icd9_codes) > 0

    def test_custom_icd10_codes_used(self):
        custom = {"Z00.00": "test"}
        v = ICDValidator(icd10_codes=custom)
        assert v.icd10_codes == custom

    def test_custom_icd9_codes_used(self):
        custom = {"999.9": "test"}
        v = ICDValidator(icd9_codes=custom)
        assert v.icd9_codes == custom

    def test_custom_icd10_default_icd9_preserved(self):
        custom_10 = {"Z00.00": "test"}
        v = ICDValidator(icd10_codes=custom_10)
        # icd9 should still be the module default (non-empty)
        assert len(v.icd9_codes) > 0


# ===========================================================================
# 8. ICDValidator.validate – ICD-10 valid codes
# ===========================================================================

class TestValidateICD10:
    def test_j069_is_valid(self, validator):
        result = validator.validate("J06.9")
        assert result.is_valid is True

    def test_j069_code_system_icd10(self, validator):
        result = validator.validate("J06.9")
        assert result.code_system is ICDCodeSystem.ICD10

    def test_j069_has_description(self, validator):
        result = validator.validate("J06.9")
        # J06.9 is in COMMON_ICD10_CODES
        assert isinstance(result.description, str) and len(result.description) > 0

    def test_normalized_code_stored_in_result(self, validator):
        result = validator.validate("j06.9")
        assert result.code == "J06.9"

    def test_known_icd10_no_warning(self, validator):
        result = validator.validate("J06.9")
        assert result.warning is None

    def test_format_valid_unknown_icd10_has_warning(self, validator):
        # Syntactically valid ICD-10 but not in common codes
        result = validator.validate("Z99.99")
        assert result.is_valid is True
        assert result.code_system is ICDCodeSystem.ICD10
        assert result.warning is not None

    def test_e1165_is_valid(self, validator):
        result = validator.validate("E11.65")
        assert result.is_valid is True
        assert result.code_system is ICDCodeSystem.ICD10

    def test_i10_hypertension(self, validator):
        result = validator.validate("I10")
        assert result.is_valid is True
        assert result.code_system is ICDCodeSystem.ICD10


# ===========================================================================
# 9. ICDValidator.validate – ICD-9 valid codes
# ===========================================================================

class TestValidateICD9:
    def test_250_00_is_valid(self, validator):
        result = validator.validate("250.00")
        assert result.is_valid is True

    def test_250_00_code_system_icd9(self, validator):
        result = validator.validate("250.00")
        assert result.code_system is ICDCodeSystem.ICD9

    def test_250_00_has_description(self, validator):
        result = validator.validate("250.00")
        assert isinstance(result.description, str) and len(result.description) > 0

    def test_401_9_is_valid(self, validator):
        result = validator.validate("401.9")
        assert result.is_valid is True
        assert result.code_system is ICDCodeSystem.ICD9

    def test_known_icd9_no_warning(self, validator):
        result = validator.validate("250.00")
        assert result.warning is None

    def test_format_valid_unknown_icd9_has_warning(self, validator):
        result = validator.validate("999.9")
        assert result.is_valid is True
        assert result.warning is not None


# ===========================================================================
# 10. ICDValidator.validate – UNKNOWN / INVALID
# ===========================================================================

class TestValidateInvalid:
    def test_invalid_string_not_valid(self, validator):
        result = validator.validate("INVALID")
        assert result.is_valid is False

    def test_invalid_string_code_system_unknown(self, validator):
        result = validator.validate("INVALID")
        assert result.code_system is ICDCodeSystem.UNKNOWN

    def test_invalid_string_has_warning(self, validator):
        result = validator.validate("INVALID")
        assert result.warning is not None

    def test_empty_string_is_invalid(self, validator):
        result = validator.validate("")
        assert result.is_valid is False
        assert result.code_system is ICDCodeSystem.UNKNOWN

    def test_empty_string_warning_set(self, validator):
        result = validator.validate("")
        assert result.warning is not None

    def test_random_garbage_is_invalid(self, validator):
        result = validator.validate("!@#$%")
        assert result.is_valid is False

    def test_too_many_leading_letters_is_invalid(self, validator):
        result = validator.validate("AB123")
        assert result.is_valid is False


# ===========================================================================
# 11. ICDValidator.validate – normalisation (whitespace / case)
# ===========================================================================

class TestValidateNormalization:
    def test_leading_trailing_whitespace_stripped(self, validator):
        result = validator.validate("  J06.9  ")
        assert result.is_valid is True
        assert result.code == "J06.9"

    def test_lowercase_normalized_to_uppercase(self, validator):
        result = validator.validate("j06.9")
        assert result.is_valid is True
        assert result.code == "J06.9"

    def test_mixed_case_resolves_to_icd10(self, validator):
        result = validator.validate("j06.9")
        assert result.code_system is ICDCodeSystem.ICD10

    def test_icd10_prefix_stripped(self, validator):
        result = validator.validate("ICD-10:J06.9")
        assert result.is_valid is True
        assert result.code == "J06.9"

    def test_icd9_prefix_stripped(self, validator):
        result = validator.validate("ICD-9:250.00")
        assert result.is_valid is True
        assert result.code == "250.00"


# ===========================================================================
# 12. ICDValidator.validate_batch
# ===========================================================================

class TestValidateBatch:
    def test_returns_list(self, validator):
        results = validator.validate_batch(["J06.9", "250.00", "INVALID"])
        assert isinstance(results, list)

    def test_returns_correct_count(self, validator):
        results = validator.validate_batch(["J06.9", "250.00", "INVALID"])
        assert len(results) == 3

    def test_first_result_icd10(self, validator):
        results = validator.validate_batch(["J06.9", "250.00", "INVALID"])
        assert results[0].code_system is ICDCodeSystem.ICD10

    def test_second_result_icd9(self, validator):
        results = validator.validate_batch(["J06.9", "250.00", "INVALID"])
        assert results[1].code_system is ICDCodeSystem.ICD9

    def test_third_result_invalid(self, validator):
        results = validator.validate_batch(["J06.9", "250.00", "INVALID"])
        assert results[2].is_valid is False

    def test_empty_list_returns_empty(self, validator):
        results = validator.validate_batch([])
        assert results == []

    def test_all_results_are_validation_result_type(self, validator):
        results = validator.validate_batch(["J06.9", "INVALID"])
        for r in results:
            assert isinstance(r, ICDValidationResult)

    def test_single_item_batch(self, validator):
        results = validator.validate_batch(["J06.9"])
        assert len(results) == 1
        assert results[0].is_valid is True


# ===========================================================================
# 13. ICDValidator.get_description
# ===========================================================================

class TestGetDescription:
    def test_known_icd10_returns_string(self, validator):
        desc = validator.get_description("J06.9")
        assert isinstance(desc, str) and len(desc) > 0

    def test_known_icd9_returns_string(self, validator):
        desc = validator.get_description("250.00")
        assert isinstance(desc, str) and len(desc) > 0

    def test_unknown_code_returns_none(self, validator):
        # A code not in the common database should return None
        desc = validator.get_description("Z99.99")
        assert desc is None

    def test_lowercase_code_normalised_before_lookup(self, validator):
        desc = validator.get_description("j06.9")
        assert desc is not None

    def test_custom_validator_returns_custom_description(self, custom_validator):
        desc = custom_validator.get_description("J06.9")
        assert desc == "Acute upper respiratory infection, unspecified"

    def test_custom_validator_code_not_in_dict_returns_none(self, custom_validator):
        desc = custom_validator.get_description("I10")
        assert desc is None


# ===========================================================================
# 14. extract_icd_codes
# ===========================================================================

class TestExtractICDCodes:
    def test_extracts_icd10_from_text(self):
        codes = extract_icd_codes("Patient diagnosed with J06.9 today.")
        upper = [c.upper() for c in codes]
        assert "J06.9" in upper

    def test_extracts_icd9_from_text(self):
        codes = extract_icd_codes("History of 250.00 diabetes.")
        assert "250.00" in codes

    def test_extracts_both_systems(self):
        codes = extract_icd_codes("Patient has J06.9 and 250.00")
        upper = [c.upper() for c in codes]
        assert "J06.9" in upper
        assert "250.00" in upper

    def test_returns_list(self):
        codes = extract_icd_codes("J06.9")
        assert isinstance(codes, list)

    def test_empty_text_returns_empty_list(self):
        codes = extract_icd_codes("")
        assert codes == []

    def test_no_codes_returns_empty_list(self):
        codes = extract_icd_codes("No diagnostic codes here.")
        assert codes == []

    def test_deduplicates_codes(self):
        codes = extract_icd_codes("J06.9 and J06.9 again")
        upper = [c.upper() for c in codes]
        count = upper.count("J06.9")
        assert count == 1

    def test_multiple_icd10_codes(self):
        codes = extract_icd_codes("Diagnoses: J06.9, E11.65, M54.5")
        upper = [c.upper() for c in codes]
        assert "J06.9" in upper
        assert "E11.65" in upper
        assert "M54.5" in upper


# ===========================================================================
# 15. Module-level convenience functions (validate_code / validate_codes)
# ===========================================================================

class TestConvenienceFunctions:
    def test_validate_code_returns_result_instance(self):
        result = validate_code("J06.9")
        assert isinstance(result, ICDValidationResult)

    def test_validate_code_icd10_is_valid(self):
        result = validate_code("J06.9")
        assert result.is_valid is True
        assert result.code_system is ICDCodeSystem.ICD10

    def test_validate_code_icd9_is_valid(self):
        result = validate_code("250.00")
        assert result.is_valid is True
        assert result.code_system is ICDCodeSystem.ICD9

    def test_validate_code_invalid_string(self):
        result = validate_code("INVALID")
        assert result.is_valid is False

    def test_validate_codes_returns_list(self):
        results = validate_codes(["J06.9"])
        assert isinstance(results, list)

    def test_validate_codes_single_item(self):
        results = validate_codes(["J06.9"])
        assert len(results) == 1
        assert results[0].is_valid is True

    def test_validate_codes_multiple_items(self):
        results = validate_codes(["J06.9", "250.00", "INVALID"])
        assert len(results) == 3

    def test_validate_codes_empty_list(self):
        results = validate_codes([])
        assert results == []


# ===========================================================================
# 16. get_validator singleton
# ===========================================================================

class TestGetValidator:
    def test_returns_icd_validator_instance(self):
        v = get_validator()
        assert isinstance(v, ICDValidator)

    def test_returns_same_instance_on_second_call(self):
        v1 = get_validator()
        v2 = get_validator()
        assert v1 is v2

    def test_singleton_reset_creates_fresh_instance(self):
        # autouse fixture already reset it; calling get_validator() creates new
        v = get_validator()
        assert v is not None

    def test_singleton_is_functional(self):
        v = get_validator()
        result = v.validate("J06.9")
        assert result.is_valid is True
