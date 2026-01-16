# Technical Debt Backlog

This document tracks architectural improvements and technical debt items for the Medical Assistant codebase. Items are prioritized by impact and effort.

## Priority Levels

- **P1 (High)**: Impacts reliability, security, or causes frequent bugs
- **P2 (Medium)**: Improves maintainability and developer experience
- **P3 (Low)**: Nice-to-have improvements, cleanup

---

## 1. Error Handling Adoption

### Issue
Excellent error handling infrastructure exists but is underutilized. Most code uses basic patterns instead of the rich utilities available.

### Available Infrastructure (USE THESE)
- `OperationResult[T]` - Type-safe result wrapper (`src/utils/error_handling.py`)
- `ErrorContext` - Captures operation context for debugging (`src/utils/error_handling.py`)
- `@handle_errors` decorator - Consistent error handling (`src/utils/error_handling.py`)
- `ErrorMessageMapper` - User-friendly error messages (`src/utils/error_registry.py`)
- `structured_logging` - Rich context logging (`src/utils/structured_logging.py`)

### Files Needing Updates

| File | Issue | Priority | Status |
|------|-------|----------|--------|
| `src/processing/processing_queue.py` | 26+ bare `except Exception` catches | P1 | ✅ Fixed - Uses ErrorContext, specific exceptions |
| `src/translation/deep_translator_provider.py` | Multiple broad Exception catches | P2 | ✅ Fixed - Uses ErrorContext |
| `src/ui/dialogs/*.py` | Many files use `messagebox.showerror()` directly | P2 | Pending |
| `src/audio/audio.py` | Some silently swallowed errors | P2 | ✅ Fixed - Uses ErrorContext |
| `src/database/database.py` | Migration errors not always re-raised | P2 | ✅ Fixed - Uses ErrorContext, documented design |

### Pattern to Follow
```python
# BEFORE (common in codebase):
try:
    result = some_operation()
except Exception as e:
    logging.error(f"Error: {e}")
    return None

# AFTER (use infrastructure):
from utils.error_handling import ErrorContext, OperationResult
from utils.exceptions import APIError, TranscriptionError

try:
    result = some_operation()
    return OperationResult.success(result)
except (APIError, TranscriptionError) as e:
    ctx = ErrorContext.capture(
        operation="some_operation",
        exception=e,
        input_summary=f"Input length: {len(data)}"
    )
    logger.error(ctx.to_log_string())
    return OperationResult.failure(ctx.user_message, error_code=e.error_code)
except Exception as e:
    # Unexpected errors should be logged and re-raised
    logger.error("Unexpected error", exc_info=True)
    raise
```

---

## 2. Return Type Standardization

### Issue
Functions inconsistently return `OperationResult`, `AIResult`, dicts, strings, or throw exceptions. Callers must handle multiple patterns.

### Current State
```python
# Pattern 1: OperationResult (good) - for high-level operations
def refine_text(self) -> OperationResult[Dict]: ...

# Pattern 2: AIResult (good) - for AI provider calls
def call_ai() -> AIResult: ...
# Use result.text for content, result.is_success to check status
# str(result) provides backward compatibility

# Pattern 3: Dict (legacy) - avoid in new code
return {"success": False, "error": "..."}

# Pattern 4: Raise exception - for unrecoverable errors
raise TranscriptionError("Failed")
```

### Recommendation
- `OperationResult[T]` for high-level operations with complex return data
- `AIResult` for AI provider calls (already implemented)
- Exceptions for unrecoverable errors

### Files Status

| File | Current Pattern | Priority | Status |
|------|-----------------|----------|--------|
| `src/ai/ai_processor.py` | OperationResult | P2 | ✅ Already standardized |
| `src/ai/providers/openai_provider.py` | AIResult | P2 | ✅ Updated |
| `src/ai/providers/anthropic_provider.py` | AIResult | P2 | ✅ Updated |
| `src/ai/providers/gemini_provider.py` | AIResult | P2 | ✅ Updated |
| `src/ai/providers/ollama_provider.py` | AIResult | P2 | ✅ Updated |
| `src/ai/providers/router.py` | AIResult | P2 | ✅ Updated |
| `src/ai/letter_generation.py` | Uses AIResult.text | P2 | ✅ Updated |
| `src/processing/document_generators.py` | Via AIResult | P2 | ✅ Inherited |
| `src/managers/*.py` | Various return styles | P3 | Pending |

---

## 3. Logging Standardization

### Issue
Structured logging module exists but most files use basic `logging.error(str(e))`.

### Available Infrastructure
```python
from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Rich context logging
logger.error(
    "Operation failed",
    operation="generate_soap",
    recording_id=123,
    duration_ms=1500,
    error_code="AI_TIMEOUT"
)
```

### Files Using Basic Logging (Sample)

| File | Lines with basic logging | Priority | Status |
|------|-------------------------|----------|--------|
| `src/processing/processing_queue.py` | ~67 | P2 | ✅ Fixed - Uses structured logger with context |
| `src/ai/ai_processor.py` | ~10 | P2 | ✅ Fixed - Uses structured logger with context |
| `src/audio/recording_manager.py` | ~18 | P3 | ✅ Fixed - Uses structured logger with context |
| `src/database/database.py` | ~12 | P3 | Pending |

