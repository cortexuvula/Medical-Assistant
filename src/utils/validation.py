"""Input validation utilities for the Medical Assistant application."""

import os
import re
from pathlib import Path
from typing import Optional, Tuple, List
from utils.error_codes import get_error_message
from utils.structured_logging import get_logger

logger = get_logger(__name__)
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_GEMINI,
    STT_DEEPGRAM, STT_ELEVENLABS, STT_GROQ
)

# API key patterns for basic validation
# NOTE: These patterns use flexible length ranges instead of exact lengths to accommodate
# provider format changes. Only prefix validation is strict; length is validated as a range.
API_KEY_PATTERNS = {
    # OpenAI uses various formats including sk-proj-*, sk-*, etc.
    # Minimum 20 chars after prefix, no strict maximum (providers change formats)
    PROVIDER_OPENAI: re.compile(r'^sk-[a-zA-Z0-9\-_]{20,}$'),
    # Deepgram keys are alphanumeric, typically 32+ characters
    STT_DEEPGRAM: re.compile(r'^[a-zA-Z0-9]{32,}$'),
    # ElevenLabs keys start with sk_ followed by alphanumeric characters
    STT_ELEVENLABS: re.compile(r'^sk_[a-zA-Z0-9]{20,}$'),
    # Groq keys start with gsk_ - flexible length (was 52 exact, now 40+)
    STT_GROQ: re.compile(r'^gsk_[a-zA-Z0-9]{40,}$'),
    # Anthropic keys start with sk-ant- - flexible length (was 95+ exact, now 80+)
    PROVIDER_ANTHROPIC: re.compile(r'^sk-ant-[a-zA-Z0-9\-_]{80,}$'),
    # Google Gemini keys start with AIza - typically 39 characters total
    PROVIDER_GEMINI: re.compile(r'^AIza[a-zA-Z0-9\-_]{30,}$'),
}

# Maximum lengths for input validation
MAX_PROMPT_LENGTH = 10000  # Maximum characters for user prompts
MAX_FILE_PATH_LENGTH = 260  # Windows MAX_PATH limitation
MAX_API_KEY_LENGTH = 200  # Reasonable maximum for API keys

