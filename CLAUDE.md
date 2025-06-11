# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
python main.py
```

### Building Executables
```bash
# Windows
scripts/build_windows.bat

# macOS  
./scripts/build_macos.sh

# Linux
./scripts/build_linux.sh
```

### Running Tests
```bash
# Run all tests with pytest
pytest

# Run minimal tests
python tests/unit/test_minimal.py

# Run specific component tests
python tests/unit/test_services.py
python tests/unit/test_audio.py
python tests/unit/test_resilience.py

# Run STT provider tests
python tests/unit/test_stt_providers/run_tests.py

# Run UI tests
python tests/run_ui_tests.py
python tests/run_tkinter_ui_tests.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development/testing
```

## Architecture Overview

### Core Application Flow
1. **Entry Point**: `main.py` → `src/core/app.py` → `src/ui/workflow_ui.py`
2. **UI Structure**: 5 workflow tabs (Record, Process, Generate, Recordings, Chat) + 5 text editor tabs
3. **Audio Pipeline**: `src/audio/audio.py` → `src/audio/recording_manager.py` → STT provider → `src/ai/ai_processor.py`
4. **Data Flow**: Recording → Transcript → AI Processing → SOAP/Referral/Letter generation

### Key Architectural Components

**Provider Pattern**: All STT providers inherit from `src/stt_providers/base.BaseSTTProvider`:
- `deepgram.py`, `elevenlabs.py`, `groq.py`, `whisper.py`
- Each implements `transcribe()` and `test_connection()` methods

**Security Layer**: 
- API keys encrypted via `src/utils/security.py` using Fernet encryption
- Security decorators in `src/utils/security_decorators.py` for rate limiting and input sanitization
- Keys stored in `AppData/api_keys.enc` with machine-specific derivation

**Database Architecture**:
- SQLite with version-controlled migrations in `src/database/db_migrations.py`
- Main table: `recordings` with FTS5 support
- Queue system tables for background processing
- Connection pooling via `src/database/db_pool.py`

**Configuration System**:
- Environment-based configs in `config/` directory
- `src/core/config.py` loads appropriate config based on environment
- Dataclass-based configuration with validation

### Processing Queue System
- `src/processing/processing_queue.py` manages background processing
- "Quick Continue Mode" allows queuing recordings while starting new ones
- Status tracked in database with visual indicators (✓, —, 🔄, ❌)

### UI Components
- **Chat Interface**: `src/ui/chat_ui.py` - ChatGPT-style interface as 5th workflow tab
- **Recording Dialog**: `src/audio/soap_audio_processor.py` - Handles SOAP recording workflow
- **Settings Dialogs**: `src/ui/dialogs/dialogs.py` - API keys, prompts, models configuration
- **Theme System**: `src/ui/theme_manager.py` - Dark/light theme support

### AI Integration
- **AI Processor**: `src/ai/ai_processor.py` - Core AI integration for document generation
- **Chat Processor**: `src/ai/chat_processor.py` - Handles chat interactions
- **SOAP Processor**: `src/ai/soap_processor.py` - SOAP note generation logic
- **Prompts**: `src/ai/prompts.py` - System prompts for AI models

### Important Patterns
- Use context managers for database transactions
- All API calls should use security decorators
- Audio processing must handle platform-specific differences
- Always preserve user context during SOAP recordings
- Queue processing runs in background threads

## Platform-Specific Considerations

### Windows
- FFmpeg bundled with executable
- Audio backend: soundcard or pyaudio fallback
- Console suppression via `hooks/suppress_console.py`

### macOS
- FFmpeg bundled in .app
- Requires microphone permissions
- Icon: `icon.icns`

### Linux
- Uses system FFmpeg (not bundled)
- Requires `scripts/linux_launcher.sh` for proper library loading
- Desktop entry: `medical-assistant.desktop`

## Critical Files to Understand

1. **src/ui/workflow_ui.py**: Main UI orchestration and tab management
2. **src/ai/ai_processor.py**: Core AI integration logic for all providers
3. **src/audio/recording_manager.py**: Audio recording state management
4. **src/processing/processing_queue.py**: Background processing implementation
5. **src/utils/security.py**: API key encryption and security features
6. **src/database/db_migrations.py**: Database schema evolution

## Common Development Tasks

### Adding a New STT Provider
1. Create new file in `src/stt_providers/`
2. Inherit from `BaseSTTProvider`
3. Implement required methods
4. Add to provider list in UI

### Adding a New AI Provider
1. Update `src/ai/ai.py` with new provider class
2. Add API key handling in `src/managers/api_key_manager.py`
3. Update UI dropdowns in `src/ui/workflow_ui.py`
4. Add to security configuration
5. For Anthropic/Claude models, dynamic model fetching is already implemented

### Database Schema Changes
1. Add migration in `src/database/db_migrations.py`
2. Increment version number
3. Test migration with existing databases

## Testing and Validation

When making changes:
1. Test all audio recording scenarios (start, pause, resume, stop)
2. Verify queue processing with multiple recordings
3. Check all document generation paths (SOAP, Referral, Letter)
4. Test with different AI/STT provider combinations
5. Validate security features (API key encryption, rate limiting)
6. Test chat functionality with various AI providers
7. Verify UI responsiveness across all tabs

## Project Structure (Post-Reorganization)

All source code is now organized under the `src/` directory:
- `src/ai/` - AI providers and processors
- `src/audio/` - Audio recording and processing
- `src/core/` - Core application logic
- `src/database/` - Database management
- `src/managers/` - Various manager classes
- `src/processing/` - Document processing
- `src/settings/` - Settings management
- `src/stt_providers/` - Speech-to-text providers
- `src/ui/` - User interface components
- `src/utils/` - Utility functions and helpers