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
- Clear button in UI allows manual clearing of analysis results
- Analysis results automatically clear when starting a new recording

### Settings Integration
- Advanced analysis settings stored in `settings.json`
- Configurable prompt and system message
- Provider-specific models and temperatures
- Settings accessible via menu: Settings → Prompt Settings → Advanced Analysis Settings

## RAG (Retrieval-Augmented Generation) Tab Implementation Summary

The RAG tab provides document search capabilities through N8N webhook integration:

### Architecture
- **RagProcessor**: Core class in `src/ai/rag_processor.py` handling N8N webhook communication
- **N8N Integration**: Webhook-based document search with authorization headers
- **UI Integration**: New tab alongside Chat tab with shared AI Assistant input
- **Session Management**: Persistent session IDs for conversation continuity

### Key Features
- Query documents stored in your RAG database via N8N webhook
- Markdown rendering for formatted responses
- Copy button for each RAG response
- Clear history button to start new search sessions
- Session persistence across queries

### Implementation Details
- **Environment Variables**: N8N_URL and N8N_AUTHORIZATION_SECRET loaded from .env
- **Request Format**: Sends `chatInput` and `sessionId` fields to N8N
- **Response Handling**: Supports both array and object response formats
- **Markdown Support**: Renders headers, bold text, bullets, numbered lists, and code blocks
- **Error Handling**: Graceful handling of timeouts, connection errors, and empty responses

### UI Components
- RAG tab in main notebook (index 5, 0-based)
- Clear RAG History button in top-right corner
- Read-only text widget with markdown rendering
- Copy buttons for each assistant response
- Welcome message with usage instructions

## Bidirectional Translation Implementation Summary

The bidirectional translation assistant enables real-time medical translation for multilingual consultations:

### Architecture
- **TranslationDialog**: Main dialog in `src/ui/dialogs/translation_dialog.py`
- **TranslationManager**: Singleton manager in `src/managers/translation_manager.py`
- **DeepTranslatorProvider**: Translation backend supporting Google, DeepL, Microsoft
- **Integration**: Accessible via Tools → Translation Assistant menu

### Key Features
- **Real-time Translation**: Automatic translation as user types with debouncing
- **Speech-to-Text**: Record patient speech with automatic transcription
- **Text-to-Speech**: Play translated responses for patients
- **Language Support**: 100+ languages with automatic detection
- **Canned Responses**: Customizable quick responses for common phrases
- **Export**: Save conversation transcripts

### UI Components
- **Language Selection**: Dropdown menus showing "Language Name (code)"
- **Recording Controls**: Microphone selection and recording button
- **Text Areas**: Side-by-side display of original and translated text
- **TTS Controls**: Play button with output device selection
- **Canned Responses**: Grid of customizable quick response buttons

### Implementation Details
- **Language Code Parsing**: Fixed to handle languages with parentheses (e.g., "Chinese (Simplified)")
  - Uses `rfind('(')` to find last parenthesis for proper code extraction
- **Audio Handling**: Separate AudioHandler instance for translation recording
- **Settings Persistence**: Saves language and device preferences
- **Threading**: Non-blocking translation and TTS operations

### Canned Responses Management
- **CannedResponsesDialog**: CRUD interface for managing responses
- **Categories**: Greeting, symptom, history, instruction, clarify, general
- **Storage**: Responses saved in `settings.json` under `translation_canned_responses`
- **Default Responses**: Pre-populated common medical phrases

## RSVP Reader Implementation Summary

The RSVP (Rapid Serial Visual Presentation) reader provides speed reading functionality for SOAP notes:

### Architecture
- **RSVPDialog**: Main dialog class in `src/ui/dialogs/rsvp_dialog.py`
- **ORP Highlighting**: Optimal Recognition Point algorithm for improved reading comprehension
- **Settings Persistence**: All preferences saved to `settings.json` under "rsvp" key
- **Integration**: Accessible via "RSVP Reader" button in SOAP tab context menu