# Patterns for sensitive data that should be redacted from logs
SENSITIVE_PATTERNS = [
    # API keys
    (re.compile(r'sk-[a-zA-Z0-9\-_]{10,}'), '[OPENAI_KEY_REDACTED]'),
    (re.compile(r'sk-ant-[a-zA-Z0-9\-_]{10,}'), '[ANTHROPIC_KEY_REDACTED]'),
    (re.compile(r'sk_[a-zA-Z0-9]{10,}'), '[ELEVENLABS_KEY_REDACTED]'),
    (re.compile(r'gsk_[a-zA-Z0-9]{10,}'), '[GROQ_KEY_REDACTED]'),
    # Authorization headers
    (re.compile(r'Bearer\s+[a-zA-Z0-9\-_\.]+', re.IGNORECASE), 'Bearer [TOKEN_REDACTED]'),
    (re.compile(r'Authorization:\s*[^\n]+', re.IGNORECASE), 'Authorization: [REDACTED]'),
    # Email addresses (potential PII)
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
    # Phone numbers (potential PII) - basic patterns
    (re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE_REDACTED]'),
    # SSN patterns (potential PII)
    (re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'), '[SSN_REDACTED]'),
]

# Dangerous patterns to sanitize from prompts
DANGEROUS_PATTERNS = [
    # Injection attempts
    # Updated pattern to match various script tag formats including malformed ones
    re.compile(r'<script[^>]*>.*?</script[^>]*>', re.IGNORECASE | re.DOTALL),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # Event handlers
    # System commands
    re.compile(r';\s*(rm|del|format|shutdown|reboot)', re.IGNORECASE),
    re.compile(r'\$\(.*?\)'),  # Command substitution
    re.compile(r'`.*?`'),  # Backtick command execution
    # Prompt injection attempts - patterns designed to manipulate AI behavior
    re.compile(r'ignore\s+(all\s+)?(previous|prior|above)\s+instructions?', re.IGNORECASE),
    re.compile(r'disregard\s+(all\s+)?(previous|prior|above)', re.IGNORECASE),
    re.compile(r'forget\s+(everything|all|your)\s+(you|instructions?|context)', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+(a|an|the)', re.IGNORECASE),  # Index 9
    re.compile(r'new\s+(system\s+)?instructions?:', re.IGNORECASE),
    re.compile(r'override\s*(:|mode|instructions?)', re.IGNORECASE),
    re.compile(r'pretend\s+(to\s+be|you\s+are)', re.IGNORECASE),
    re.compile(r'act\s+as\s+(if|a|an|the)', re.IGNORECASE),  # Index 13
    re.compile(r'jailbreak', re.IGNORECASE),
    re.compile(r'bypass\s+(safety|security|filter)', re.IGNORECASE),
]

# Medical phrase whitelist for prompt injection patterns
# Maps DANGEROUS_PATTERNS indices to medical phrases that should be allowed
MEDICAL_PHRASE_WHITELIST = {
    13: [  # Index 13: r'act\s+as\s+(if|a|an|the)' pattern
        # Pharmacology - mechanism of action (must match pattern: "act as a/an/the")
        r'\b(?:medication|drug|agent|compound|substance|treatment)\s+(?:can|may|should|will|does|might)\s+act\s+as\s+(?:a|an|the)\b',
        r'\b(?:nitroglycerin|aspirin|warfarin|heparin|metformin|insulin|lisinopril|atorvastatin)\s+(?:can|may|should|will|does|might)\s+act\s+as\s+(?:a|an|the)\b',
        # Therapeutic mechanisms
        r'\b(?:can|may|should|will|does|might)\s+act\s+as\s+(?:a|an|the)\s+(?:vasodilator|bronchodilator|analgesic|anti-inflammatory|antihypertensive|inhibitor|blocker)\b',
        r'\b(?:primary|secondary|alternative)\s+(?:treatment|therapy|medication)\b.*?\bact\s+as\s+(?:a|an|the)\b',
    ],
    9: [  # Index 9: r'you\s+are\s+now\s+(a|an|the)' pattern
        # Post-treatment status (must match pattern: "you are now a/an/the")
        r'\b(?:after|since|following)\s+(?:recovery|treatment|surgery|therapy|discharge)\s+you\s+are\s+now\s+(?:a|an|the)\b',
        r'\byou\s+are\s+now\s+(?:a|an|the)\s+(?:suitable|eligible|qualified)\s+(?:donor|candidate|patient)\b',
        r'\byou\s+are\s+now\s+(?:a|an|the)\s+(?:healthiest|strongest)\b',
    ]
}

# Compiled whitelist patterns (built at module initialization)
_COMPILED_MEDICAL_WHITELIST: dict = {}

def validate_api_key(provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
    """Validate an API key for a specific provider (format validation only).

    NOTE: This function only validates the API key FORMAT, not whether the key
    actually works with the provider's API. Format validation alone cannot detect:
    - Expired keys
    - Revoked keys
    - Keys with insufficient permissions
    - Rate-limited accounts

    RECOMMENDATION: After format validation passes, always perform a live
    connection test using the provider's API to verify the key is actually valid.
    Use `validate_api_key_with_connection_test()` for comprehensive validation.

    Args:
        provider: The API provider name (openai, deepgram, etc.)
        api_key: The API key to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key:
        return False, "API key cannot be empty"

    # Check length
    if len(api_key) > MAX_API_KEY_LENGTH:
        return False, f"API key is too long (max {MAX_API_KEY_LENGTH} characters)"

    # Remove whitespace
    api_key = api_key.strip()

    # Basic format validation for known providers
    if provider.lower() in API_KEY_PATTERNS:
        pattern = API_KEY_PATTERNS[provider.lower()]
        if not pattern.match(api_key):
            return False, f"Invalid {provider} API key format"

    # Check for common mistakes
    if api_key.startswith('"') or api_key.endswith('"'):
        return False, "API key should not include quotes"

    if ' ' in api_key:
        return False, "API key should not contain spaces"

    if api_key == f"<YOUR_{provider.upper()}_API_KEY>" or api_key.startswith("<") or api_key.endswith(">"):
        return False, "Please replace the placeholder with your actual API key"

    return True, None


class APIKeyValidationResult:
    """Result of API key validation including format check and optional connection test."""

    def __init__(
        self,
        is_valid: bool,
        format_valid: bool,
        connection_tested: bool = False,
        connection_success: bool = False,
        error_message: Optional[str] = None,
        recommendation: Optional[str] = None
    ):
        self.is_valid = is_valid
        self.format_valid = format_valid
        self.connection_tested = connection_tested
        self.connection_success = connection_success
        self.error_message = error_message
        self.recommendation = recommendation


def validate_api_key_comprehensive(
    provider: str,
    api_key: str,
    test_connection: bool = False,
    connection_tester: Optional[callable] = None
) -> APIKeyValidationResult:
    """Comprehensive API key validation with optional connection testing.

    This function provides complete validation including:
    1. Format validation (pattern matching)
    2. Common mistake detection
    3. Optional live connection testing

    Args:
        provider: The API provider name (openai, deepgram, etc.)
        api_key: The API key to validate
        test_connection: If True, also test the API connection
        connection_tester: Optional callable that takes (provider, api_key) and
                          returns (success: bool, error: Optional[str]).
                          If not provided, connection testing is skipped.

    Returns:
        APIKeyValidationResult with detailed validation information

    Example:
        # Format validation only
        result = validate_api_key_comprehensive("openai", "sk-...")

        # With connection testing
        def test_openai(provider, key):
            try:
                # Call OpenAI API with minimal request
                return True, None
            except Exception as e:
                return False, str(e)

        result = validate_api_key_comprehensive(
            "openai", "sk-...",
            test_connection=True,
            connection_tester=test_openai
        )
    """
    # First, validate format
    format_valid, format_error = validate_api_key(provider, api_key)

    if not format_valid:
        return APIKeyValidationResult(
            is_valid=False,
            format_valid=False,
            error_message=format_error,
            recommendation="Please check the API key format and try again."
        )

    # Format is valid - check if connection testing is requested
    if not test_connection or connection_tester is None:
        return APIKeyValidationResult(
            is_valid=True,  # Provisionally valid based on format
            format_valid=True,
            connection_tested=False,
            recommendation=(
                "API key format is valid. For complete validation, test the "
                "connection using the 'Test Connection' button in Settings."
            )
        )

    # Perform connection test
    try:
        connection_success, connection_error = connection_tester(provider, api_key)

        if connection_success:
            return APIKeyValidationResult(
                is_valid=True,
                format_valid=True,
                connection_tested=True,
                connection_success=True
            )
        else:
            return APIKeyValidationResult(
                is_valid=False,
                format_valid=True,
                connection_tested=True,
                connection_success=False,
                error_message=f"Connection test failed: {connection_error}",
                recommendation=(
                    "The API key format is correct but the connection test failed. "
                    "Please verify: 1) The key is active and not expired, "
                    "2) Your account has the required permissions, "
                    "3) You have not exceeded rate limits."
                )
            )
    except Exception as e:
        return APIKeyValidationResult(
            is_valid=False,
            format_valid=True,
            connection_tested=True,
            connection_success=False,
            error_message=f"Connection test error: {str(e)}",
            recommendation="An unexpected error occurred during connection testing."
        )


def sanitize_for_logging(text: str, max_length: int = 500) -> str:
    """Sanitize text for safe logging by removing sensitive data.

    Args:
        text: The text to sanitize
        max_length: Maximum length of output (default 500)

    Returns:
        Sanitized text safe for logging
    """
    if not text:
        return ""

    # Apply all sensitive patterns
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "...[TRUNCATED]"

    return sanitized


def _build_medical_whitelist():
    """Build compiled regex patterns from medical whitelist."""
    global _COMPILED_MEDICAL_WHITELIST
    for pattern_idx, phrases in MEDICAL_PHRASE_WHITELIST.items():
        _COMPILED_MEDICAL_WHITELIST[pattern_idx] = [
            re.compile(phrase, re.IGNORECASE) for phrase in phrases
        ]


# Initialize at module load
_build_medical_whitelist()


def _is_likely_medical_text(text: str) -> bool:
    """Quick heuristic to detect if text is likely medical content.

    Uses fast pattern matching on common medical indicators from
    the medical_ner.py dictionaries (medications, conditions, units, vitals).

    Args:
        text: Input text to check

    Returns:
        True if text appears to contain medical terminology
    """
    # Quick check: look for medical indicators
    medical_indicators = [
        # Common medications from medical_ner.py (expanded)
        r'\b(?:aspirin|lisinopril|metformin|atorvastatin|warfarin|insulin|nitroglycerin|heparin)\b',
        # Common conditions
        r'\b(?:hypertension|diabetes|asthma|copd|pneumonia|chf|cardiac)\b',
        # Medical units and abbreviations
        r'\b(?:mg|mcg|ml|bpm|mmHg|po|iv|bid|tid|qid)\b',
        # Vital signs
        r'\b(?:bp|hr|temp|spo2|glucose|weight)\b',
        # Medical procedures
        r'\b(?:ecg|ekg|mri|ct\s+scan|x-ray|surgery|treatment|therapy)\b',
        # Medical roles and settings
        r'\b(?:patient|donor|organ|recovery|cardiac|antihypertensive|vasodilator)\b',
    ]

    # Compile on first use (cached in function)
    if not hasattr(_is_likely_medical_text, '_pattern'):
        _is_likely_medical_text._pattern = re.compile(
            '|'.join(medical_indicators),
            re.IGNORECASE
        )

    return bool(_is_likely_medical_text._pattern.search(text))


def _check_medical_whitelist(text: str, pattern_idx: int, match_obj: re.Match) -> bool:
    """Check if a dangerous pattern match is actually a whitelisted medical phrase.

    Args:
        text: Full text being sanitized
        pattern_idx: Index of the dangerous pattern in DANGEROUS_PATTERNS
        match_obj: The regex match object

    Returns:
        True if match should be allowed (is whitelisted), False otherwise
    """
    # No whitelist for this pattern
    if pattern_idx not in _COMPILED_MEDICAL_WHITELIST:
        return False

    # Get context around the match (±50 chars for efficiency)
    start = max(0, match_obj.start() - 50)
    end = min(len(text), match_obj.end() + 50)
    context = text[start:end]

    # Check each whitelisted phrase
    for whitelist_pattern in _COMPILED_MEDICAL_WHITELIST[pattern_idx]:
        if whitelist_pattern.search(context):
            logger.debug(
                f"Medical phrase whitelist: allowed pattern at position {match_obj.start()}"
            )
            return True

    return False


class PromptInjectionError(ValueError):
    """Raised when a prompt injection attempt is detected in strict mode."""
    pass


def sanitize_prompt(prompt: str, strict_mode: bool = False) -> str:
    """Sanitize user prompt before sending to API.

    Args:
        prompt: The user's input prompt
        strict_mode: If True, reject prompts with dangerous content instead of sanitizing.
                     Use strict_mode=True for untrusted external input.
                     Note: Medical whitelist is disabled in strict mode for security.

    Returns:
        Sanitized prompt safe for API calls

    Raises:
        PromptInjectionError: If strict_mode=True and dangerous patterns are detected
    """
    if not prompt:
        return ""

    # Truncate if too long
    if len(prompt) > MAX_PROMPT_LENGTH:
        logger.warning(f"Prompt truncated from {len(prompt)} to {MAX_PROMPT_LENGTH} characters")
        prompt = prompt[:MAX_PROMPT_LENGTH] + "..."

    # Detect medical context for whitelist application (only in normal mode)
    is_medical_context = False
    if not strict_mode:
        is_medical_context = _is_likely_medical_text(prompt)

    # Check for dangerous patterns and build whitelist exceptions
    detected_patterns = []
    whitelisted_matches = {}  # Maps pattern_idx -> list of Match objects to preserve

    for pattern_idx, pattern in enumerate(DANGEROUS_PATTERNS):
        matches = list(pattern.finditer(prompt))
        if matches:
            # Track detected pattern
            detected_patterns.append(pattern.pattern[:50])

            # Check whitelist for each match in medical context (normal mode only)
            if is_medical_context and not strict_mode:
                whitelisted = []
                for match in matches:
                    if _check_medical_whitelist(prompt, pattern_idx, match):
                        whitelisted.append(match)

                if whitelisted:
                    whitelisted_matches[pattern_idx] = whitelisted

    if detected_patterns:
        if strict_mode:
            # In strict mode, reject the entire prompt (no whitelist)
            logger.warning(
                f"Prompt injection attempt blocked (strict mode): {len(detected_patterns)} patterns detected"
            )
            # Log to audit if available
            try:
                from utils.audit_logger import audit_log, AuditEventType
                audit_log(
                    event_type=AuditEventType.SECURITY_WARNING,
                    action="prompt_injection_blocked",
                    outcome="warning",
                    details={"patterns_detected": len(detected_patterns)}
                )
            except ImportError:
                pass  # Audit logger not available
            raise PromptInjectionError(
                "Input contains potentially dangerous content and has been rejected. "
                "Please remove any instruction-like text and try again."
            )
        else:
            # In normal mode, sanitize by removing dangerous patterns
            # but preserve whitelisted medical phrases
            removed_count = 0
            whitelisted_count = 0

            for pattern_idx, pattern in enumerate(DANGEROUS_PATTERNS):
                whitelisted_for_pattern = whitelisted_matches.get(pattern_idx, [])

                if whitelisted_for_pattern:
                    # Build a set of whitelisted spans to preserve
                    whitelisted_spans = {(m.start(), m.end()) for m in whitelisted_for_pattern}

                    # Replace only non-whitelisted matches
                    def replacement_func(match):
                        nonlocal removed_count, whitelisted_count
                        if (match.start(), match.end()) in whitelisted_spans:
                            whitelisted_count += 1
                            return match.group(0)  # Preserve whitelisted match
                        else:
                            removed_count += 1
                            return ''  # Remove non-whitelisted match

                    prompt = pattern.sub(replacement_func, prompt)
                else:
                    # No whitelist for this pattern, remove all matches
                    matches_found = len(pattern.findall(prompt))
                    removed_count += matches_found
                    prompt = pattern.sub('', prompt)

            # Log sanitization results
            if whitelisted_count > 0:
                logger.info(
                    f"Sanitization: removed {removed_count} patterns, whitelisted {whitelisted_count} medical phrases"
                )
            else:
                logger.warning(
                    f"Potentially dangerous content removed from prompt: {removed_count} patterns"
                )

    # Remove excessive whitespace
    prompt = ' '.join(prompt.split())

    # Remove null bytes and other problematic characters
    prompt = prompt.replace('\x00', '').replace('\r', '\n')

    # Ensure the prompt is valid UTF-8
    try:
        prompt.encode('utf-8')
    except UnicodeEncodeError:
        # Remove non-UTF-8 characters
        prompt = prompt.encode('utf-8', 'ignore').decode('utf-8')
        logger.warning("Non-UTF-8 characters removed from prompt")

    return prompt.strip()


def validate_prompt_safety(prompt: str) -> tuple[bool, Optional[str]]:
    """Check if a prompt contains potentially dangerous content.

    This is a non-throwing alternative to strict_mode for cases where you
    want to check before processing.

    Args:
        prompt: The prompt to validate

    Returns:
        Tuple of (is_safe, warning_message)
    """
    if not prompt:
        return True, None

    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(prompt):
            return False, "Prompt contains potentially dangerous content that may attempt to manipulate AI behavior"

    return True, None


# Maximum device name length for validation
MAX_DEVICE_NAME_LENGTH = 256


def sanitize_device_name(device_name: str) -> str:
    """Sanitize device name for safe use in logging and matching.

    Prevents log injection and ensures device name is safe for comparison.

    Args:
        device_name: The device name to sanitize

    Returns:
        Sanitized device name
    """
    if not device_name:
        return ""

    # Truncate to reasonable length
    if len(device_name) > MAX_DEVICE_NAME_LENGTH:
        device_name = device_name[:MAX_DEVICE_NAME_LENGTH]

    # Remove control characters and newlines (prevent log injection)
    device_name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', device_name)

    # Remove any characters that could be used for log injection
    device_name = device_name.replace('\n', ' ').replace('\r', ' ')

    # Ensure valid UTF-8
    try:
        device_name.encode('utf-8')
    except UnicodeEncodeError:
        device_name = device_name.encode('utf-8', 'ignore').decode('utf-8')

    return device_name.strip()


def validate_file_path(
    file_path: str,
    must_exist: bool = False,
    must_be_writable: bool = False,
    base_directory: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Validate a file path for safety and accessibility.

    Args:
        file_path: The file path to validate
        must_exist: Whether the file must already exist
        must_be_writable: Whether we need write access to the file/directory
        base_directory: If provided, the resolved path must be within this directory.
                        This prevents path traversal attacks.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "File path cannot be empty"

    # Check length
    if len(file_path) > MAX_FILE_PATH_LENGTH:
        return False, f"File path too long (max {MAX_FILE_PATH_LENGTH} characters)"

    # Check for null bytes (can be used to truncate paths)
    if '\x00' in file_path:
        return False, "File path cannot contain null bytes"

    try:
        # Resolve to absolute path first (this handles .., symlinks, etc.)
        path = Path(file_path).resolve()

        # Security check: if base_directory provided, ensure resolved path is within it
        # This check happens AFTER resolve() to prevent encoded path traversal
        if base_directory:
            base_path = Path(base_directory).resolve()
            try:
                # Python 3.9+ has is_relative_to
                if hasattr(path, 'is_relative_to'):
                    if not path.is_relative_to(base_path):
                        logger.warning(f"Path traversal attempt blocked: {file_path} resolved outside {base_directory}")
                        return False, "File path attempts to access location outside allowed directory"
                else:
                    # Fallback for Python 3.8
                    try:
                        path.relative_to(base_path)
                    except ValueError:
                        logger.warning(f"Path traversal attempt blocked: {file_path} resolved outside {base_directory}")
                        return False, "File path attempts to access location outside allowed directory"
            except Exception:
                return False, "Could not validate path containment"

        # Even without base_directory, warn about ".." in original path (might be intentional)
        # But still allow if it resolves to a valid location
        if ".." in file_path:
            logger.debug(f"Path contains '..', resolved to: {path}")

        # Check if path exists when required
        if must_exist and not path.exists():
            return False, f"File does not exist: {file_path}"

        # Check write permissions
        if must_be_writable:
            if path.exists():
                if not os.access(path, os.W_OK):
                    return False, f"No write permission for: {file_path}"
            else:
                # Check parent directory for write permission
                parent = path.parent
                if not parent.exists():
                    return False, f"Parent directory does not exist: {parent}"
                if not os.access(parent, os.W_OK):
                    return False, f"No write permission in directory: {parent}"

        # Check for dangerous file names (Windows reserved names)
        dangerous_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                          'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                          'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']

        base_name = path.stem.upper()
        if base_name in dangerous_names:
            return False, f"Reserved file name not allowed: {path.stem}"

        return True, None

    except Exception as e:
        return False, f"Invalid file path: {str(e)}"

def validate_audio_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """Validate an audio file path.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # First do general file validation
    is_valid, error = validate_file_path(file_path, must_exist=True)
    if not is_valid:
        return False, error
    
    # Check file extension
    valid_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.webm'}
    path = Path(file_path)
    if path.suffix.lower() not in valid_extensions:
        return False, f"Unsupported audio format: {path.suffix}"
    
    # Check file size (limit to 100MB for safety)
    max_size = 100 * 1024 * 1024  # 100MB
    if path.stat().st_size > max_size:
        return False, f"Audio file too large (max 100MB)"
    
    return True, None

def validate_model_name(model_name: str, provider: str) -> Tuple[bool, Optional[str]]:
    """Validate a model name for a specific provider.
    
    Args:
        model_name: The model name to validate
        provider: The API provider
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not model_name:
        return False, "Model name cannot be empty"
    
    # Basic validation
    if len(model_name) > 100:
        return False, "Model name too long"
    
    # Provider-specific validation
    if provider.lower() == "openai":
        valid_prefixes = ['gpt-3.5', 'gpt-4', 'text-', 'davinci', 'curie', 'babbage', 'ada']
        if not any(model_name.startswith(prefix) for prefix in valid_prefixes):
            logger.warning(f"Unusual OpenAI model name: {model_name}")
    
    elif provider.lower() == "ollama":
        # Ollama models should not contain special characters
        if not re.match(r'^[a-zA-Z0-9_\-:\.]+$', model_name):
            return False, "Invalid Ollama model name format"
    
    return True, None

def validate_temperature(temperature: float) -> Tuple[bool, Optional[str]]:
    """Validate temperature parameter for AI models.
    
    Args:
        temperature: The temperature value
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        temp = float(temperature)
        if temp < 0.0 or temp > 2.0:
            return False, "Temperature must be between 0.0 and 2.0"
        return True, None
    except (ValueError, TypeError):
        return False, "Temperature must be a number"

def validate_export_path(directory: str) -> Tuple[bool, Optional[str]]:
    """Validate a directory path for exporting files.
    
    Args:
        directory: The directory path to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_file_path(directory, must_exist=True, must_be_writable=True)
    if not is_valid:
        return False, error
    
    path = Path(directory)
    if not path.is_dir():
        return False, "Path must be a directory, not a file"
    
    return True, None

def safe_filename(filename: str, max_length: int = 255) -> str:
    """Convert a string into a safe filename.
    
    Args:
        filename: The desired filename
        max_length: Maximum length for the filename
        
    Returns:
        A sanitized filename safe for the filesystem
    """
    # Remove invalid characters
    safe_chars = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters
    safe_chars = ''.join(char for char in safe_chars if ord(char) >= 32)
    
    # Remove leading/trailing dots and spaces
    safe_chars = safe_chars.strip('. ')
    
    # Ensure it's not empty
    if not safe_chars:
        safe_chars = "unnamed"
    
    # Truncate if too long
    if len(safe_chars) > max_length:
        safe_chars = safe_chars[:max_length]

    return safe_chars


def validate_path_for_subprocess(path: str, must_exist: bool = True) -> Tuple[bool, Optional[str]]:
    """Validate a file or directory path before passing to subprocess.

    This function performs security checks to prevent command injection
    and path traversal attacks when opening files/folders via subprocess.

    Args:
        path: The file or directory path to validate
        must_exist: Whether the path must exist (default True)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Path cannot be empty"

    # Check for null bytes (can be used for injection)
    if '\x00' in path:
        logger.warning(f"Null byte detected in path: {repr(path)}")
        return False, "Invalid path: contains null byte"

    # Check for shell metacharacters that could be exploited
    # These are dangerous in shell contexts
    dangerous_chars = ['|', '&', ';', '$', '`', '(', ')', '{', '}', '[', ']',
                       '<', '>', '\n', '\r', '!', '#']
    for char in dangerous_chars:
        if char in path:
            logger.warning(f"Dangerous character '{char}' in path: {path}")
            return False, f"Invalid path: contains dangerous character '{char}'"

    try:
        # Resolve to absolute path and normalize
        resolved_path = Path(path).resolve()

        # Check path length
        if len(str(resolved_path)) > MAX_FILE_PATH_LENGTH:
            return False, f"Path too long (max {MAX_FILE_PATH_LENGTH} characters)"

        # Check for path traversal attempts
        # After resolving, the path should not escape expected locations
        if ".." in path:
            # Log but allow if resolved path is valid
            logger.debug(f"Path contains '..', resolved to: {resolved_path}")

        # Check existence if required
        if must_exist and not resolved_path.exists():
            return False, f"Path does not exist: {path}"

        # Verify it's a real path (not a symlink pointing outside allowed areas)
        # This is a basic check - can be enhanced based on security requirements
        if resolved_path.is_symlink():
            target = resolved_path.resolve()
            logger.debug(f"Symlink {path} -> {target}")

        return True, None

    except (OSError, ValueError) as e:
        return False, f"Invalid path: {str(e)}"


def open_file_or_folder_safely(path: str, operation: str = "open") -> Tuple[bool, Optional[str]]:
    """Safely open a file or folder using the system's default application.

    This function validates the path and uses the appropriate system
    command to open files/folders safely.

    Args:
        path: The file or directory path to open
        operation: The operation type - "open" or "print"

    Returns:
        Tuple of (success, error_message)
    """
    import platform
    import subprocess
    import shlex

    # Validate the path first
    is_valid, error = validate_path_for_subprocess(path, must_exist=True)
    if not is_valid:
        logger.error(f"Path validation failed: {error}")
        return False, error

    try:
        # Resolve to absolute path
        resolved_path = str(Path(path).resolve())
        system = platform.system()

        if system == 'Windows':
            # Windows: use os.startfile which is safe
            if operation == "print":
                os.startfile(resolved_path, "print")
            else:
                os.startfile(resolved_path)

        elif system == 'Darwin':  # macOS
            # macOS: use 'open' command with proper argument handling
            if operation == "print":
                # Use lpr for printing
                subprocess.run(['lpr', resolved_path], check=True)
            else:
                subprocess.run(['open', resolved_path], check=True)

        else:  # Linux and other Unix-like systems
            if operation == "print":
                subprocess.run(['lpr', resolved_path], check=True)
            else:
                subprocess.run(['xdg-open', resolved_path], check=True)

        return True, None

    except FileNotFoundError as e:
        error_msg = f"System command not found: {e}"
        logger.error(error_msg)
        return False, error_msg
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to {operation} path: {e}"
        logger.error(error_msg)
        return False, error_msg
    except OSError as e:
        error_msg = f"OS error opening path: {e}"
        logger.error(error_msg)
        return False, error_msg