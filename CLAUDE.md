# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General Rules

Never declare a task complete or working without verifying the result. Run the relevant command, check the output, or ask the user to confirm before saying 'done'.

## Refactoring

After any find-and-replace or bulk refactoring operation, always run a grep to verify the replacements look correct before proceeding. Check for spacing issues, concatenated tokens, and malformed syntax.

## Testing

After modifying import paths or module structure, always run the full test suite AND check that patch paths in tests still match the new module locations.

## Architecture Boundary Conventions

The codebase enforces clean boundaries between components. Follow these rules when adding or modifying code:

### ServiceRegistry (src/core/service_registry.py)
- **New controllers** must accept `registry: Optional[ServiceRegistry]` in their constructor (dual-mode pattern)
- Access protocol-backed services (status_manager, recording_manager, database, etc.) via `self._registry`, not `self.app`
- Widget/Tk operations may still use `self.app` (backward-compatible)

### Protocol Interfaces (src/core/interfaces.py)
- All protocols are `@runtime_checkable` — add the decorator when creating new protocols
- Protocol signatures must match concrete implementations
- `DocumentTargetProtocol` is the narrow interface for dialogs that insert content into documents

### Controller Rules
- Controllers must NOT import `from core.app import MedicalDictationApp` at runtime — only inside `if TYPE_CHECKING:` blocks
- This is enforced by CI (import boundary check in tests.yml)
- Use `ServiceRegistry` for service access, `self.app` only for Tk widget operations

### Dialog Rules
- **New result dialogs** should accept `document_target` parameter instead of reaching into `self.parent`
- Use `self._document_target or self.parent` pattern for backward compatibility
- Base class: `BaseResultsDialog` already supports this via `_get_document_target()`

### File Size Guidelines
- New files should be under 500 lines
- Large files should be decomposed using the mixin pattern (see `ProcessingQueue` with 7 mixins as the reference)
- Static data (dictionaries, prompt templates, code tables) should be in separate `*_data.py` or `*_prompts.py` files

### CI Enforcement
- **Mypy**: Runs on `interfaces.py` and `service_registry.py` with `--follow-imports=silent`
- **Import boundary**: Verifies controllers don't import `core.app` at runtime
- **Tests**: Boundary contract tests in `tests/unit/test_boundary_contracts.py`, `test_dialog_boundaries.py`, `test_controller_boundaries.py`

## Development Commands

```bash
# Run the application
python main.py

# Run all tests
pytest

# Build executables
scripts/build_windows.bat      # Windows
./scripts/build_macos.sh       # macOS
./scripts/build_linux.sh       # Linux

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # dev/testing
```

## Key Architecture

- **Entry Point**: `main.py` → `src/core/app.py` → `src/ui/workflow_ui.py`
- **UI**: Sidebar with 8 nav sections (Record, SOAP Note, Referral, Letter, Chat, RAG, Recordings, Analysis) + 6 text editor tabs + 6 SOAP analysis sub-tabs
- **Audio Pipeline**: `src/audio/` → STT provider → `src/ai/ai_processor.py`
- **Data Flow**: Recording → Transcript → AI Processing → SOAP/Referral/Letter
- **Database**: SQLite with versioned migrations in `src/database/db_migrations.py`
- **Security**: Fernet-encrypted API keys, audit logging, PHI redaction — see `src/utils/security/`
- **Agents**: `src/ai/agents/` — BaseAgent pattern with medication, diagnostic, synopsis, workflow, referral, data_extraction agents
- **RAG**: `src/rag/` — Neon pgvector + optional Neo4j knowledge graph with hybrid search (BM25 + vector + MMR)

## Important Patterns

- Use context managers for database transactions
- All API calls should use security decorators from `src/utils/security_decorators.py`
- Audio processing must handle platform-specific differences
- Queue processing runs in background threads (`src/processing/processing_queue.py`)
- Agent input uses "clinical_text" key (not "content")

## Adding New Components

### New STT Provider
1. Create file in `src/stt_providers/` inheriting from `BaseSTTProvider`
2. Implement `transcribe()` and `test_connection()`
3. Add to provider list in UI

### New AI Provider
1. Update `src/ai/ai.py` with new provider class
2. Add API key handling in `src/managers/api_key_manager.py`
3. Update UI dropdowns in `src/ui/workflow_ui.py`
4. Add to security configuration

### New AI Agent
1. Create file in `src/ai/agents/` inheriting from `BaseAgent`
2. Implement `execute()` method
3. Add to `AgentType` enum in `src/ai/agents/models.py`
4. Register in `src/managers/agent_manager.py`
5. Add UI integration in `src/processing/document_generators.py`
6. Create dialogs in `src/ui/dialogs/` if needed
7. Add command mapping in `src/core/app.py`

### Database Schema Changes
1. Add migration in `src/database/db_migrations.py`
2. Increment version number
3. Test migration with existing databases

## Platform Notes

- **Windows**: FFmpeg bundled; audio via soundcard/pyaudio; console suppression via `hooks/suppress_console.py`
- **macOS**: FFmpeg bundled in .app; requires microphone permissions
- **Linux**: System FFmpeg; requires `scripts/linux_launcher.sh` for library loading

## Known Gotchas

- **Threading/Shutdown**: `_refresh_recordings_list` can hit "main thread not in main loop" — UI updates wrapped in try-except with parent existence checks
- **Translation language parsing**: Languages with parentheses (e.g., "Chinese (Simplified)") — use `rfind('(')` for code extraction
- **TTS Settings Dialog**: Widget references must be created before lambda closures that reference them