### Key Features
- **Persistent WPM Setting**: Reading speed saved between sessions (50-2000 WPM)
- **Fullscreen Mode (F11)**: Distraction-free reading experience
- **Section Navigation**: Jump directly to SOAP sections (Subjective, Objective, Assessment, Plan)
- **Chunk Mode**: Display 1-3 words at a time for faster reading
- **Adjustable Font Size**: Slider control for font size (24-96pt)
- **Auto-Start Option**: Automatically begin playback when dialog opens
- **Light/Dark Theme Toggle**: RSVP-specific theme independent of main app
- **Reading Statistics**: Shows elapsed time, average WPM, and word count on completion
- **Sentence Context Display**: Shows current sentence dimmed in background (optional)
- **Audio Cue on Section Changes**: Plays sound when entering new section (optional)

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| Space | Play/Pause |
| Up/Down | Speed +/- |
| Left/Right | Previous/Next word |
| Home/End | Start/End of text |
| F11 | Toggle fullscreen |
| Escape | Exit fullscreen first, then close |
| T | Toggle theme |
| 1/2/3 | Set chunk size |

### Settings Keys
```python
"rsvp": {
    "wpm": 300,           # Words per minute (50-2000)
    "font_size": 48,      # Font size for display (24-96)
    "chunk_size": 1,      # Words to display at once (1-3)
    "dark_theme": True,   # Dark/light theme
    "audio_cue": False,   # Sound on section changes
    "show_context": False # Show sentence context
}
```

### Text Preprocessing
- Removes ICD codes (ICD-9, ICD-10 lines)
- Removes "Not discussed" entries
- Strips leading bullet dashes
- Cleans excess whitespace

### Smart Timing
- Section headers: 3x delay
- End of sentence (.!?): 2.5x delay
- Clause punctuation (,;:): 1.5x delay
- Regular words: 1x delay

## TTS (Text-to-Speech) Integration

### ElevenLabs TTS Provider
- **Voice Selection**: Dropdown interface in TTS settings dialog
- **Model Support**:
  - Flash v2.5 (ultra-low latency, 50% cheaper - NEW Dec 2025)
  - Turbo v2.5 (fast, good quality)
  - Multilingual v2 (high quality multilingual, default)
- **Settings**: Voice ID, model, rate stored in `settings.json`
- **API Integration**: Fetch available voices dynamically using ElevenLabs SDK v2

## Unified Preferences Dialog

The application features a comprehensive Preferences dialog accessible via Settings → Preferences (Ctrl+,):

### Architecture
- **UnifiedSettingsDialog**: Main dialog class in `src/ui/dialogs/unified_settings_dialog.py`
- **Tabbed Interface**: 6 tabs organizing all settings logically
- **Keyboard Shortcut**: Ctrl+, (bound in `src/core/keyboard_shortcuts_controller.py`)
- **Menu Integration**: Primary entry point in Settings menu

### Tab Structure
| Tab | Content |
|-----|---------|
| **API Keys** | All LLM API keys (OpenAI, Anthropic, Grok, etc.) and STT keys (Deepgram, ElevenLabs, Groq) |
| **Audio & STT** | Sub-tabs: ElevenLabs, Deepgram, Groq, TTS settings |
| **AI Models** | Sub-tabs: Temperature settings, Translation provider configuration |
| **Prompts** | Quick links to edit Refine, Improve, SOAP, Referral, Advanced Analysis prompts |
| **Storage** | Default folder, Custom Vocabulary, Address Book, Prefix Audio |
| **General** | Quick Continue Mode, Theme selection, Sidebar preferences, Keyboard shortcuts reference |