### Migration Strategy
1. Replace `import logging` with `from utils.structured_logging import get_logger`
2. Replace `logging.getLogger(__name__)` with `get_logger(__name__)`
3. Add context parameters to log calls

---

## 4. Settings Access Patterns

### Issue
`SettingsManager` provides typed accessors but most code directly accesses `SETTINGS[...]` dict.

### Current State
```python
# Common pattern (direct access):
provider = SETTINGS.get("ai_provider", "openai")
temperature = SETTINGS.get("soap_note", {}).get("temperature", 0.4)

# Available but unused:
from settings.settings_manager import SettingsManager
manager = SettingsManager()
provider = manager.get_ai_provider()
temperature = manager.get_nested("soap_note.temperature", 0.4)
```

### Recommendation
For new code, prefer `SettingsManager` typed accessors. Gradual migration for existing code.

### Priority: P3 (Low impact, high effort)

---

## 5. Large File Refactoring

### Issue
Some files are too large, making them hard to navigate and maintain.

### Files Over 500 Lines

| File | Lines | Suggestion | Priority |
|------|-------|------------|----------|
| `src/core/app.py` | ~1100 | Further mixin extraction | P3 |
| `src/ui/workflow_ui.py` | ~800 | Split by tab/concern | P3 |
| `src/processing/processing_queue.py` | ~600 | Extract batch processing | P3 |
| `src/settings/settings.py` | ~700 | Already improved, acceptable | - |

### Note
`app.py` already uses mixins. Further splitting may introduce complexity without benefit. Monitor but don't force.

---

## 6. Resilience Pattern Expansion

### Issue
Excellent resilience decorators exist but only applied to some providers.

### Current Coverage
- `@resilient_api_call`: Applied to Deepgram, OpenAI, Anthropic, Gemini providers
- `@smart_retry`: Available but underused
- `CircuitBreaker`: Available but underused

### Expansion Opportunities

| Component | Current | Suggested | Priority |
|-----------|---------|-----------|----------|
| Translation API calls | No retry | Add `@smart_retry` | P2 |
| Database operations | Basic `@db_retry` | Add circuit breaker for persistent failures | P3 |
| HTTP fetches (RAG, webhooks) | No retry | Add `@network_retry` | P2 |

---

## 7. Test Infrastructure

### Issue
Tests exist but pytest not installed in current environment. Test coverage unclear.

### Files in `tests/`
- `tests/unit/test_minimal.py`
- `tests/unit/test_services.py`
- `tests/unit/test_audio.py`
- `tests/unit/test_resilience.py`
- `tests/unit/test_stt_providers/`

### Recommendations
1. Add pytest to requirements.txt (may already be in requirements-dev.txt)
2. Add CI/CD pipeline for automated testing
3. Add error path tests (currently most tests are happy path)

### Priority: P2

---

## 8. Duplicate Code Consolidation

### Issue
Some patterns duplicated across files.

### Examples

| Pattern | Files | Suggestion |
|---------|-------|------------|
| TclError handling in UI | 10+ dialog files | Already consistent, acceptable |
| Provider model/temperature config | Now uses `_make_provider_model_config()` | Resolved |
| Retry logic | `retry_decorator.py` + `resilience.py` | Consider consolidating | P3 |

---

## 9. Documentation Gaps

### Issue
Some modules lack docstrings explaining error handling contracts.

### Suggested Template
```python
"""
Module docstring.

Error Handling:
    - Raises APIError: On connection/API failures
    - Raises ValidationError: On invalid input
    - Returns OperationResult: For operations that can fail gracefully

Logging:
    - Uses structured logging with operation context
    - Sensitive data is automatically redacted
"""
```

### Priority: P3

---

## Completed Items

| Item | Date | Commit |
|------|------|--------|
| Import inconsistency standardization | 2024 | v2.6.137 |
| RSVP dialog modularization | 2024 | RSVP refactor |
| CommandRegistry for app.py decoupling | 2024 | CommandRegistry commit |
| Settings domain organization | 2024 | Settings refactor |
| Exception consolidation (APITimeoutError) | 2024 | Exception consolidation |
| Error handling: processing_queue.py (P1) | 2026-01 | ErrorContext + specific exceptions |
| Error handling: deep_translator_provider.py (P2) | 2026-01 | ErrorContext adoption |
| Error handling: audio.py (P2) | 2026-01 | ErrorContext adoption |
| Error handling: database.py (P2) | 2026-01 | ErrorContext + documented design |
| Return type: AI providers use AIResult (P2) | 2026-01 | All providers return AIResult |
| Return type: router.py uses AIResult (P2) | 2026-01 | call_ai, call_ai_streaming |
| Return type: letter_generation.py (P2) | 2026-01 | Uses AIResult.text |
| Logging: processing_queue.py (P2) | 2026-01 | Structured logger with context |
| Logging: ai_processor.py (P2) | 2026-01 | Structured logger with context |
| Logging: recording_manager.py (P3) | 2026-01 | Structured logger with context |

---

## How to Use This Document

1. **When fixing bugs**: Check if the file is listed here; apply patterns while fixing
2. **When adding features**: Use the recommended patterns from the start
3. **During refactoring sprints**: Pick a section and migrate files systematically
4. **Code review**: Reference this for consistent feedback

---

## Contributing

When addressing items:
1. Update the file's entry in this document
2. Move completed items to "Completed Items" section
3. Add new debt discovered during development
