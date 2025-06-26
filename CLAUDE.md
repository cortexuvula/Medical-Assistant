# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Medication Agent Implementation Summary

The medication agent has been fully integrated into the Medical Assistant application. Key implementation details:

### Architecture
- **Agent System**: Located in `src/ai/agents/` with base class inheritance pattern
- **MedicationAgent**: Comprehensive medication analysis in `src/ai/agents/medication.py`
- **UI Integration**: Button in Generate tab connects to `analyze_medications` command
- **Dialog System**: Two dialogs for options selection and results display

### Data Flow
1. User clicks medication analysis button → `app.analyze_medications()`
2. Shows `MedicationAnalysisDialog` for source/type selection
3. `document_generators.analyze_medications()` prepares data
4. `agent_manager.execute_agent_task()` runs the medication agent
5. Results displayed in `MedicationResultsDialog`

### Key Features
- Extract medications from clinical text
- Check drug-drug interactions with severity levels
- Validate dosing appropriateness
- Suggest medication alternatives
- Generate prescriptions
- Comprehensive analysis with safety warnings

### Important Implementation Details
- Input data mapping: UI sends "clinical_text" (not "content") to agent
- Context support: Can analyze from transcript, SOAP note, or context tab
- Medication list detection: Automatically parses medication lists for comprehensive analysis
- Settings integration: Uses medication-specific model settings from settings.json

## Workflow Agent Implementation Summary

The workflow agent has been fully integrated into the Medical Assistant application:

### Architecture
- **WorkflowAgent**: Clinical workflow coordinator in `src/ai/agents/workflow.py`
- **Workflow Types**: Patient intake, diagnostic workup, treatment protocols, follow-up care
- **Interactive UI**: Progress tracking with checkboxes and workflow visualization

### Key Features
- Step-by-step clinical process guidance
- Interactive checklist for progress tracking
- Time estimates and decision points
- Safety checkpoints and documentation requirements
- Export workflows to multiple formats
- Flexible and customizable workflows

### UI Integration
- Button in Generate tab for "Clinical Workflow"
- `WorkflowDialog` for selecting workflow type and patient context
- `WorkflowResultsDialog` for displaying and tracking workflow progress
- Progress indicators and step completion tracking

## Periodic Analysis Implementation Summary

The periodic analysis feature provides real-time differential diagnosis during recordings:

### Architecture
- **PeriodicAnalyzer**: Core class in `src/audio/periodic_analysis.py` managing timed analysis
- **AudioSegmentExtractor**: Extracts audio segments from ongoing recordings
- **Integration**: Checkbox in Record tab enables/disables feature
- **Interval**: Analysis runs every 2 minutes (120 seconds)

### Key Features
- Real-time differential diagnosis generation during recordings
- Customizable prompts via Settings → Prompt Settings → Advanced Analysis Settings
- Provider-specific model and temperature configuration
- Clear display in Advanced Analysis Results text area
- Automatic cleanup on recording stop/cancel

### Implementation Details
- Timer threads are daemon threads to prevent shutdown issues
- Periodic analyzer stops automatically when:
  - Recording is stopped normally
  - Recording is cancelled
  - Application is closed
- Audio segments are passed directly to transcription (no temp files)
- Results clear on each new analysis to maintain readability

### Settings Integration
- Advanced analysis settings stored in `settings.json`
- Configurable prompt and system message
- Provider-specific models and temperatures
- Settings accessible via menu: Settings → Prompt Settings → Advanced Analysis Settings

## Voice Mode Implementation Summary

Advanced voice mode provides real-time voice conversations with the AI assistant:

### Architecture
- **VoiceInteractionManager**: Core orchestrator in `src/voice/voice_interaction_manager.py`
- **StreamingSTT**: Real-time speech recognition via `src/voice/streaming_stt.py` using Deepgram WebSocket API
- **TTSProviders**: Text-to-speech in `src/voice/tts_providers.py` supporting OpenAI and ElevenLabs
- **AudioPlayback**: Audio output system in `src/voice/audio_playback.py` with streaming support
- **VoiceActivityDetection**: VAD in `src/voice/voice_activity_detection.py` using WebRTC VAD
- **WebSocket Infrastructure**: Optional WebSocket server/client for remote audio streaming

### Key Features
- Natural voice conversations with turn-taking
- Real-time transcription with interim results
- Streaming TTS for low-latency responses
- Voice interruption support
- Medical context awareness
- Conversation history and export
- Volume control and voice selection

### UI Integration
- New "Voice Mode" tab in main workflow
- Large activation button with visual feedback
- Real-time conversation display
- Settings for voice, volume, and interruptions
- Export and context integration options

### Implementation Details
- Conversation states: IDLE, LISTENING, PROCESSING, SPEAKING, INTERRUPTED
- Hybrid VAD combining WebRTC VAD and energy-based detection
- Audio playback with queue system for smooth streaming
- Async/await patterns for WebSocket and API operations
- Thread-safe audio processing

