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
| `src/ui/dialogs/*.py` | Many files use `messagebox.showerror()` directly | P2 | Phase 1 ✅ (6 files), Phase 2 ✅ (7 files) |
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
| `src/managers/*.py` | Various return styles | P3 | ✅ Logging standardized |

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
| `src/database/database.py` | ~12 | P3 | ✅ Fixed - Uses structured logger |

### Migration Strategy
1. Replace `import logging` with `from utils.structured_logging import get_logger`
2. Replace `logging.getLogger(__name__)` with `get_logger(__name__)`
3. Add context parameters to log calls

---

## 4. Settings Access Patterns

### Issue
`SettingsManager` provides typed accessors but some code directly accesses `SETTINGS[...]` dict.

### Current State
```python
# Preferred pattern (typed accessors):
from settings.settings_manager import settings_manager
provider = settings_manager.get_ai_provider()
temperature = settings_manager.get_nested("soap_note.temperature", 0.4)
soap_config = settings_manager.get_soap_config()

# Legacy pattern (direct access) - still in some UI/test files:
provider = SETTINGS.get("ai_provider", "openai")
temperature = SETTINGS.get("soap_note", {}).get("temperature", 0.4)
```

### Migration Progress (2026-01)

| Category | Files Migrated | Status |
|----------|---------------|--------|
| AI Processing | ai_processor.py, chat_processor.py, text_processing.py, soap_processor.py | ✅ |
| Managers | file_manager.py, tts_manager.py, translation_manager.py, agent_manager.py | ✅ |
| Processing | processing_queue.py | ✅ |
| STT Providers | elevenlabs.py | ✅ |
| UI/Dialogs | All dialog files migrated | ✅ |
| Tests/Examples | Expected - uses SETTINGS | N/A |

### UI Dialog Migration (2026-01)
All UI dialog files migrated from direct `SETTINGS[...]` access to `settings_manager`:
- folder_dialogs.py, canned_responses_dialog.py, vocabulary_dialog.py
- audio_dialogs.py, recordings_dialog_manager.py, rsvp_dialog.py
- translation/__init__.py, translation/languages.py, translation/responses.py, translation/recording.py
- standalone_rsvp_dialog.py, unified_settings_dialog.py, document_dialogs.py
- groq_settings_dialog.py, translation_settings_dialog.py, elevenlabs_settings_dialog.py
- deepgram_settings_dialog.py, tts_settings_dialog.py, temperature_dialog.py
- agent_settings_dialog.py, advanced_agent_settings_dialog.py, mcp_config_dialog.py

### Recommendation
- New code should use `settings_manager` typed accessors
- `settings_manager.py` wraps SETTINGS and provides typed methods
- Added `get_default()` method to access `_DEFAULT_SETTINGS` via settings_manager

### Status: ✅ Complete

---

## 5. Large File Refactoring

### Issue
Some files are too large, making them hard to navigate and maintain.

### Files Over 500 Lines

| File | Lines | Suggestion | Priority | Status |
|------|-------|------------|----------|--------|
| `src/core/app.py` | ~1100 | Further mixin extraction | P3 | ✅ Uses 5 mixins, delegates to controllers |
| `src/ui/workflow_ui.py` | 344 | Split by tab/concern | P3 | ✅ Refactored to use component classes |
| `src/processing/processing_queue.py` | ~1400 | Extract batch processing | P3 | ✅ Uses 3 mixins (batch, docs, reprocess) |
| `src/settings/settings.py` | ~700 | Already improved, acceptable | - | ✅ |

### Note
All large files now use mixins or component classes for organization. `app.py` uses:
- AppSettingsMixin, AppChatMixin, AppDialogMixin, AppUiLayoutMixin, AppRecordingMixin

`processing_queue.py` uses:
- BatchProcessingMixin, DocumentGenerationMixin, ReprocessingMixin

`workflow_ui.py` uses component classes:
- RecordTab, RecordingsTab, ContextPanel, StatusBar, NotebookTabs, etc.

### Status: ✅ Complete

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
| Translation API calls | Has `@resilient_api_call` | ✅ Already uses retry + circuit breaker | - |
| Database operations | `@db_retry` + `@db_resilient` | ✅ Circuit breaker added via `db_resilient` decorator | - |
| HTTP fetches (RAG, webhooks) | Has `@smart_retry` | ✅ RAG processor uses retry with backoff | - |

---

## 7. Test Infrastructure

### Issue
Tests exist but test coverage unclear.

### Files in `tests/`
- `tests/unit/test_minimal.py`
- `tests/unit/test_services.py`
- `tests/unit/test_audio.py`
- `tests/unit/test_resilience.py`
- `tests/unit/test_stt_providers/`

### Status
- ✅ pytest is in `requirements-dev.txt` with full test suite:
  - pytest==7.4.3
  - pytest-cov==4.1.0
  - pytest-mock==3.12.0
  - pytest-asyncio==0.21.1
  - pytest-timeout==2.2.0
  - pytest-xdist==3.5.0 (parallel execution)

### Recommendations
1. ✅ CI/CD pipeline exists in `.github/workflows/tests.yml`:
   - Multi-platform (Ubuntu, Windows, macOS)
   - Multiple Python versions (3.10, 3.11, 3.12)
   - Coverage reporting via Codecov
   - Security scanning (safety, bandit)
   - Build testing with PyInstaller
2. ✅ Error path tests exist in key modules (test_resilience.py, test_processing_queue.py)
3. Run `pip install -r requirements-dev.txt` to install test dependencies

### Status: ✅ Complete

---

## 8. Duplicate Code Consolidation

### Issue
Some patterns duplicated across files.

### Examples

