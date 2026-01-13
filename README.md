# Medical Assistant

Medical Assistant is a desktop application designed to transcribe and refine spoken medical notes. It leverages advanced AI APIs (OpenAI, Anthropic/Claude, Google Gemini, and Ollama) and offers efficient audio-to-text conversion and note generation with context-aware capabilities.

## Features

### Core Features
- **Workflow-Based Interface:** Modern task-oriented design with 5 main workflow tabs (Record, Process, Generate, Recordings, Chat) plus 6 text editor tabs
- **AI-Powered Chat Interface:** ChatGPT-style interface with context-aware suggestions for interacting with your medical notes
- **RAG Document Search:** RAG tab enables searching your document database via N8N webhook integration with markdown rendering
- **Advanced Recording System:** Record medical conversations with visual feedback, timer display, and pause/resume capabilities
- **Real-Time Analysis:** Optional periodic analysis during recording generates differential diagnoses every 2 minutes
- **Queue System:** Background processing queue with "Quick Continue Mode" for efficient multi-patient recording sessions
- **Dedicated Recordings Manager:** Recordings tab with search, filter, and document status indicators (✓, —, 🔄, ❌)

### Medical Documentation
- **Context-Aware SOAP Notes:** Side panel for adding previous medical information that automatically integrates into SOAP note generation
- **ICD Code Options:** Choose between ICD-9, ICD-10, or both code versions in SOAP notes
- **Smart Templates:** Pre-built and custom context templates for common scenarios (Follow-up, New Patient, Telehealth, etc.)
- **Multi-Format Document Generation:** Create SOAP notes, referral letters, and custom medical documents
- **Smart Context Preservation:** Context information is preserved during SOAP recordings and only cleared on new sessions or manual clearing

### AI Agents
- **Medication Analysis Agent:** Comprehensive medication analysis including extraction, interaction checking, dosing validation, and prescription generation
- **Diagnostic Agent:** Analyze symptoms and generate differential diagnoses with ICD codes
- **Data Extraction Agent:** Extract structured clinical data (vitals, labs, medications, diagnoses) from unstructured text
- **Clinical Workflow Agent:** Step-by-step guidance for patient intake, diagnostic workups, treatment protocols, and follow-up care
- **Referral Agent:** Generate professional referral letters with address book integration
- **Synopsis Agent:** Generate concise SOAP note summaries

### Referral & Address Book
- **Address Book Management:** Store and manage referral recipients (specialists, facilities, labs)
- **CSV Contact Import:** Bulk import contacts from CSV files
- **Searchable Recipients:** Quick search and selection when creating referrals
- **Smart Specialty Inference:** Automatically suggests appropriate specialists based on clinical content

### Bidirectional Translation Assistant
- **Real-time Translation:** Automatic translation as user types with debouncing
- **Speech-to-Text:** Record patient speech with automatic transcription
- **Text-to-Speech:** Play translated responses for patients
- **Language Support:** 100+ languages with automatic detection
- **Canned Responses:** Customizable quick responses for common medical phrases
- **Export:** Save conversation transcripts

### AI & Transcription
- **Multiple AI Providers:**
  - OpenAI (GPT-4, GPT-4o, GPT-3.5)
  - Anthropic (Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku)
  - Google Gemini (Gemini Pro, Gemini Flash)
  - Ollama (Local models - Llama, Mistral, etc.)
- **Multiple STT Providers:**
  - Deepgram (Nova-2 Medical model)
  - ElevenLabs (Scribe v1)
  - Groq (Whisper Large v3 Turbo - 216x real-time)
  - Local Whisper (Turbo model)
- **Text-to-Speech:** ElevenLabs integration with voice selection and Flash v2.5 model for ultra-low latency
- **Customizable Prompts:** Edit and import/export prompts and models for text refinement and note generation

### Technical Features
- **Secure API Key Storage:** Encrypted storage with Fernet encryption and machine-specific key derivation
- **Database Storage:** SQLite with FTS5 full-text search, automatic migrations, and connection pooling
- **Export Functionality:** Export recordings and documents in various formats
- **Performance Optimizations:** HTTP/2 support, connection pooling, and latency optimizations
- **Cross-Platform Support:** Available for Windows, macOS, and Linux with platform-specific optimizations
- **Modern UI/UX:** Built with Tkinter and ttkbootstrap featuring animations, visual indicators, and responsive design

## Installation

### Prerequisites
- Python 3.10 or higher (required for SDK compatibility)
- FFmpeg (for audio processing)