### Voice Mode Flow
1. User clicks "Start Voice Mode" button
2. System initializes STT, TTS, and VAD components
3. Audio capture begins, VAD detects speech segments
4. Speech is transcribed in real-time via Deepgram
5. Complete utterances trigger AI processing
6. AI response is synthesized to speech
7. Audio plays while allowing interruptions
8. Conversation saved to database on session end

### Configuration
- Voice settings integrated with existing provider settings
- Default models: GPT-4 for AI, Nova for TTS voice
- Customizable system prompts for medical context
- Provider-specific API keys required:
  - Deepgram for streaming STT
  - OpenAI/ElevenLabs for TTS

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
2. **UI Structure**: 6 workflow tabs (Record, Process, Generate, Recordings, Chat, Voice Mode) + 5 text editor tabs
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
- **Medication Dialogs**: 
  - `src/ui/dialogs/medication_analysis_dialog.py` - Options for medication analysis
  - `src/ui/dialogs/medication_results_dialog.py` - Display medication analysis results
- **Workflow Dialogs**:
  - `src/ui/dialogs/workflow_dialog.py` - Options for clinical workflow selection
  - `src/ui/dialogs/workflow_results_dialog.py` - Interactive workflow tracking and display

### AI Integration
- **AI Processor**: `src/ai/ai_processor.py` - Core AI integration for document generation
- **Chat Processor**: `src/ai/chat_processor.py` - Handles chat interactions
- **SOAP Processor**: `src/ai/soap_processor.py` - SOAP note generation logic
- **Prompts**: `src/ai/prompts.py` - System prompts for AI models
- **Agent System**: `src/ai/agents/` - Specialized AI agents for medical tasks
  - `base.py` - BaseAgent class all agents inherit from
  - `medication.py` - Medication analysis agent
  - `models.py` - Pydantic models (AgentConfig, AgentTask, AgentResponse)
  - Additional agents: synopsis, diagnostic, referral, data_extraction, workflow

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
4. **src/audio/periodic_analysis.py**: Periodic analysis during recordings
5. **src/processing/processing_queue.py**: Background processing implementation
6. **src/utils/security.py**: API key encryption and security features
7. **src/database/db_migrations.py**: Database schema evolution
8. **src/managers/agent_manager.py**: Agent system management and execution
9. **src/ai/agents/medication.py**: Medication agent implementation example
10. **src/ai/agents/workflow.py**: Workflow agent for clinical process coordination
11. **src/voice/voice_interaction_manager.py**: Core voice mode orchestration
12. **src/voice/streaming_stt.py**: Real-time speech recognition implementation
13. **src/ui/voice_mode_ui.py**: Voice mode user interface

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

### Adding a New AI Agent
1. Create new file in `src/ai/agents/` inheriting from `BaseAgent`
2. Implement `execute()` method to handle `AgentTask` input
3. Add agent type to `AgentType` enum in `src/ai/agents/models.py`
4. Register in `src/managers/agent_manager.py`
5. Add UI integration in `src/processing/document_generators.py`
6. Create dialogs in `src/ui/dialogs/` if needed
7. Add command mapping in `src/core/app.py`
8. Update settings.json with agent configuration

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
8. Test agent functionality (medication analysis, diagnostic, etc.)
9. Verify agent settings persistence and configuration

## Project Structure (Post-Reorganization)

All source code is now organized under the `src/` directory:
- `src/ai/` - AI providers and processors
  - `agents/` - Specialized AI agents
    - `base.py` - Base agent class
    - `medication.py` - Medication analysis
    - `diagnostic.py` - Diagnostic suggestions
    - `synopsis.py` - SOAP note synopsis
    - `models.py` - Shared data models
    - `workflow.py` - Clinical workflow coordination
- `src/audio/` - Audio recording and processing
- `src/core/` - Core application logic
- `src/database/` - Database management
- `src/managers/` - Various manager classes
  - `agent_manager.py` - Singleton for agent management
- `src/processing/` - Document processing
  - `document_generators.py` - Handles all document generation including agent tasks
- `src/settings/` - Settings management
- `src/stt_providers/` - Speech-to-text providers
- `src/ui/` - User interface components
  - `dialogs/` - All dialog windows
    - `medication_analysis_dialog.py` - Medication analysis options
    - `medication_results_dialog.py` - Medication results display
  - `voice_mode_ui.py` - Voice mode interface
- `src/utils/` - Utility functions and helpers
- `src/voice/` - Voice mode components
  - `voice_interaction_manager.py` - Main voice mode orchestrator
  - `streaming_stt.py` - Real-time speech recognition
  - `tts_providers.py` - Text-to-speech providers
  - `audio_playback.py` - Audio output system
  - `voice_activity_detection.py` - VAD implementation
  - `websocket_server.py` - WebSocket server for remote audio
  - `websocket_client.py` - WebSocket client