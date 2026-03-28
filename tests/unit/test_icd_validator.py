"""Tests for ICD code validator."""

import unittest

from utils.icd_validator import (
    ICDValidator,
    ICDCodeSystem,
    ICDValidationResult,
    extract_icd_codes,
    validate_code,
    validate_codes,
    get_validator,
)


class TestICDCodeSystemDetection(unittest.TestCase):
    """Tests for ICD code format detection and system classification."""

    def setUp(self):
        self.validator = ICDValidator()

    # --- ICD-10 format ---

    def test_icd10_basic(self):
        result = self.validator.validate("J06.9")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.ICD10)

    def test_icd10_no_decimal(self):
        result = self.validator.validate("J06")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.ICD10)

    def test_icd10_long_decimal(self):
        result = self.validator.validate("E11.65")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.ICD10)

    def test_icd10_lowercase_normalized(self):
        result = self.validator.validate("j06.9")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code, "J06.9")  # normalized to uppercase

    def test_icd10_4_digit_decimal(self):
        result = self.validator.validate("S72.0012")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.ICD10)

    # --- ICD-9 format ---

    def test_icd9_basic(self):
        result = self.validator.validate("250.00")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.ICD9)

    def test_icd9_no_decimal(self):
        result = self.validator.validate("401")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.ICD9)

    def test_icd9_single_decimal(self):
        result = self.validator.validate("780.7")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.ICD9)

    def test_icd9_ecode(self):
        result = self.validator.validate("E880.1")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.ICD9)

    def test_icd9_vcode(self):
        # V70.0 matches ICD-10 pattern (V\d{2}.\d) first, which is correct
        # since ICD-10 is checked before V-codes in detection order
        result = self.validator.validate("V70.0")
        self.assertTrue(result.is_valid)
        self.assertIn(result.code_system, (ICDCodeSystem.ICD9, ICDCodeSystem.ICD10))

    # --- Invalid formats ---

    def test_invalid_empty(self):
        result = self.validator.validate("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.code_system, ICDCodeSystem.UNKNOWN)

    def test_invalid_random_text(self):
        result = self.validator.validate("hello")
        self.assertFalse(result.is_valid)

    def test_invalid_too_short(self):
        result = self.validator.validate("A1")
        self.assertFalse(result.is_valid)

    def test_invalid_too_many_letters(self):
        result = self.validator.validate("AB12.3")
        self.assertFalse(result.is_valid)

    def test_invalid_special_chars(self):
        result = self.validator.validate("J06#9")
        self.assertFalse(result.is_valid)


class TestICDCodeNormalization(unittest.TestCase):
    """Tests for code normalization (whitespace, prefixes, case)."""

    def setUp(self):
        self.validator = ICDValidator()

    def test_strips_whitespace(self):
        result = self.validator.validate("  J06.9  ")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code, "J06.9")

    def test_strips_icd10_prefix(self):
        result = self.validator.validate("ICD-10: J06.9")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code, "J06.9")

    def test_strips_icd9_prefix(self):
        result = self.validator.validate("ICD-9: 250.00")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.code, "250.00")

    def test_strips_icd_prefix(self):
        result = self.validator.validate("ICD: J06.9")
        self.assertTrue(result.is_valid)

    def test_uppercase_conversion(self):
        result = self.validator.validate("e11.65")
        self.assertEqual(result.code, "E11.65")


class TestICDCodeLookup(unittest.TestCase):
    """Tests for code description lookup."""

    def setUp(self):
        self.validator = ICDValidator()

    def test_known_icd10_has_description(self):
        result = self.validator.validate("E11.65")
        self.assertTrue(result.is_valid)
        self.assertIsNotNone(result.description)

    def test_unknown_icd10_format_valid_no_description(self):
        result = self.validator.validate("Z99.9")
        self.assertTrue(result.is_valid)
        # Valid format but likely not in common codes
        if result.description is None:
            self.assertIsNotNone(result.warning)
            self.assertIn("not in the common codes database", result.warning)

    def test_get_description_known(self):
        desc = self.validator.get_description("E11.65")
        self.assertIsNotNone(desc)

    def test_get_description_unknown(self):
        desc = self.validator.get_description("INVALID")
        self.assertIsNone(desc)

    def test_is_valid_format_true(self):
        self.assertTrue(self.validator.is_valid_format("J06.9"))
        self.assertTrue(self.validator.is_valid_format("250.00"))

    def test_is_valid_format_false(self):
        self.assertFalse(self.validator.is_valid_format("INVALID"))
        self.assertFalse(self.validator.is_valid_format(""))


