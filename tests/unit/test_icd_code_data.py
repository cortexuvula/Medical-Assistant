"""
Tests for src/utils/icd_code_data.py

Covers COMMON_ICD10_CODES and COMMON_ICD9_CODES static data dicts:
structure integrity, key format, value types, and presence of well-known codes.
Pure data verification — no mocking required.
"""

import sys
import re
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.icd_code_data import COMMON_ICD10_CODES, COMMON_ICD9_CODES


# ===========================================================================
# COMMON_ICD10_CODES
# ===========================================================================

class TestCommonIcd10Codes:
    def test_is_dict(self):
        assert isinstance(COMMON_ICD10_CODES, dict)

    def test_is_non_empty(self):
        assert len(COMMON_ICD10_CODES) > 0

    def test_all_keys_are_strings(self):
        for key in COMMON_ICD10_CODES:
            assert isinstance(key, str), f"Non-string key: {key!r}"

    def test_all_values_are_strings(self):
        for code, desc in COMMON_ICD10_CODES.items():
            assert isinstance(desc, str), f"Non-string value for {code}"

    def test_all_values_are_non_empty(self):
        for code, desc in COMMON_ICD10_CODES.items():
            assert desc.strip(), f"Empty description for {code}"

    def test_icd10_keys_have_plausible_format(self):
        # ICD-10 codes start with a letter followed by digits and optional suffix
        icd10_pattern = re.compile(r'^[A-Z]\d{2}')
        for code in COMMON_ICD10_CODES:
            assert icd10_pattern.match(code), f"Unexpected ICD-10 format: {code}"

    def test_contains_common_respiratory_code(self):
        # J06.9 = Acute upper respiratory infection
        assert "J06.9" in COMMON_ICD10_CODES

    def test_contains_common_diabetes_code(self):
        # E11 family = Type 2 diabetes
        diabetes_codes = [k for k in COMMON_ICD10_CODES if k.startswith("E11")]
        assert len(diabetes_codes) > 0

    def test_contains_hypertension_code(self):
        # I10 = Essential hypertension
        assert "I10" in COMMON_ICD10_CODES

    def test_description_for_hypertension(self):
        assert "hypertension" in COMMON_ICD10_CODES.get("I10", "").lower()

    def test_no_duplicate_values_for_same_code(self):
        # Each code should appear at most once (dict enforces uniqueness)
        assert len(COMMON_ICD10_CODES) == len(set(COMMON_ICD10_CODES.keys()))

    def test_substantial_code_count(self):
        # Should have a meaningful number of codes
        assert len(COMMON_ICD10_CODES) >= 50


# ===========================================================================
# COMMON_ICD9_CODES
# ===========================================================================

class TestCommonIcd9Codes:
    def test_is_dict(self):
        assert isinstance(COMMON_ICD9_CODES, dict)

    def test_is_non_empty(self):
        assert len(COMMON_ICD9_CODES) > 0

    def test_all_keys_are_strings(self):
        for key in COMMON_ICD9_CODES:
            assert isinstance(key, str), f"Non-string key: {key!r}"

    def test_all_values_are_strings(self):
        for code, desc in COMMON_ICD9_CODES.items():
            assert isinstance(desc, str), f"Non-string value for {code}"

    def test_all_values_are_non_empty(self):
        for code, desc in COMMON_ICD9_CODES.items():
            assert desc.strip(), f"Empty description for {code}"

    def test_icd9_keys_are_numeric_based(self):
        # ICD-9 codes are numeric (possibly with decimal and letter suffix like E or V)
        icd9_pattern = re.compile(r'^[0-9VE]\d*')
        for code in COMMON_ICD9_CODES:
            assert icd9_pattern.match(code), f"Unexpected ICD-9 format: {code}"

    def test_contains_common_code(self):
        # 250 family = Diabetes mellitus
        diabetes_codes = [k for k in COMMON_ICD9_CODES if k.startswith("250")]
        assert len(diabetes_codes) > 0

    def test_substantial_code_count(self):
        assert len(COMMON_ICD9_CODES) >= 30

    def test_no_duplicate_keys(self):
        assert len(COMMON_ICD9_CODES) == len(set(COMMON_ICD9_CODES.keys()))
