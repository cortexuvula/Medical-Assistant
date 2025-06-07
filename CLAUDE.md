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
build_windows.bat

# macOS  
./build_macos.sh

# Linux
./build_linux.sh
```

### Running Tests
```bash
# Run minimal tests
python test_minimal.py

# Run specific component tests
python test_services.py
python test_audio.py
python test_resilience.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

## Architecture Overview

### Core Application Flow
1. **Entry Point**: `main.py` → `app.py` → `workflow_ui.py`
2. **UI Structure**: 4 workflow tabs (Record, Process, Generate, Recordings) + 5 text editor tabs
3. **Audio Pipeline**: `audio.py` → `recording_manager.py` → STT provider → `ai_processor.py`
4. **Data Flow**: Recording → Transcript → AI Processing → SOAP/Referral/Letter generation

### Key Architectural Components

**Provider Pattern**: All STT providers inherit from `stt_providers.base.BaseSTTProvider`:
- `deepgram.py`, `elevenlabs.py`, `groq.py`, `whisper.py`
- Each implements `transcribe()` and `test_connection()` methods

**Security Layer**: 
- API keys encrypted via `security.py` using Fernet encryption
- Security decorators in `security_decorators.py` for rate limiting and input sanitization
- Keys stored in `AppData/api_keys.enc` with machine-specific derivation

**Database Architecture**:
- SQLite with version-controlled migrations in `db_migrations.py`
- Main table: `recordings` with FTS5 support
- Queue system tables for background processing
- Connection pooling via `db_pool.py`

**Configuration System**:
- Environment-based configs in `config/` directory
- `config.py` loads appropriate config based on environment
- Dataclass-based configuration with validation

### Processing Queue System
- `processing_queue.py` manages background processing
- "Quick Continue Mode" allows queuing recordings while starting new ones
- Status tracked in database with visual indicators (✓, —, 🔄, ❌)

### UI Components
- **Chat Interface**: `chat_ui.py` - ChatGPT-style interface at bottom
- **Recording Dialog**: `soap_audio_processor.py` - Handles SOAP recording workflow
- **Settings Dialogs**: `dialogs.py` - API keys, prompts, models configuration
- **Theme System**: `theme_manager.py` - Dark/light theme support

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
- Console suppression via `suppress_console.py`

### macOS
- FFmpeg bundled in .app
- Requires microphone permissions
- Icon: `icon.icns`

### Linux
- Uses system FFmpeg (not bundled)
- Requires `linux_launcher.sh` for proper library loading
- Desktop entry: `medical-assistant.desktop`

## Critical Files to Understand

1. **workflow_ui.py**: Main UI orchestration and tab management
2. **ai_processor.py**: Core AI integration logic for all providers
3. **recording_manager.py**: Audio recording state management
4. **processing_queue.py**: Background processing implementation
5. **security.py**: API key encryption and security features
6. **db_migrations.py**: Database schema evolution

## Common Development Tasks

### Adding a New STT Provider
1. Create new file in `stt_providers/`
2. Inherit from `BaseSTTProvider`
3. Implement required methods
4. Add to provider list in UI

### Adding a New AI Provider
1. Update `ai.py` with new provider class
2. Add API key handling in `api_key_manager.py`
3. Update UI dropdowns in `workflow_ui.py`
4. Add to security configuration

### Database Schema Changes
1. Add migration in `db_migrations.py`
2. Increment version number
3. Test migration with existing databases

## Testing and Validation

When making changes:
1. Test all audio recording scenarios (start, pause, resume, stop)
2. Verify queue processing with multiple recordings
3. Check all document generation paths (SOAP, Referral, Letter)
4. Test with different AI/STT provider combinations
5. Validate security features (API key encryption, rate limiting)