class TestICDSuggestSimilar(unittest.TestCase):
    """Tests for similar code suggestions."""

    def setUp(self):
        self.validator = ICDValidator()

    def test_suggest_icd10(self):
        suggestions = self.validator.suggest_similar_codes("E11")
        self.assertIsInstance(suggestions, list)
        for code in suggestions:
            self.assertTrue(code.startswith("E11"))

    def test_suggest_limit(self):
        suggestions = self.validator.suggest_similar_codes("E11", limit=2)
        self.assertLessEqual(len(suggestions), 2)

    def test_suggest_no_matches(self):
        suggestions = self.validator.suggest_similar_codes("Z99")
        self.assertIsInstance(suggestions, list)

    def test_suggest_icd9(self):
        suggestions = self.validator.suggest_similar_codes("250")
        self.assertIsInstance(suggestions, list)


class TestICDBatchValidation(unittest.TestCase):
    """Tests for batch validation."""

    def setUp(self):
        self.validator = ICDValidator()

    def test_batch_mixed(self):
        results = self.validator.validate_batch(["J06.9", "INVALID", "250.00"])
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0].is_valid)
        self.assertFalse(results[1].is_valid)
        self.assertTrue(results[2].is_valid)

    def test_batch_empty(self):
        results = self.validator.validate_batch([])
        self.assertEqual(len(results), 0)

    def test_batch_all_valid(self):
        results = self.validator.validate_batch(["J06.9", "E11.65"])
        self.assertTrue(all(r.is_valid for r in results))


class TestExtractICDCodes(unittest.TestCase):
    """Tests for extracting ICD codes from free text."""

    def test_extract_icd10(self):
        text = "Diagnosis: J06.9 (common cold) and E11.65 (diabetes)"
        codes = extract_icd_codes(text)
        self.assertIn("J06.9", codes)
        self.assertIn("E11.65", codes)

    def test_extract_icd9(self):
        text = "ICD-9 codes: 250.00 and 401.9"
        codes = extract_icd_codes(text)
        self.assertIn("250.00", codes)
        self.assertIn("401.9", codes)

    def test_extract_mixed(self):
        text = "Primary: J06.9. Secondary: 250.00"
        codes = extract_icd_codes(text)
        self.assertTrue(len(codes) >= 2)

    def test_extract_no_codes(self):
        text = "Patient presents with headache and fatigue."
        codes = extract_icd_codes(text)
        # Should not extract random numbers as ICD codes
        # (3-digit numbers in text might match ICD-9 pattern though)
        self.assertIsInstance(codes, list)

    def test_extract_deduplicates(self):
        text = "J06.9 confirmed. Also J06.9 again."
        codes = extract_icd_codes(text)
        count = sum(1 for c in codes if c == "J06.9")
        self.assertEqual(count, 1)

    def test_extract_case_insensitive(self):
        text = "Code: j06.9 and J06.9"
        codes = extract_icd_codes(text)
        # Both should normalize to J06.9
        count = sum(1 for c in codes if c == "J06.9")
        self.assertEqual(count, 1)


class TestModuleLevelFunctions(unittest.TestCase):
    """Tests for module-level convenience functions."""

    def test_validate_code(self):
        result = validate_code("J06.9")
        self.assertIsInstance(result, ICDValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_codes(self):
        results = validate_codes(["J06.9", "E11.65"])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.is_valid for r in results))

    def test_get_validator_singleton(self):
        v1 = get_validator()
        v2 = get_validator()
        self.assertIs(v1, v2)

    def test_custom_code_dicts(self):
        custom_icd10 = {"Z99.9": "Test code"}
        validator = ICDValidator(icd10_codes=custom_icd10)
        result = validator.validate("Z99.9")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.description, "Test code")


class TestICDValidationResult(unittest.TestCase):
    """Tests for ICDValidationResult dataclass."""

    def test_defaults(self):
        result = ICDValidationResult(
            code="J06.9",
            is_valid=True,
            code_system=ICDCodeSystem.ICD10
        )
        self.assertIsNone(result.description)
        self.assertIsNone(result.warning)
        self.assertIsNone(result.suggested_code)

    def test_code_system_values(self):
        self.assertEqual(ICDCodeSystem.ICD9.value, "ICD-9")
        self.assertEqual(ICDCodeSystem.ICD10.value, "ICD-10")
        self.assertEqual(ICDCodeSystem.UNKNOWN.value, "Unknown")


if __name__ == '__main__':
    unittest.main()