### Key Features
- **Scrollable API Keys**: Canvas-based scrollable list for many API keys
- **Show/Hide Toggle**: Eye button to reveal/hide API key values
- **Nested Notebooks**: Audio & STT and AI Models tabs use nested notebooks for sub-sections
- **Tooltips**: All fields have descriptive tooltips on hover
- **Reset Defaults**: Button to reset all settings to defaults
- **Settings Persistence**: Uses `SETTINGS` dict and `save_settings()` function

### Settings Menu Organization
The Settings menu is organized into logical submenus:
```
Settings
├── Preferences...              [Ctrl+,] - Opens unified dialog
├── ─────────────
├── Update API Keys             [Quick access]
├── ─────────────
├── Audio & Transcription ▸     [ElevenLabs, Deepgram, Groq, TTS]
├── AI & Models ▸               [Temperature, Agent, Translation]
├── Prompt Settings ▸           [Refine, Improve, SOAP, Referral, Advanced]
├── Data & Storage ▸            [Vocabulary, Address Book, Storage, Prefix Audio]
├── ─────────────
├── Export Prompts
├── Import Prompts
├── ─────────────
├── Quick Continue Mode         [Toggle]
└── Toggle Theme                [Alt+T]
```

### Implementation Files
- `src/ui/dialogs/unified_settings_dialog.py` - Main dialog implementation
- `src/ui/menu_manager.py` - Settings menu organization with submenus
- `src/core/keyboard_shortcuts_controller.py` - Ctrl+, shortcut binding
- `src/core/app_settings_mixin.py` - `show_preferences()` method

## STT (Speech-to-Text) Providers

All STT providers inherit from `src/stt_providers/base.BaseSTTProvider` and implement:
- `transcribe(segment: AudioSegment) -> str` - Transcribe audio segment
- `test_connection() -> bool` - Test API connectivity

### Deepgram Provider (`src/stt_providers/deepgram.py`)
- **SDK**: `deepgram-sdk>=3.0.0,<5.0.0`
- **Model**: `nova-2-medical` (best for medical transcription)
- **Features**: Smart formatting, diarization, profanity filter, redaction
- **Settings Dialog**: Settings → Deepgram Settings
- **Configuration**: `config/config.default.json` → `deepgram` section

### ElevenLabs STT Provider (`src/stt_providers/elevenlabs.py`)
- **SDK**: `elevenlabs>=2.27.0` (v2 SDK)
- **Model**: `scribe_v1` (speech-to-text model)
- **Features**: Audio event tagging, timestamps, diarization
- **Settings Dialog**: Settings → ElevenLabs Settings
- **Configuration**: `config/config.default.json` → `elevenlabs` section

### Groq Provider (`src/stt_providers/groq.py`)
- **API**: OpenAI-compatible endpoint (`https://api.groq.com/openai/v1`)
- **Models**:
  - `whisper-large-v3-turbo` (default, fastest, 216x real-time)
  - `whisper-large-v3` (higher quality, slower)
  - `distil-whisper-large-v3-en` (English-only, fast)
- **Features**: Language selection, context prompts
- **Settings Dialog**: Settings → Groq Settings
- **Configuration**: `config/config.default.json` → `groq` section

### Whisper Provider (`src/stt_providers/whisper.py`)
- **Package**: `openai-whisper>=20250625`
- **Model**: `turbo` (default since 2025, best accuracy for English)
- **Note**: Runs locally, no API key required
- **Trade-off**: Higher accuracy but slower than cloud providers

## Batch Processing Implementation Summary

The batch processing feature allows users to process multiple recordings efficiently:

### Architecture
- **Enhanced BatchProcessingDialog**: Source selection between database recordings and audio files
- **Multi-file selection**: Support for selecting multiple audio files from computer
- **Processing queue integration**: Leverages existing queue system for efficient processing
- **Progress tracking**: Real-time BatchProgressDialog with statistics and ETA

### Key Features
- **Dual source support**:
  - Process selected recordings from database
  - Process audio files directly from computer
