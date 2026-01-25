# Medical Assistant

[![Tests](https://github.com/cortexuvula/Medical-Assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/cortexuvula/Medical-Assistant/actions/workflows/tests.yml)
[![Build](https://github.com/cortexuvula/Medical-Assistant/actions/workflows/build.yml/badge.svg)](https://github.com/cortexuvula/Medical-Assistant/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Medical Assistant is a comprehensive desktop application for medical documentation, designed to transcribe and refine spoken medical notes. It leverages multiple AI providers (OpenAI, Anthropic/Claude, Google Gemini, and Ollama) with a modular architecture for efficient audio-to-text conversion, clinical note generation, and intelligent medical analysis.

## Table of Contents

- [Features](#features)
  - [Core Features](#core-features)
  - [Medical Documentation](#medical-documentation)
  - [AI Agents](#ai-agents)
  - [Referral & Address Book](#referral--address-book)
  - [Bidirectional Translation](#bidirectional-translation-assistant)
  - [AI & Transcription](#ai--transcription)
  - [Technical Features](#technical-features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Pre-built Releases](#pre-built-releases)
- [Building from Source](#building-from-source)
- [Usage Guide](#usage-guide)
- [Configuration](#configuration)
- [Security](#security)
- [Healthcare Standards](#healthcare-standards)
- [Architecture](#architecture)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Core Features

| Feature | Description |
|---------|-------------|
| **Workflow-Based Interface** | Modern task-oriented design with 5 main workflow tabs (Record, Process, Generate, Recordings, Chat) plus 6 text editor tabs |
| **Unified Preferences** | Comprehensive settings dialog (`Ctrl+,`) with tabbed interface for API keys, audio settings, AI models, prompts, and storage |
| **AI-Powered Chat** | ChatGPT-style interface with context-aware suggestions for interacting with your medical notes |
| **RAG Document Search** | Search your document database using local vector storage with markdown rendering |
| **Advanced Recording** | Record medical conversations with visual feedback, waveform display, timer, and pause/resume capabilities |
| **Real-Time Analysis** | Optional periodic analysis during recording generates differential diagnoses every 2 minutes |
| **Queue System** | Background processing queue with "Quick Continue Mode" for efficient multi-patient recording sessions |
| **Batch Processing** | Process multiple recordings or audio files at once with progress tracking and statistics |
| **Recordings Manager** | Dedicated tab with search, filter, and document status indicators (✓, —, 🔄, ❌) |

### Medical Documentation

- **Context-Aware SOAP Notes**
  - Side panel for adding previous medical information
  - Automatically integrates patient history into SOAP note generation
  - Smart context preservation during recordings

- **ICD Code Integration**
  - Choose between ICD-9, ICD-10, or both code versions
  - Automatic code suggestions based on diagnoses

- **Smart Templates**
  - Pre-built templates: Follow-up, New Patient, Telehealth, Emergency, Pediatric, Geriatric
  - Create and save custom context templates
  - Template import/export functionality

- **Multi-Format Document Generation**
  - SOAP notes with customizable sections
  - Professional referral letters
  - Patient correspondence
  - Employer/insurance documentation

### AI Agents

Medical Assistant includes specialized AI agents for different clinical tasks:

| Agent | Capabilities |
|-------|-------------|
| **Medication Analysis** | Extract medications from text, check drug-drug interactions with severity levels, validate dosing appropriateness, suggest alternatives, generate prescriptions |
| **Diagnostic Agent** | Analyze symptoms, generate differential diagnoses ranked by likelihood, provide ICD codes, suggest diagnostic workups |
| **Data Extraction** | Extract structured clinical data (vitals, labs, medications, diagnoses, allergies) from unstructured text |
| **Clinical Workflow** | Step-by-step guidance for patient intake, diagnostic workups, treatment protocols, and follow-up care with interactive checklists |
| **Referral Agent** | Generate professional referral letters with address book integration and specialty inference |
| **Synopsis Agent** | Generate concise SOAP note summaries for quick review |

### Referral & Address Book

- **Address Book Management:** Store and manage referral recipients (specialists, facilities, labs)
- **CSV Contact Import:** Bulk import contacts with field mapping
- **Searchable Recipients:** Quick search and selection when creating referrals
- **Smart Specialty Inference:** Automatically suggests appropriate specialists based on clinical content
- **Contact Categories:** Organize by specialty, facility type, or custom categories

### Bidirectional Translation Assistant

Real-time medical translation for multilingual patient consultations:

- **Real-time Translation:** Automatic translation as you type with smart debouncing
- **Speech-to-Text:** Record patient speech with automatic transcription
- **Text-to-Speech:** Play translated responses for patients with voice selection
- **Language Support:** 100+ languages with automatic detection
- **Canned Responses:** Customizable quick responses for common medical phrases organized by category
- **Conversation Export:** Save conversation transcripts for documentation

### AI & Transcription

#### LLM Providers (Modular Architecture)

| Provider | Models | Features |
|----------|--------|----------|
| **OpenAI** | GPT-4o, GPT-4o-mini, GPT-4 Turbo, GPT-3.5 Turbo | Streaming, function calling |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku, Claude 3.5 Haiku | Extended context, vision |
| **Google Gemini** | Gemini 2.0 Flash, Gemini 1.5 Pro, Gemini 1.5 Flash | Multimodal, long context |
| **Ollama** | Llama 3, Mistral, Qwen, CodeLlama, Phi-3, etc. | Local/offline, privacy-focused |

- **Intelligent Provider Routing:** Automatic fallback and provider selection based on model configuration
- **Streaming Support:** Real-time response streaming for faster perceived performance

#### Speech-to-Text Providers

| Provider | Model | Best For |
|----------|-------|----------|
| **Deepgram** | Nova-2 Medical | Medical terminology accuracy, HIPAA-eligible |
| **ElevenLabs** | Scribe v1 | High accuracy, speaker diarization |
| **Groq** | Whisper Large v3 Turbo | Speed (216x real-time), cost-effective |
| **Local Whisper** | Turbo | Offline capability, privacy |

#### Text-to-Speech

- **ElevenLabs Integration:** Multiple voice options with natural speech
- **Model Selection:** Flash v2.5 (ultra-low latency), Turbo v2.5, Multilingual v2
- **Offline Fallback:** pyttsx3 for offline TTS capability

### Technical Features

- **Secure API Key Storage:** Fernet encryption with machine-specific key derivation
- **Security Decorators:** Rate limiting, input sanitization, and secure API call wrappers
- **Database Storage:** SQLite with FTS5 full-text search, automatic migrations, and connection pooling
- **Resilient API Calls:** Circuit breaker pattern, exponential backoff, and automatic retry on transient failures
- **Export Functionality:** Export recordings and documents in PDF, DOCX, and text formats
- **FHIR Support:** Export clinical data in HL7 FHIR R4 format for healthcare interoperability
- **Performance Optimizations:** HTTP/2 support, connection pooling, latency optimizations (50-200ms savings per API call)
- **Cross-Platform:** Windows, macOS, and Linux with platform-specific optimizations
- **Modern UI/UX:** Built with Tkinter and ttkbootstrap featuring animations, visual indicators, dark/light themes

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/cortexuvula/Medical-Assistant.git
cd Medical-Assistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python main.py

# 4. Configure API keys via Settings → API Keys (keys are encrypted)
```

**Minimum Requirements:** At least one LLM provider API key (OpenAI, Anthropic, or Gemini) and one STT provider API key (Deepgram, ElevenLabs, or Groq).

---

## Installation

### Prerequisites

- **Python 3.10 or higher** (required for SDK compatibility)
- **FFmpeg** (for audio processing)

### Step-by-Step Installation

1. **Clone or Download the Repository**
   ```bash
   git clone https://github.com/cortexuvula/Medical-Assistant.git
   cd Medical-Assistant
   ```

2. **Create Virtual Environment (Recommended)**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API Keys**

   **Option A - Application Dialog (Recommended):**
   - Launch the application: `python main.py`
   - Go to Settings → API Keys
   - Enter your API keys (they are encrypted automatically)

   **Option B - Environment File:**
   Create a `.env` file in the project root:
   ```env
   # LLM Providers
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   GEMINI_API_KEY=AI...

   # Speech-to-Text Providers
   DEEPGRAM_API_KEY=...
   ELEVENLABS_API_KEY=...
   GROQ_API_KEY=gsk_...

   # Optional: Local Models
   OLLAMA_API_URL=http://localhost:11434

   # Optional: RAG Integration (Neon PostgreSQL with pgvector)
   NEON_DATABASE_URL=postgresql://user:pass@host/database?sslmode=require
   ```

5. **Install FFmpeg**

   | Platform | Command |
   |----------|---------|
   | **Windows** | `winget install FFmpeg` or download from [ffmpeg.org](https://ffmpeg.org) |
   | **macOS** | `brew install ffmpeg` |
   | **Ubuntu/Debian** | `sudo apt install ffmpeg` |
   | **Fedora** | `sudo dnf install ffmpeg` |

6. **Ollama Setup (Optional)**

   For local AI models without internet dependency:
   ```bash
   # Install Ollama from https://ollama.ai

   # Pull models
   ollama pull llama3
   ollama pull mistral
   ollama pull qwen2

   # Models are automatically detected by the application
   ```

---

## Pre-built Releases

Download pre-built executables from the [Releases](https://github.com/cortexuvula/Medical-Assistant/releases) page:

| Platform | File | Notes |
|----------|------|-------|
| **Windows** | `MedicalAssistant.exe` | Requires FFmpeg installation |
| **macOS** | `MedicalAssistant-macOS.zip` | FFmpeg bundled, may require security approval |
| **Linux** | `MedicalAssistant` | Requires system FFmpeg |

### Release Notes

- Executables include all Python dependencies
- API keys configured via the application's settings dialog
- First run may be slower due to antivirus scanning
- macOS users: Right-click → Open to bypass Gatekeeper on first run

---

## Building from Source

### Prerequisites

- Python 3.10+ with pip
- All dependencies: `pip install -r requirements.txt`

### Build Commands

**Windows:**
```batch
scripts\build_windows.bat
```

**macOS:**
```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

**Linux:**
```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

Executables are output to the `dist/` directory.

---

## Usage Guide

### Launching the Application

```bash
python main.py
```

### Main Workflow Tabs

#### 1. Record Tab
- **Start Recording:** Click the record button or press the keyboard shortcut
- **Visual Feedback:** Real-time waveform display and timer
- **Pause/Resume:** Pause recordings without losing progress
- **Advanced Analysis:** Enable checkbox for real-time differential diagnosis every 2 minutes
- **Microphone Selection:** Choose input device from dropdown

#### 2. Process Tab
- **Refine Text:** Clean up transcribed text with AI assistance
- **Improve Text:** Enhance clarity and medical terminology
- **Undo/Redo:** Full history with `Ctrl+Z` / `Ctrl+Y`
- **File Operations:** Save, export, and manage documents

#### 3. Generate Tab

| Button | Function |
|--------|----------|
| **SOAP Note** | Generate structured clinical notes with ICD-9/10 codes |
| **Referral** | Create professional referral letters with address book integration |
| **Letter** | Generate formal medical correspondence (patient, employer, insurance) |
| **Diagnostic Analysis** | Analyze symptoms and generate differential diagnoses |
| **Medication Analysis** | Extract medications, check interactions, validate dosing |
| **Extract Clinical Data** | Extract structured data (vitals, labs, medications) |
| **Clinical Workflow** | Step-by-step clinical process guidance |

#### 4. Recordings Tab
- **Search & Filter:** Find recordings by date, content, or status
- **Status Indicators:**
  - ✓ Documents generated
  - — Not yet processed
  - 🔄 Processing in progress
  - ❌ Error occurred
- **Batch Processing:** Select multiple recordings for bulk operations
- **Export:** Export recordings and documents in various formats

#### 5. Chat Tab
- **AI Chat Interface:** Ask questions about your notes or get clinical suggestions
- **Context-Aware:** Automatically uses current document as context
- **Quick Focus:** Press `Ctrl+/` to focus chat input

### Context Panel

The context panel provides additional information for SOAP note generation:

1. Click the **Context** button to open the side panel
2. Add previous medical history, current medications, allergies
3. Select from pre-built templates or create custom ones
4. Context is automatically integrated into SOAP note generation
5. Context persists during recording sessions

### Address Book

Manage referral recipients efficiently:

1. Access via **Tools → Manage Address Book**
2. Add specialists, facilities, and labs with contact details
3. Import contacts from CSV: **Tools → Import Contacts from CSV**
4. Quick search when creating referrals
5. Automatic specialty inference from clinical content

### Translation Assistant

For multilingual patient consultations:

1. Access via **Tools → Translation Assistant**
2. Select patient and doctor languages from dropdowns
3. **Record Patient Speech:** Click microphone to record, transcribes automatically
4. **Type Responses:** Real-time translation as you type
5. **Play Translation:** Click speaker icon for TTS playback
6. **Canned Responses:** Use quick responses for common phrases
7. **Export:** Save conversation transcript

### RAG Document Search

Query your document database:

1. Navigate to the **RAG** tab
2. Enter your search query
3. Results rendered in markdown format
4. Copy responses with the copy button
5. Session persistence for follow-up queries

---

## Configuration

### Unified Preferences (Ctrl+,)

Access all settings through the comprehensive Preferences dialog:

| Tab | Settings |
|-----|----------|
| **API Keys** | All LLM keys (OpenAI, Anthropic, Gemini, Grok) and STT keys (Deepgram, ElevenLabs, Groq) |
| **Audio & STT** | Provider settings (ElevenLabs, Deepgram, Groq), TTS voice selection, audio quality |
| **AI Models** | Temperature settings per task, model selection, translation provider configuration |
| **Prompts** | Customize Refine, Improve, SOAP, Referral, and Advanced Analysis prompts |
| **Storage** | Default folder, Custom Vocabulary, Address Book management, Prefix Audio |
| **General** | Quick Continue Mode, Theme selection, Sidebar preferences, Keyboard shortcuts |

### Settings Menu Structure

```
Settings
├── Preferences...              [Ctrl+,]
├── ─────────────
├── Update API Keys             [Quick access]
├── ─────────────
├── Audio & Transcription ▸
│   ├── ElevenLabs Settings
│   ├── Deepgram Settings
│   ├── Groq Settings
│   └── TTS Settings
├── AI & Models ▸
│   ├── Temperature Settings
│   ├── Agent Settings
│   ├── Translation Settings
│   └── MCP Tools
├── Prompt Settings ▸
│   ├── Refine Prompt Settings
│   ├── Improve Prompt Settings
│   ├── SOAP Note Settings
│   ├── Referral Settings
│   └── Advanced Analysis Settings
├── Data & Storage ▸
│   ├── Custom Vocabulary
│   ├── Manage Address Book...
│   ├── Import Contacts from CSV...
│   ├── Set Storage Folder
│   └── Record Prefix Audio
├── ─────────────
├── Export Prompts
├── Import Prompts
├── ─────────────
├── Quick Continue Mode         [Toggle]
└── Toggle Theme                [Alt+T]
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+,` / `Cmd+,` | Open Preferences dialog |
| `Ctrl+/` / `Cmd+/` | Focus chat input |
| `Ctrl+N` / `Cmd+N` | New session |
| `Ctrl+S` / `Cmd+S` | Save |
| `Ctrl+Z` / `Cmd+Z` | Undo |
| `Ctrl+Y` / `Cmd+Shift+Z` | Redo |
| `Ctrl+E` / `Cmd+E` | Export as PDF |
| `Ctrl+D` / `Cmd+D` | Run Diagnostic Analysis |
| `Alt+T` | Toggle dark/light theme |

See [SHORTCUTS.md](SHORTCUTS.md) for the complete list.

---

## Security

### API Key Protection

- **Encrypted Storage:** API keys are encrypted using Fernet symmetric encryption
- **Machine-Specific Keys:** Encryption keys are derived from machine-specific identifiers
- **No Plaintext Storage:** Keys are never stored in plaintext on disk
- **Memory Protection:** Keys are cleared from memory when not in use

### Security Features

- **Rate Limiting:** Built-in rate limiting for API calls to prevent abuse
- **Input Sanitization:** All user inputs are sanitized before processing
- **Secure API Wrappers:** Decorators ensure secure handling of API calls
- **No Data Transmission:** Patient data is only sent to configured AI providers
- **Local Processing Options:** Use Ollama for completely offline operation

### Best Practices

1. Use the in-app API key dialog (encrypted) rather than `.env` files
2. Keep API keys confidential and rotate them periodically
3. Use local Whisper or Ollama for sensitive data when possible
4. Review provider privacy policies for HIPAA compliance requirements

---

## Healthcare Standards

### FHIR R4 Support

Medical Assistant supports HL7 FHIR R4 for healthcare interoperability:

- **Export to FHIR:** File → Export → Export as FHIR...
- **Clipboard Export:** File → Export → Export FHIR to Clipboard
- **Supported Resources:**
  - Patient
  - Encounter
  - Condition (diagnoses)
  - Observation (vitals, labs)
  - MedicationStatement
  - DocumentReference (SOAP notes)

### ICD Code Support

- **ICD-9:** Legacy code support for historical records
- **ICD-10:** Current standard with automatic suggestions
- **Dual Coding:** Generate both ICD-9 and ICD-10 codes simultaneously

---

## Architecture

### Project Structure

```
Medical-Assistant/
├── main.py                    # Application entry point
├── src/
│   ├── ai/                    # AI providers and processors
│   │   ├── agents/           # Specialized AI agents
│   │   │   ├── base.py       # Base agent class
│   │   │   ├── medication.py # Medication analysis
│   │   │   ├── diagnostic.py # Diagnostic suggestions
│   │   │   ├── workflow.py   # Clinical workflows
│   │   │   ├── synopsis.py   # SOAP summaries
│   │   │   └── models.py     # Pydantic data models
│   │   ├── providers/        # Modular AI provider implementations
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   ├── gemini_provider.py
│   │   │   ├── ollama_provider.py
│   │   │   └── router.py     # Intelligent provider routing
│   │   ├── ai_processor.py   # Core AI processing logic
│   │   ├── soap_generation.py
│   │   ├── letter_generation.py
│   │   ├── text_processing.py
│   │   └── rag_processor.py  # RAG local integration
│   ├── audio/                 # Audio recording and processing
│   │   ├── audio.py          # Main audio handler
│   │   ├── recording_manager.py
│   │   └── periodic_analysis.py
│   ├── core/                  # Application core
│   │   ├── app.py            # Main application class
│   │   ├── app_initializer.py
│   │   └── config.py
│   ├── database/              # Data persistence
│   │   ├── db_manager.py     # Database operations
│   │   ├── db_migrations.py  # Schema migrations
│   │   └── db_pool.py        # Connection pooling
│   ├── managers/              # Singleton managers
│   │   ├── agent_manager.py
│   │   ├── api_key_manager.py
│   │   └── translation_manager.py
│   ├── processing/            # Document processing
│   │   ├── document_generators.py
│   │   └── processing_queue.py
│   ├── stt_providers/         # Speech-to-text
│   │   ├── base.py
│   │   ├── deepgram.py
│   │   ├── elevenlabs.py
│   │   ├── groq.py
│   │   └── whisper.py
│   ├── tts_providers/         # Text-to-speech
│   │   ├── base.py
│   │   └── elevenlabs_tts.py
│   ├── translation/           # Translation providers
│   │   ├── base.py
│   │   └── deep_translator_provider.py
│   ├── ui/                    # User interface
│   │   ├── workflow_ui.py    # Main UI orchestration
│   │   ├── chat_ui.py        # Chat interface
│   │   ├── menu_manager.py   # Application menus
│   │   ├── theme_manager.py  # Theme handling
│   │   ├── dialogs/          # All dialog windows
│   │   └── components/       # Reusable UI components
│   └── utils/                 # Utilities
│       ├── security.py       # Encryption, key storage
│       ├── security_decorators.py
│       ├── resilience.py     # Circuit breaker, retry
│       └── validators.py
├── config/                    # Configuration files
├── tests/                     # Test suites
│   ├── unit/
│   ├── integration/
│   └── regression/
└── scripts/                   # Build scripts
```

### Key Design Patterns

| Pattern | Usage |
|---------|-------|
| **Provider Pattern** | All AI, STT, and TTS providers inherit from base classes for consistent interfaces |
| **Singleton Managers** | Agent, translation, and API key managers ensure single instances |
| **Circuit Breaker** | Resilient API calls with automatic failure detection and recovery |
| **Security Decorators** | Rate limiting and input sanitization applied via decorators |
| **Migration System** | Database schema evolution with versioned migrations |
| **Observer Pattern** | UI updates via event-driven architecture |
| **Queue System** | Background processing with priority and status tracking |

### Data Flow

```
Audio Input → STT Provider → Transcript → AI Processing → Document Generation
                                              ↓
                                        Agent System
                                              ↓
                                     Database Storage → Export (PDF/DOCX/FHIR)
```

---

## Testing

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests with pytest
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test suites
pytest tests/unit/
pytest tests/integration/
pytest tests/regression/

# Run specific test files
pytest tests/unit/test_db_migrations.py
pytest tests/unit/test_processing_queue.py
```

### Test Categories

| Suite | Purpose |
|-------|---------|
| **Unit Tests** | Test individual components in isolation |
| **Integration Tests** | Test component interactions |
| **Regression Tests** | Ensure fixes don't break existing functionality |

### CI/CD

The project uses GitHub Actions for continuous integration:

- **Tests Workflow:** Runs on every push and PR across Windows, macOS, and Linux
- **Build Workflow:** Builds executables for all platforms
- **CodeQL:** Security scanning for vulnerabilities

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **API Connection Errors** | Verify API keys in Settings → API Keys. Check internet connection. |
| **Audio Not Recording** | Check microphone permissions. Verify FFmpeg installation. Select correct input device. |
| **Transcription Errors** | Try a different STT provider. Check audio quality. Ensure API key is valid. |
| **Ollama Timeouts** | Use smaller model variants. Check system resources. Increase timeout in settings. |
| **Queue Stuck** | Check logs via Help → View Logs. Restart application if needed. |
| **Theme Not Changing** | Restart application after theme change for full effect. |
| **Export Failures** | Check write permissions for output directory. Ensure sufficient disk space. |

### Getting Help

- **Application Logs:** Help → View Logs → View Log Contents
- **Log Location:** Help → View Logs → Open Logs Folder
- **GitHub Issues:** [Report bugs or request features](https://github.com/cortexuvula/Medical-Assistant/issues)

### Debug Mode

For detailed logging, set the environment variable:
```bash
export LOG_LEVEL=DEBUG  # Linux/macOS
set LOG_LEVEL=DEBUG     # Windows
```

---

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Operating System** | Windows 10, macOS 10.14, Ubuntu 20.04 | Windows 11, macOS 13+, Ubuntu 22.04 |
| **Python** | 3.10 | 3.11+ |
| **Memory** | 4GB RAM | 8GB RAM |
| **Storage** | 500MB | 1GB+ for recordings |
| **Internet** | Required for cloud AI | Optional with Ollama |
| **Audio** | Any microphone | USB condenser microphone |

---

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Make** your changes with clear commit messages
4. **Run** tests: `pytest`
5. **Push** to your fork: `git push origin feature/amazing-feature`
6. **Submit** a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/Medical-Assistant.git
cd Medical-Assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests to verify setup
pytest
```

---

## Documentation

- [Keyboard Shortcuts](SHORTCUTS.md)
- [Desktop Shortcuts](DESKTOP_SHORTCUTS.md) - Creating application shortcuts
- [Security Features](docs/security_features.md)
- [Agent System](docs/agent_system.md)
- [Medication Agent](docs/medication_agent.md)
- [Testing Guide](docs/testing_guide.md)
- [CLAUDE.md](CLAUDE.md) - Development guide for AI assistants

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

---

## Acknowledgments

- [OpenAI](https://openai.com) - GPT models
- [Anthropic](https://anthropic.com) - Claude models
- [Google AI](https://ai.google.dev) - Gemini models
- [Deepgram](https://deepgram.com) - Speech-to-text
- [ElevenLabs](https://elevenlabs.io) - Text-to-speech and STT
- [Groq](https://groq.com) - Fast inference
- [Ollama](https://ollama.ai) - Local model hosting
- [ttkbootstrap](https://ttkbootstrap.readthedocs.io) - Modern UI themes

---

<p align="center">
  Made with care for healthcare professionals
</p>
