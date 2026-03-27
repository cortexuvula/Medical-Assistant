"""
ICD Code Validator

Validates ICD-9 and ICD-10 diagnostic codes with pattern matching and
common code lookup. Supports both code systems as requested.

Usage:
    validator = ICDValidator()
    result = validator.validate("J06.9")  # Common cold, ICD-10
    if result.is_valid:
        print(f"Valid {result.code_system}: {result.description}")
"""

import re
from typing import Optional, List, Dict
from dataclasses import dataclass
from enum import Enum

from utils.icd_code_data import COMMON_ICD10_CODES, COMMON_ICD9_CODES
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ICDCodeSystem(Enum):
    """Supported ICD code systems."""
    ICD9 = "ICD-9"
    ICD10 = "ICD-10"
    UNKNOWN = "Unknown"


@dataclass
class ICDValidationResult:
    """Result of ICD code validation."""
    code: str
    is_valid: bool
    code_system: ICDCodeSystem
    description: Optional[str] = None
    warning: Optional[str] = None
    suggested_code: Optional[str] = None


# ICD-10 pattern: Letter followed by 2 digits, optional decimal and more digits
# Example: J06.9, E11.65, M54.5
ICD10_PATTERN = re.compile(r'^[A-Z]\d{2}(\.\d{1,4})?$', re.IGNORECASE)

# ICD-9 pattern: 3-5 digits with optional decimal after 3rd digit
# Example: 250.00, 401.9, 780.79
ICD9_PATTERN = re.compile(r'^\d{3}(\.\d{1,2})?$')

# E-codes (external causes) for ICD-9: E followed by 3-4 digits
ICD9_ECODE_PATTERN = re.compile(r'^E\d{3}(\.\d)?$', re.IGNORECASE)

# V-codes (supplementary classification) for ICD-9: V followed by 2 digits
ICD9_VCODE_PATTERN = re.compile(r'^V\d{2}(\.\d{1,2})?$', re.IGNORECASE)