- **Multi-selection UI**:
  - Ctrl/Shift+Click for database recordings
  - File dialog for selecting multiple audio files
- **Processing options**:
  - Generate SOAP notes, referrals, and/or letters
  - Priority settings (low, normal, high)
  - Skip existing content option
  - Continue on error handling
- **Progress monitoring**:
  - Real-time progress bar and statistics
  - Processing speed calculation
  - Detailed log of each item's status
  - Cancel support for in-progress batches

### UI Integration
- **Recordings tab buttons**:
  - "Process Selected" - for database recordings
  - "Batch Process Files" - for audio files from computer
- **Dialogs**:
  - `BatchProcessingDialog` - Configure source and options
  - `BatchProgressDialog` - Monitor real-time progress

### Processing Flow
1. User selects source (database or files)
2. If files: Select audio files via file dialog
3. Configure processing options
4. Files are transcribed using selected STT provider
5. Transcripts saved to database
6. Documents generated via processing queue
7. Progress tracked in real-time

### Database Schema
- Migration 8 adds batch processing support:
  - `processing_queue` table with `batch_id` column
  - `batch_processing` table for batch metadata
  - Indexes for efficient batch queries

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
- **Unified Settings**: `src/ui/dialogs/unified_settings_dialog.py` - Tabbed Preferences dialog (Ctrl+,)
- **Menu Manager**: `src/ui/menu_manager.py` - Application menu bar with organized submenus
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
11. **src/ui/dialogs/translation_dialog.py**: Bidirectional translation implementation
12. **src/managers/translation_manager.py**: Translation provider management
13. **src/tts_providers/elevenlabs_tts.py**: ElevenLabs TTS with voice selection
14. **src/ai/rag_processor.py**: RAG tab N8N webhook integration
15. **src/ui/dialogs/unified_settings_dialog.py**: Unified Preferences dialog with 6 tabs
16. **src/ui/menu_manager.py**: Settings menu organization and creation

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
10. Check for threading issues during app shutdown (recordings refresh)

## Known Issues and Solutions

### Threading and Shutdown
- **Issue**: RuntimeError "main thread is not in main loop" during app shutdown
- **Solution**: Added checks for parent window existence in `_refresh_recordings_list` before UI updates
- **Location**: `src/ui/workflow_ui.py` - wrapped `self.parent.after()` calls in try-except blocks

### Translation Language Parsing
- **Issue**: Chinese language options "Chinese (Simplified)" and "Chinese (Traditional)" were parsed incorrectly
- **Solution**: Updated language code extraction to use `rfind('(')` to find the last parenthesis
- **Location**: `src/ui/dialogs/translation_dialog.py` - `_on_patient_language_change()` and `_on_doctor_language_change()`

### TTS Settings Dialog
- **Issue**: NameError when opening TTS settings due to lambda closure and widget reference issues
- **Solution**: Created widgets before function definitions and stored exception messages in variables
- **Location**: `src/ui/dialogs/dialogs.py` - TTS settings dialog creation

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
  - `menu_manager.py` - Application menu bar with organized submenus
  - `dialogs/` - All dialog windows
    - `unified_settings_dialog.py` - Tabbed Preferences dialog (Ctrl+,)
    - `medication_analysis_dialog.py` - Medication analysis options
    - `medication_results_dialog.py` - Medication results display
    - `translation_dialog.py` - Bidirectional translation assistant
    - `canned_responses_dialog.py` - Manage translation quick responses
    - `workflow_dialog.py` - Clinical workflow selection
    - `workflow_results_dialog.py` - Interactive workflow tracking
- `src/utils/` - Utility functions and helpers
- `src/translation/` - Translation providers
  - `base.py` - Base translation provider class
  - `deep_translator_provider.py` - Multi-backend translation support
- `src/tts_providers/` - Text-to-speech providers
  - `base.py` - Base TTS provider class
  - `elevenlabs_tts.py` - ElevenLabs TTS with voice selection