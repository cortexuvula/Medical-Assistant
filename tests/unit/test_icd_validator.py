"""Tests for ICDValidator pure-logic methods."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pytest
from utils.icd_validator import (
    ICDValidator, ICDCodeSystem, ICDValidationResult,
    ICD10_PATTERN, ICD9_PATTERN, ICD9_ECODE_PATTERN, ICD9_VCODE_PATTERN,
    extract_icd_codes, get_validator, validate_code, validate_codes,
)
import utils.icd_validator as _icd_module


# ---------------------------------------------------------------------------
# Singleton reset fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_validator_singleton():
    """Reset the module-level validator singleton before/after each test."""
    _icd_module._default_validator = None
    yield
    _icd_module._default_validator = None


# ---------------------------------------------------------------------------
# TestIcdPatterns
# ---------------------------------------------------------------------------

class TestIcdPatterns:
    """Tests for compile-time regex constants."""

    # 1. ICD10_PATTERN matches "J06.9"
    def test_icd10_matches_j06_9(self):
        assert ICD10_PATTERN.match("J06.9") is not None

    # 2. ICD10_PATTERN matches "E11" (3 chars, no decimal)
    def test_icd10_matches_e11_no_decimal(self):
        assert ICD10_PATTERN.match("E11") is not None

    # 3. ICD10_PATTERN matches "E11.65"
    def test_icd10_matches_e11_65(self):
        assert ICD10_PATTERN.match("E11.65") is not None

    # 4. ICD10_PATTERN does NOT match "123"
    def test_icd10_does_not_match_digits_only(self):
        assert ICD10_PATTERN.match("123") is None

    # 5. ICD10_PATTERN does NOT match "J06.12345" (too many decimal digits)
    def test_icd10_does_not_match_too_many_decimal_digits(self):
        assert ICD10_PATTERN.match("J06.12345") is None

    # 6. ICD10_PATTERN matches "A00.0"
    def test_icd10_matches_a00_0(self):
        assert ICD10_PATTERN.match("A00.0") is not None

    # 7. ICD9_PATTERN matches "250.00"
    def test_icd9_matches_250_00(self):
        assert ICD9_PATTERN.match("250.00") is not None

    # 8. ICD9_PATTERN matches "780"
    def test_icd9_matches_780(self):
        assert ICD9_PATTERN.match("780") is not None

    # 9. ICD9_PATTERN does NOT match "E123" (starts with letter)
    def test_icd9_does_not_match_e123(self):
        assert ICD9_PATTERN.match("E123") is None

    # 10. ICD9_ECODE_PATTERN matches "E123"
    def test_icd9_ecode_matches_e123(self):
        assert ICD9_ECODE_PATTERN.match("E123") is not None

    # 11. ICD9_ECODE_PATTERN matches "E123.4"
    def test_icd9_ecode_matches_e123_4(self):
        assert ICD9_ECODE_PATTERN.match("E123.4") is not None

    # 12. ICD9_VCODE_PATTERN matches "V12.3"
    def test_icd9_vcode_matches_v12_3(self):
        assert ICD9_VCODE_PATTERN.match("V12.3") is not None

    # 13. ICD9_VCODE_PATTERN matches "V22"
    def test_icd9_vcode_matches_v22(self):
        assert ICD9_VCODE_PATTERN.match("V22") is not None


# ---------------------------------------------------------------------------
# TestNormalizeCode
# ---------------------------------------------------------------------------

class TestNormalizeCode:
    """Tests for ICDValidator._normalize_code."""

    def setup_method(self):
        self.v = ICDValidator()

    # 1. "  J06.9  " → "J06.9" (stripped)
    def test_strips_whitespace(self):
        assert self.v._normalize_code("  J06.9  ") == "J06.9"

    # 2. "j06.9" → "J06.9" (uppercased)
    def test_uppercases_code(self):
        assert self.v._normalize_code("j06.9") == "J06.9"

    # 3. "ICD-10:J06.9" → "J06.9"
    def test_removes_icd10_dash_prefix(self):
        assert self.v._normalize_code("ICD-10:J06.9") == "J06.9"

    # 4. "ICD-9:250.00" → "250.00"
    def test_removes_icd9_dash_prefix(self):
        assert self.v._normalize_code("ICD-9:250.00") == "250.00"

    # 5. "ICD10:E11.65" → "E11.65"
    def test_removes_icd10_no_dash_prefix(self):
        assert self.v._normalize_code("ICD10:E11.65") == "E11.65"

    # 6. "ICD:A01" → "A01"
    def test_removes_icd_prefix(self):
        assert self.v._normalize_code("ICD:A01") == "A01"

    # 7. Normal code unchanged: "J06.9" → "J06.9"
    def test_normal_code_unchanged(self):
        assert self.v._normalize_code("J06.9") == "J06.9"


# ---------------------------------------------------------------------------
# TestDetectCodeSystem
# ---------------------------------------------------------------------------

class TestDetectCodeSystem:
    """Tests for ICDValidator._detect_code_system."""

    def setup_method(self):
        self.v = ICDValidator()

    # 1. "J06.9" → ICD10
    def test_j06_9_is_icd10(self):
        assert self.v._detect_code_system("J06.9") == ICDCodeSystem.ICD10

    # 2. "E11.65" → ICD10
    def test_e11_65_is_icd10(self):
        assert self.v._detect_code_system("E11.65") == ICDCodeSystem.ICD10

    # 3. "A00" → ICD10
    def test_a00_is_icd10(self):
        assert self.v._detect_code_system("A00") == ICDCodeSystem.ICD10

    # 4. "250.00" → ICD9
    def test_250_00_is_icd9(self):
        assert self.v._detect_code_system("250.00") == ICDCodeSystem.ICD9

    # 5. "780" → ICD9
    def test_780_is_icd9(self):
        assert self.v._detect_code_system("780") == ICDCodeSystem.ICD9

    # 6. "E123" → ICD9 (E-code)
    def test_e123_is_icd9_ecode(self):
        assert self.v._detect_code_system("E123") == ICDCodeSystem.ICD9

    # 7. "V12.3" → detected as ICD10 because ICD10_PATTERN (letter + 2 digits +
    #    optional decimal) matches before the ICD-9 V-code check runs
    def test_v12_3_detected_before_vcode_check(self):
        # V12.3 matches ICD10_PATTERN (V + 12 + .3) so it is returned as ICD10
        assert self.v._detect_code_system("V12.3") == ICDCodeSystem.ICD10

    # 8. "" → UNKNOWN
    def test_empty_string_is_unknown(self):
        assert self.v._detect_code_system("") == ICDCodeSystem.UNKNOWN

    # 9. "INVALID" → UNKNOWN
    def test_invalid_string_is_unknown(self):
        assert self.v._detect_code_system("INVALID") == ICDCodeSystem.UNKNOWN

    # 10. "12" → UNKNOWN (2 digits, doesn't match ICD9 3-digit pattern)
    def test_two_digits_is_unknown(self):
        assert self.v._detect_code_system("12") == ICDCodeSystem.UNKNOWN


# ---------------------------------------------------------------------------
# TestValidate
# ---------------------------------------------------------------------------

class TestValidate:
    """Tests for ICDValidator.validate."""

    def setup_method(self):
        self.v = ICDValidator()

    # 1. Empty string → is_valid=False, warning about empty
    def test_empty_string_is_invalid(self):
        result = self.v.validate("")
        assert result.is_valid is False

    def test_empty_string_has_warning(self):
        result = self.v.validate("")
        assert result.warning is not None and len(result.warning) > 0

    # 2. Invalid format "INVALID" → is_valid=False, code_system=UNKNOWN, warning about format
    def test_invalid_format_is_invalid(self):
        result = self.v.validate("INVALID")
        assert result.is_valid is False

    def test_invalid_format_code_system_unknown(self):
        result = self.v.validate("INVALID")
        assert result.code_system == ICDCodeSystem.UNKNOWN

    def test_invalid_format_has_warning(self):
        result = self.v.validate("INVALID")
        assert result.warning is not None

    # 3. "J06.9" → is_valid=True, code_system=ICD10
    def test_j06_9_is_valid(self):
        result = self.v.validate("J06.9")
        assert result.is_valid is True

    def test_j06_9_is_icd10(self):
        result = self.v.validate("J06.9")
        assert result.code_system == ICDCodeSystem.ICD10

    # 4. Known ICD-10 code ("J06.9") → description is not None
    def test_known_code_has_description(self):
        result = self.v.validate("J06.9")
        assert result.description is not None
        assert isinstance(result.description, str)

    # 5. Valid format but unknown code → is_valid=True, warning about not in database
    def test_valid_format_unknown_code_has_warning(self):
        result = self.v.validate("Z99.99")
        assert result.is_valid is True
        assert result.warning is not None

    # 6. "250.00" → is_valid=True, code_system=ICD9
    def test_250_00_is_valid(self):
        result = self.v.validate("250.00")
        assert result.is_valid is True

    def test_250_00_is_icd9(self):
        result = self.v.validate("250.00")
        assert result.code_system == ICDCodeSystem.ICD9

    # 7. Normalized code stored in result.code (not raw input)
    def test_result_code_is_normalized(self):
        result = self.v.validate(" j06.9 ")
        assert result.code == "J06.9"

    # 8. " j06.9 " (with spaces, lowercase) → is_valid=True after normalization
    def test_lowercase_whitespace_code_is_valid(self):
        result = self.v.validate(" j06.9 ")
        assert result.is_valid is True

    # 9. "ICD-10:J06.9" prefix stripped → valid
    def test_prefix_stripped_code_is_valid(self):
        result = self.v.validate("ICD-10:J06.9")
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# TestIsValidFormat
# ---------------------------------------------------------------------------

class TestIsValidFormat:
    """Tests for ICDValidator.is_valid_format."""

    def setup_method(self):
        self.v = ICDValidator()

    # 1. "J06.9" → True
    def test_j06_9_is_valid_format(self):
        assert self.v.is_valid_format("J06.9") is True

    # 2. "250.00" → True
    def test_250_00_is_valid_format(self):
        assert self.v.is_valid_format("250.00") is True

    # 3. "INVALID" → False
    def test_invalid_is_not_valid_format(self):
        assert self.v.is_valid_format("INVALID") is False

    # 4. "" → False
    def test_empty_string_is_not_valid_format(self):
        assert self.v.is_valid_format("") is False

    # 5. "E123" → True (ICD-9 E-code)
    def test_ecode_is_valid_format(self):
        assert self.v.is_valid_format("E123") is True

    # 6. "V12" → True (ICD-9 V-code)
    def test_vcode_is_valid_format(self):
        assert self.v.is_valid_format("V12") is True


# ---------------------------------------------------------------------------
# TestGetDescription
# ---------------------------------------------------------------------------

class TestGetDescription:
    """Tests for ICDValidator.get_description."""

    def setup_method(self):
        self.v = ICDValidator()

    # 1. Known ICD-10 code returns string description
    def test_known_code_returns_description(self):
        desc = self.v.get_description("J06.9")
        assert isinstance(desc, str)
        assert len(desc) > 0

    # 2. Unknown valid format returns None
    def test_unknown_valid_format_returns_none(self):
        desc = self.v.get_description("Z99.99")
        assert desc is None

    # 3. Invalid code returns None
    def test_invalid_code_returns_none(self):
        desc = self.v.get_description("INVALID")
        assert desc is None

    # 4. Case-insensitive: "j06.9" normalized to "J06.9" for lookup
    def test_case_insensitive_lookup(self):
        desc_lower = self.v.get_description("j06.9")
        desc_upper = self.v.get_description("J06.9")
        assert desc_lower == desc_upper
        assert desc_lower is not None


# ---------------------------------------------------------------------------
# TestValidateBatch
# ---------------------------------------------------------------------------

class TestValidateBatch:
    """Tests for ICDValidator.validate_batch."""

    def setup_method(self):
        self.v = ICDValidator()

    # 1. Empty list → []
    def test_empty_list_returns_empty(self):
        assert self.v.validate_batch([]) == []

    # 2. Single code → list with 1 result
    def test_single_code_returns_list_of_one(self):
        results = self.v.validate_batch(["J06.9"])
        assert len(results) == 1

    # 3. Multiple codes → same length list
    def test_multiple_codes_same_length(self):
        codes = ["J06.9", "250.00", "E11.65"]
        results = self.v.validate_batch(codes)
        assert len(results) == 3

    # 4. Mixed valid/invalid codes in batch
    def test_mixed_valid_invalid_batch(self):
        codes = ["J06.9", "INVALID", "250.00"]
        results = self.v.validate_batch(codes)
        assert results[0].is_valid is True
        assert results[1].is_valid is False
        assert results[2].is_valid is True


# ---------------------------------------------------------------------------
# TestSuggestSimilarCodes
# ---------------------------------------------------------------------------

class TestSuggestSimilarCodes:
    """Tests for ICDValidator.suggest_similar_codes."""

    def setup_method(self):
        self.v = ICDValidator()

    # 1. Valid ICD-10 code prefix → returns list
    def test_valid_prefix_returns_list(self):
        suggestions = self.v.suggest_similar_codes("J06.9")
        assert isinstance(suggestions, list)

    # 2. Returns at most `limit` suggestions
    def test_at_most_limit_suggestions(self):
        suggestions = self.v.suggest_similar_codes("J06.9", limit=5)
        assert len(suggestions) <= 5

    # 3. "J06" prefix → suggestions all start with "J06"
    def test_j06_prefix_suggestions_start_with_j06(self):
        suggestions = self.v.suggest_similar_codes("J06", limit=10)
        for s in suggestions:
            assert s.startswith("J06")

    # 4. Completely invalid code → returns [] or partial list
    def test_completely_invalid_code_returns_list(self):
        suggestions = self.v.suggest_similar_codes("ZZZZZ")
        assert isinstance(suggestions, list)

    # 5. limit=1 → at most 1 result
    def test_limit_one_returns_at_most_one(self):
        suggestions = self.v.suggest_similar_codes("J06.9", limit=1)
        assert len(suggestions) <= 1


# ---------------------------------------------------------------------------
# TestExtractIcdCodes
# ---------------------------------------------------------------------------

class TestExtractIcdCodes:
    """Tests for the extract_icd_codes module-level function."""

    # 1. Empty string → []
    def test_empty_string_returns_empty(self):
        assert extract_icd_codes("") == []

    # 2. "Patient has J06.9" → ["J06.9"]
    def test_single_icd10_in_text(self):
        result = extract_icd_codes("Patient has J06.9")
        assert "J06.9" in result

    # 3. "ICD: 250.00 confirmed" → ["250.00"]
    def test_icd9_in_text(self):
        result = extract_icd_codes("ICD: 250.00 confirmed")
        assert "250.00" in result

    # 4. Text with multiple ICD-10 codes → all found
    def test_multiple_icd10_codes_found(self):
        text = "Diagnoses: J06.9, E11.65, I10"
        result = extract_icd_codes(text)
        assert "J06.9" in result
        assert "E11.65" in result
        assert "I10" in result

    # 5. Text with ICD-9 code (3 digits) → found
    def test_icd9_three_digit_code_found(self):
        text = "Old code 780 still used"
        result = extract_icd_codes(text)
        assert "780" in result

    # 6. Duplicates removed: same code twice → once in output
    def test_duplicate_codes_returned_once(self):
        text = "J06.9 and J06.9 again"
        result = extract_icd_codes(text)
        assert result.count("J06.9") == 1

    # 7. Output is uppercased: "j06.9" in text → "J06.9" in result
    def test_output_uppercased(self):
        result = extract_icd_codes("diagnosis j06.9 noted")
        assert "J06.9" in result
        assert "j06.9" not in result

    # 8. Text with no ICD codes → []
    def test_no_icd_codes_returns_empty(self):
        result = extract_icd_codes("The patient feels fine today.")
        assert result == []

    # 9. Mixed ICD-10 and ICD-9 → both found
    def test_mixed_icd9_and_icd10(self):
        text = "ICD-10 code J06.9 and ICD-9 code 250.00"
        result = extract_icd_codes(text)
        assert "J06.9" in result
        assert "250.00" in result


# ---------------------------------------------------------------------------
# TestModuleLevelHelpers
# ---------------------------------------------------------------------------

class TestModuleLevelHelpers:
    """Tests for module-level helper functions."""

    # 1. `get_validator()` returns ICDValidator
    def test_get_validator_returns_icd_validator(self):
        v = get_validator()
        assert isinstance(v, ICDValidator)

    # 2. `get_validator()` returns same instance on second call (singleton)
    def test_get_validator_returns_singleton(self):
        v1 = get_validator()
        v2 = get_validator()
        assert v1 is v2

    # 3. `validate_code("J06.9")` returns ICDValidationResult
    def test_validate_code_returns_result(self):
        result = validate_code("J06.9")
        assert isinstance(result, ICDValidationResult)

    # 4. `validate_codes(["J06.9", "250.00"])` returns list of 2
    def test_validate_codes_returns_list_of_two(self):
        results = validate_codes(["J06.9", "250.00"])
        assert len(results) == 2
        assert all(isinstance(r, ICDValidationResult) for r in results)