| Pattern | Files | Suggestion |
|---------|-------|------------|
| TclError handling in UI | 10+ dialog files | Already consistent, acceptable |
| Provider model/temperature config | Now uses `_make_provider_model_config()` | Resolved |
| Retry logic | `retry_decorator.py` + `resilience.py` | Keep separate (different domains) | ✅ |

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

### Status
- ✅ `exceptions.py` - Full exception hierarchy documentation
- ✅ `resilience.py` - Error handling and usage documentation
- ✅ `retry_decorator.py` - Component documentation with usage examples
- ✅ `error_handling.py` - Comprehensive usage examples in docstring
- ✅ `ai_processor.py` - Error handling, logging, and usage documentation
- ✅ `recording_manager.py` - Error handling, logging, and thread safety documentation
- ✅ `processing_queue.py` - Error handling, logging, thread safety, and deduplication documentation
- ✅ `chat_processor.py` - Error handling, logging, and thread safety documentation
- ✅ `router.py` - Error handling, logging, and usage documentation
- ✅ `stt_providers/base.py` - Error handling, logging, and usage documentation
- ✅ `tts_providers/base.py` - Error handling, logging, and usage documentation

### Priority: P3 (Gradual - add documentation when touching files) - ✅ Key modules documented

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
| Error handling: diagnostic_history_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: base_results_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: mcp_config_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: medication_results_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: workflow_results_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: recordings_dialog_manager.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: translation dialogs (P2) | 2026-01 | ErrorContext + structured logging (recording.py, history.py, tts.py, __init__.py) |
| Error handling: audio_dialogs.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: data_extraction_results_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: vocabulary_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: agent_settings_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Error handling: advanced_agent_settings_dialog.py (P2) | 2026-01 | ErrorContext + structured logging |
| Logging: database.py + all mixins (P3) | 2026-01 | Structured logging across database layer |
| Logging: db_migrations.py (P3) | 2026-01 | Structured logging |
| Logging: db_pool.py (P3) | 2026-01 | Structured logging |
| Logging: db_manager.py (P3) | 2026-01 | Structured logging |
| Logging: db_queue_schema.py (P3) | 2026-01 | Structured logging |
| Logging: database_v2.py (P3) | 2026-01 | Structured logging |
| Resilience: rag_processor.py (P2) | 2026-01 | @smart_retry for HTTP webhook calls |
| Logging: managers/*.py (P3) | 2026-01 | Structured logging across all managers |
| Logging: retry_decorator.py (P3) | 2026-01 | Structured logging |
| Logging: resilience.py (P3) | 2026-01 | Structured logging |
| Duplicate Code: retry logic decision | 2026-01 | Keep separate - different domains (DB vs API) |
| Documentation: exceptions.py | 2026-01 | Full exception hierarchy documentation |
| Documentation: resilience.py | 2026-01 | Error handling and usage documentation |
| Test Infrastructure: Error path tests | 2026-01 | Verified - tests exist in test_resilience.py, test_processing_queue.py |
| Resilience: Database circuit breaker (P3) | 2026-01 | Added DatabaseCircuitBreaker class + db_resilient decorator |
| Test Infrastructure: CI/CD Pipeline (P3) | 2026-01 | Verified - tests.yml exists with multi-platform, multi-version testing |
| Logging: error_handling.py (P3) | 2026-01 | Updated to use structured logging |
| Documentation: error_handling.py (P3) | 2026-01 | Already has comprehensive usage documentation |
| Logging: utils/*.py (P3) | 2026-01 | All utility files updated to structured logging |
| Logging: processing/generators/*.py (P3) | 2026-01 | All generator mixins updated to structured logging |
| Logging: tts_providers/*.py (P3) | 2026-01 | Base TTS provider updated to structured logging |
| Settings: ai_processor.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: chat_processor.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: file_manager.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: processing_queue.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: soap_processor.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: text_processing.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: tts_manager.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: translation_manager.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: agent_manager.py (P3) | 2026-01 | Migrated to settings_manager |
| Settings: elevenlabs.py (STT) (P3) | 2026-01 | Migrated to settings_manager |
| Documentation: ai_processor.py (P3) | 2026-01 | Error handling, logging, usage docstrings |
| Documentation: recording_manager.py (P3) | 2026-01 | Error handling, logging, thread safety docstrings |
| Documentation: processing_queue.py (P3) | 2026-01 | Comprehensive error/logging/threading documentation |
| Documentation: chat_processor.py (P3) | 2026-01 | Error handling, logging, thread safety docstrings |
| Documentation: router.py (P3) | 2026-01 | Error handling, logging, usage docstrings |
| Documentation: stt_providers/base.py (P3) | 2026-01 | Error handling, logging, usage docstrings |
| Documentation: tts_providers/base.py (P3) | 2026-01 | Error handling, logging, usage docstrings |
| Large File Refactoring: batch_processor.py | 2026-01 | Evaluated - existing separation adequate |
| Settings: UI dialogs migration (P3) | 2026-01 | All 22 dialog files migrated to settings_manager |
| Settings: Added get_default() method | 2026-01 | Access _DEFAULT_SETTINGS via settings_manager |
| Settings: Added get_all() method | 2026-01 | Returns full settings dict for dialogs |
| Large File: processing_queue.py mixins | 2026-01 | Added BatchProcessingMixin, DocumentGenerationMixin, ReprocessingMixin |
| Large File: workflow_ui.py components | 2026-01 | Already uses RecordTab, RecordingsTab, etc. component classes |
| Large File: app.py mixins | 2026-01 | Already uses 5 mixins + controller delegation |
| Bug fix: error_handling.py missing import | 2026-01 | Added missing `import logging` |

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