1. **Clone or Download the Repository**
   ```bash
   git clone https://github.com/cortexuvula/Medical-Assistant.git
   cd Medical-Assistant
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**
   - Use the "API Keys" dialog in the application (recommended - keys are encrypted)
   - Or create a `.env` file in the project root:
     - **LLM Services:** `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
     - **Speech-to-Text Services:** `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, `GROQ_API_KEY`
     - **Local Models:** `OLLAMA_API_URL` (defaults to "http://localhost:11434")
     - **RAG Integration:** `N8N_URL` and `N8N_AUTHORIZATION_SECRET` for document search
   - **Minimum Requirements:** You need at least one LLM provider and one STT provider to use the application.

4. **Ollama Setup (Optional)**
   To use local AI models:
   - Install Ollama from [ollama.ai](https://ollama.ai)
   - Pull models using `ollama pull <model_name>` (e.g., `ollama pull llama3`)
   - The application will automatically detect available models

5. **FFmpeg Installation**
   - **Windows:** Download from [ffmpeg.org](https://ffmpeg.org) or use `winget install FFmpeg`
   - **macOS:** `brew install ffmpeg`
   - **Linux:** `sudo apt install ffmpeg` (Ubuntu/Debian) or `sudo dnf install ffmpeg` (Fedora)

## Pre-built Releases

Download pre-built executables from the [Releases](https://github.com/cortexuvula/Medical-Assistant/releases) page:

- **Windows:** `MedicalAssistant.exe`
- **macOS:** `MedicalAssistant-macOS.zip`
- **Linux:** `MedicalAssistant`

### Notes
- The executable includes all Python dependencies
- FFmpeg must be installed separately (except on macOS where it's bundled)
- API keys can be configured via the application's settings dialog
- First run may be slower as antivirus software scans the executable

## Building from Source

### Prerequisites
- Python 3.10+ with pip
- All dependencies installed: `pip install -r requirements.txt`

### Building

**Windows:**
```batch
scripts\build_windows.bat
```

**macOS:**
```bash
./scripts/build_macos.sh
```

**Linux:**
```bash
./scripts/build_linux.sh
```

Executables are output to the `dist/` directory.

## Usage

### Launching the Application
```bash
python main.py
```

### Main Workflow Tabs

1. **Record Tab**
   - Start/stop recordings with visual feedback and timer display
   - Pause/resume capabilities
   - Enable "Advanced Analysis" for real-time differential diagnosis every 2 minutes
   - Select microphone and audio settings

2. **Process Tab**
   - Refine and improve transcribed text with AI assistance
   - Undo/redo functionality
   - File operations (save, export)

3. **Generate Tab**
   - **SOAP Note:** Generate structured clinical notes with ICD-9/10 codes
   - **Referral:** Create professional referral letters with address book integration
   - **Letter:** Generate formal medical correspondence
   - **Diagnostic Analysis:** Analyze symptoms and generate differential diagnoses
   - **Medication Analysis:** Extract medications, check interactions, validate dosing
   - **Extract Clinical Data:** Extract structured data (vitals, labs, medications)
   - **Clinical Workflow:** Step-by-step clinical process guidance

4. **Recordings Tab**
   - View, search, and manage all saved recordings
   - Document status indicators: ✓ (generated), — (not generated), 🔄 (in progress), ❌ (error)
   - Batch processing for multiple recordings
   - Export and delete functionality

5. **Chat Tab**
   - AI-powered chat interface for interacting with your notes
   - Context-aware suggestions based on current content
   - Press `Ctrl+/` (or `Cmd+/` on Mac) to quickly focus chat

### Context Panel
- Click "Context" button to open the collapsible side panel
- Add previous medical information for SOAP note generation
- Use pre-built templates or create custom ones
- Context is preserved during recordings

### Address Book
- Access via Tools → Manage Address Book
- Add, edit, and delete referral recipients
- Import contacts from CSV files
- Quick search when creating referrals

### Translation Assistant
- Access via Tools → Translation Assistant
- Select patient and doctor languages
- Record patient speech for transcription
- Play translated responses via TTS
- Use canned responses for common phrases

### RAG Document Search
- Navigate to the RAG tab
- Query your document database via N8N webhook
- Markdown-formatted responses with copy functionality
- Session persistence for continuous conversations

## Configuration

### Settings Menu
- **API Keys:** Securely store and manage API keys (encrypted)
- **Prompt Settings:** Customize prompts for each document type
- **Audio Settings:** Configure microphone, sample rate, and audio processing
- **Provider Settings:** Configure individual STT/TTS provider options
- **ICD Code Version:** Choose ICD-9, ICD-10, or both for SOAP notes

### Keyboard Shortcuts
- `Ctrl+/` / `Cmd+/` - Focus chat input
- `Ctrl+Z` / `Cmd+Z` - Undo
- `Ctrl+Y` / `Cmd+Shift+Z` - Redo
- `Ctrl+S` / `Cmd+S` - Save
- See [SHORTCUTS.md](SHORTCUTS.md) for complete list

## Troubleshooting

### Common Issues

- **API Connection Errors:** Verify API keys in Settings → API Keys
- **Audio Issues:** Check microphone permissions and FFmpeg installation
- **Ollama Timeouts:** Use smaller model variants or check system resources
- **Queue Stuck:** Check logs via Help → View Logs

### Getting Help
- **Application Logs:** Help → View Logs
- **GitHub Issues:** [Report bugs or request features](https://github.com/cortexuvula/Medical-Assistant/issues)

## System Requirements

- **Operating System:** Windows 10+, macOS 10.14+, or Linux (Ubuntu 20.04+)
- **Python:** 3.10+ (for running from source)
- **Memory:** 4GB RAM minimum, 8GB recommended
- **Storage:** 500MB free space
- **Internet:** Required for cloud AI services (optional for local Ollama models)
- **Audio:** Microphone for speech-to-text functionality

## Documentation

- [User Guide](docs/user_guide.md)
- [Keyboard Shortcuts](SHORTCUTS.md)
- [Security Features](docs/security_features.md)
- [Testing Guide](docs/testing_guide.md)
- [CLAUDE.md](CLAUDE.md) - Development guide

## Testing

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test suites
pytest tests/unit/
pytest tests/integration/
```

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests to ensure they pass
5. Submit a Pull Request

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## Acknowledgments

- [OpenAI](https://openai.com) - GPT models
- [Anthropic](https://anthropic.com) - Claude models
- [Google](https://ai.google.dev) - Gemini models
- [Deepgram](https://deepgram.com) - Speech-to-text
- [ElevenLabs](https://elevenlabs.io) - Text-to-speech and STT
- [Groq](https://groq.com) - Fast inference
- [Ollama](https://ollama.ai) - Local model hosting