class ICDValidator:
    """
    Validates ICD-9 and ICD-10 diagnostic codes.

    Supports:
    - Pattern-based format validation
    - Common code lookup with descriptions
    - Flexible code normalization

    Example:
        validator = ICDValidator()

        # Validate a code
        result = validator.validate("J06.9")
        print(result.is_valid)  # True
        print(result.code_system)  # ICDCodeSystem.ICD10
        print(result.description)  # "Acute upper respiratory infection, unspecified"

        # Validate multiple codes
        results = validator.validate_batch(["J06.9", "250.00", "INVALID"])
    """

    def __init__(
        self,
        icd10_codes: Optional[Dict[str, str]] = None,
        icd9_codes: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the validator.

        Args:
            icd10_codes: Optional custom ICD-10 code dictionary
            icd9_codes: Optional custom ICD-9 code dictionary
        """
        self.icd10_codes = icd10_codes or COMMON_ICD10_CODES
        self.icd9_codes = icd9_codes or COMMON_ICD9_CODES

    def validate(self, code: str) -> ICDValidationResult:
        """
        Validate an ICD code and return detailed result.

        Args:
            code: The ICD code to validate

        Returns:
            ICDValidationResult with validation status and details
        """
        if not code:
            return ICDValidationResult(
                code=code,
                is_valid=False,
                code_system=ICDCodeSystem.UNKNOWN,
                warning="Empty code provided"
            )

        # Normalize the code
        normalized = self._normalize_code(code)

        # Determine code system and validate format
        code_system = self._detect_code_system(normalized)

        if code_system == ICDCodeSystem.UNKNOWN:
            return ICDValidationResult(
                code=code,
                is_valid=False,
                code_system=ICDCodeSystem.UNKNOWN,
                warning="Invalid ICD code format"
            )

        # Look up description
        description = self._lookup_description(normalized, code_system)

        # Check if it's a known valid code
        is_known = description is not None

        # Even if not in our lookup table, format-valid codes might be correct
        # We'll mark them as valid but with a warning
        result = ICDValidationResult(
            code=normalized,
            is_valid=True,  # Format is valid
            code_system=code_system,
            description=description
        )

        if not is_known:
            result.warning = (
                f"Code {normalized} has valid {code_system.value} format but is not in "
                "the common codes database. Please verify with official ICD reference."
            )

        return result

    def validate_batch(self, codes: List[str]) -> List[ICDValidationResult]:
        """
        Validate multiple ICD codes.

        Args:
            codes: List of ICD codes to validate

        Returns:
            List of ICDValidationResult objects
        """
        return [self.validate(code) for code in codes]

    def is_valid_format(self, code: str) -> bool:
        """
        Quick check if code has valid ICD format.

        Args:
            code: The ICD code to check

        Returns:
            True if format is valid for either ICD-9 or ICD-10
        """
        normalized = self._normalize_code(code)
        return self._detect_code_system(normalized) != ICDCodeSystem.UNKNOWN

    def get_description(self, code: str) -> Optional[str]:
        """
        Get description for an ICD code if available.

        Args:
            code: The ICD code

        Returns:
            Description string or None if not found
        """
        normalized = self._normalize_code(code)
        code_system = self._detect_code_system(normalized)
        return self._lookup_description(normalized, code_system)

    def suggest_similar_codes(self, code: str, limit: int = 5) -> List[str]:
        """
        Suggest similar valid codes for a potentially incorrect code.

        Args:
            code: The code to find similar codes for
            limit: Maximum number of suggestions

        Returns:
            List of similar code suggestions
        """
        normalized = self._normalize_code(code)
        suggestions = []

        # Determine likely code system
        code_system = self._detect_code_system(normalized)

        if code_system == ICDCodeSystem.ICD10 or normalized[0].isalpha():
            # Search ICD-10 codes
            prefix = normalized[:3] if len(normalized) >= 3 else normalized
            for valid_code in self.icd10_codes.keys():
                if valid_code.startswith(prefix):
                    suggestions.append(valid_code)
                    if len(suggestions) >= limit:
                        break
        else:
            # Search ICD-9 codes
            prefix = normalized[:3] if len(normalized) >= 3 else normalized
            for valid_code in self.icd9_codes.keys():
                if valid_code.startswith(prefix):
                    suggestions.append(valid_code)
                    if len(suggestions) >= limit:
                        break

        return suggestions

    def _normalize_code(self, code: str) -> str:
        """Normalize an ICD code for consistent processing."""
        # Remove extra whitespace
        normalized = code.strip()

        # Uppercase letters (ICD-10 codes use uppercase)
        normalized = normalized.upper()

        # Remove common prefixes if present
        for prefix in ["ICD-10:", "ICD-9:", "ICD10:", "ICD9:", "ICD:"]:
            if normalized.upper().startswith(prefix.upper()):
                normalized = normalized[len(prefix):].strip()

        return normalized

    def _detect_code_system(self, code: str) -> ICDCodeSystem:
        """Detect which ICD code system a code belongs to."""
        if not code:
            return ICDCodeSystem.UNKNOWN

        # ICD-10: Starts with letter
        if ICD10_PATTERN.match(code):
            return ICDCodeSystem.ICD10

        # ICD-9: Numeric only
        if ICD9_PATTERN.match(code):
            return ICDCodeSystem.ICD9

        # ICD-9 E-codes (external causes)
        if ICD9_ECODE_PATTERN.match(code):
            return ICDCodeSystem.ICD9

        # ICD-9 V-codes (supplementary classification)
        if ICD9_VCODE_PATTERN.match(code):
            return ICDCodeSystem.ICD9

        return ICDCodeSystem.UNKNOWN

    def _lookup_description(
        self,
        code: str,
        code_system: ICDCodeSystem
    ) -> Optional[str]:
        """Look up description for a code in the appropriate database."""
        if code_system == ICDCodeSystem.ICD10:
            return self.icd10_codes.get(code)
        elif code_system == ICDCodeSystem.ICD9:
            return self.icd9_codes.get(code)
        return None


def extract_icd_codes(text: str) -> List[str]:
    """
    Extract potential ICD codes from text.

    Args:
        text: Text that may contain ICD codes

    Returns:
        List of potential ICD codes found
    """
    codes = []

    # ICD-10 pattern in text
    icd10_matches = re.findall(r'[A-Z]\d{2}(?:\.\d{1,4})?', text, re.IGNORECASE)
    codes.extend(icd10_matches)

    # ICD-9 pattern in text (3 digits, optional decimal)
    icd9_matches = re.findall(r'\b\d{3}(?:\.\d{1,2})?\b', text)
    codes.extend(icd9_matches)

    # Remove duplicates while preserving order
    seen = set()
    unique_codes = []
    for code in codes:
        upper_code = code.upper()
        if upper_code not in seen:
            seen.add(upper_code)
            unique_codes.append(upper_code)

    return unique_codes


# Module-level validator instance for convenience
_default_validator: Optional[ICDValidator] = None


def get_validator() -> ICDValidator:
    """Get the default ICD validator instance."""
    global _default_validator
    if _default_validator is None:
        _default_validator = ICDValidator()
    return _default_validator


def validate_code(code: str) -> ICDValidationResult:
    """Convenience function to validate a single code."""
    return get_validator().validate(code)


def validate_codes(codes: List[str]) -> List[ICDValidationResult]:
    """Convenience function to validate multiple codes."""
    return get_validator().validate_batch(codes)
