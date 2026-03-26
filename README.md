# Medical Assistant

[![Tests](https://github.com/cortexuvula/Medical-Assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/cortexuvula/Medical-Assistant/actions/workflows/tests.yml)
[![Build](https://github.com/cortexuvula/Medical-Assistant/actions/workflows/build.yml/badge.svg)](https://github.com/cortexuvula/Medical-Assistant/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Medical Assistant is a comprehensive desktop application for medical documentation, designed to transcribe and refine spoken medical notes. It leverages multiple AI providers (OpenAI, Anthropic/Claude, Google Gemini, Groq, Cerebras, and Ollama) with a modular, mixin-based architecture (~150K LOC across 400+ modules) for efficient audio-to-text conversion, clinical note generation, and intelligent medical analysis.

## Table of Contents

- [Features](#features)
  - [Core Features](#core-features)
  - [Medical Documentation](#medical-documentation)
  - [AI Agents](#ai-agents)
  - [RAG & Knowledge Graph](#rag--knowledge-graph)
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
| **RAG Document Search** | Hybrid vector + keyword search with medical query expansion, adaptive thresholds, and MMR diversity |
| **Knowledge Graph** | Interactive visualization of medical entities and relationships from Neo4j |
| **RSVP Reader** | Speed-reading interface for SOAP notes with ORP highlighting and section navigation |
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
  - Voice emotion analysis integration (when using Modulate STT) — patient emotional state woven into Subjective section

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
| **Compliance Agent** | Audit SOAP notes against clinical documentation standards, flag missing elements, score completeness |
| **Data Extraction** | Extract structured clinical data (vitals, labs, medications, diagnoses, allergies) from unstructured text |
| **Clinical Workflow** | Step-by-step guidance for patient intake, diagnostic workups, treatment protocols, and follow-up care with interactive checklists |
| **Referral Agent** | Generate professional referral letters with address book integration and specialty inference |
| **Synopsis Agent** | Generate concise SOAP note summaries for quick review |
| **Chat Agent** | Conversational AI with tool use for document editing, context-aware responses |

### Referral & Address Book

- **Address Book Management:** Store and manage referral recipients (specialists, facilities, labs)
- **CSV Contact Import:** Bulk import contacts with field mapping
- **Searchable Recipients:** Quick search and selection when creating referrals
- **Smart Specialty Inference:** Automatically suggests appropriate specialists based on clinical content
- **Contact Categories:** Organize by specialty, facility type, or custom categories

### RAG & Knowledge Graph

- **Hybrid Search:** Combines vector similarity (pgvector), BM25 keyword search, and knowledge graph traversal with configurable weights
- **Medical Query Expansion:** Automatic expansion of medical abbreviations (HTN, COPD, MI) and synonyms for better recall
- **Adaptive Thresholds:** Dynamically adjusts similarity cutoffs based on query length and score distribution
- **MMR Reranking:** Maximal Marginal Relevance ensures diverse, non-redundant results
- **Knowledge Graph Visualization:** Interactive pan/zoom/drag graph canvas showing entities (medications, conditions, procedures) and relationships from Neo4j
- **Clinical Guidelines:** Upload and search clinical guideline PDFs with chunking, OCR support, and recommendation extraction
- **Streaming Responses:** Progressive result display with cancellation support
- **Conversation Context:** Semantic follow-up detection maintains context across queries

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
| **OpenAI** | GPT-4o, GPT-4o-mini, GPT-4 Turbo | Streaming, function calling, dynamic model fetch |
| **Anthropic** | Claude Opus 4, Claude Sonnet 4, Claude Haiku 4 | Extended context, dynamic model fetch |
| **Google Gemini** | Gemini 2.0 Flash, Gemini 1.5 Pro, Gemini 1.5 Flash | Multimodal, long context, dynamic model fetch |
| **Groq** | Llama 3.3 70B, Mixtral 8x7B, Gemma2 9B | Ultra-fast inference, dynamic model fetch |
| **Cerebras** | Llama 3.3 70B, Qwen 3 32B | Wafer-scale inference, dynamic model fetch |
| **Ollama** | Llama 3, Mistral, Qwen, Phi-3, etc. | Local/offline, privacy-focused, auto-detect |

- **Intelligent Provider Routing:** Automatic fallback and provider selection based on model configuration
- **Dynamic Model Lists:** Models fetched from provider APIs with TTL caching (1 hour) and fallback lists
- **Streaming Support:** Real-time response streaming for faster perceived performance

#### Speech-to-Text Providers

| Provider | Model | Best For |
|----------|-------|----------|
| **Deepgram** | Nova-2 Medical | Medical terminology accuracy, HIPAA-eligible |
| **ElevenLabs** | Scribe v2 | High accuracy, speaker diarization, entity detection, keyterm prompting |
| **Groq** | Whisper Large v3 Turbo | Speed (216x real-time), cost-effective |
| **Modulate (Velma)** | Velma Transcribe | Voice emotion detection (20+ emotions), speaker diarization, deepfake detection, PII/PHI redaction |
| **Local Whisper** | Turbo | Offline capability, privacy |

#### Text-to-Speech

- **ElevenLabs Integration:** Multiple voice options with natural speech
- **Model Selection:** Flash v2.5 (ultra-low latency), Turbo v2.5, Multilingual v2
- **Offline Fallback:** pyttsx3 for offline TTS capability

### Technical Features

- **Mixin-Based Architecture:** Large classes decomposed into focused mixins (AudioHandler: 5 mixins, ProcessingQueue: 3 mixins, RagProcessor: 4 mixins) with Protocol contracts
- **Type Safety:** TypedDict definitions for processing queue tasks, chat context, and guideline batches; runtime-checkable AppProtocol for mixin boundaries
- **Secure API Key Storage:** Fernet encryption with PBKDF2 key derivation, per-installation salt, machine-specific keys, legacy salt migration
- **Security Decorators:** Rate limiting, input sanitization with prompt injection detection, and secure API call wrappers
- **PHI Redaction:** Automatic redaction of 60+ sensitive field types in application logs and audit trail
- **Audit Logging:** Append-only HIPAA-compliant audit log tracking API key access, data exports, and recording operations
- **Database Storage:** SQLite with FTS5 full-text search, versioned migrations (8+ versions), connection pooling with health checks
- **Resilient API Calls:** Circuit breaker pattern, exponential backoff, automatic retry, and STT provider failover chain
- **Export Functionality:** Export recordings and documents in PDF, DOCX, and text formats
- **FHIR Support:** Export clinical data in HL7 FHIR R4 format (Patient, Encounter, Condition, Observation, MedicationStatement, DocumentReference)
- **Performance Optimizations:** HTTP/2 support, connection pooling, thread pool executors, background processing queue with priority scheduling
- **Import Guards:** Optional dependencies (pygame, soundcard, fhir.resources, docx, reportlab) guarded with availability flags
- **Cross-Platform:** Windows, macOS, and Linux with platform-specific optimizations
- **Comprehensive Test Suite:** 1,850+ tests (unit + integration) with 50%+ critical path coverage
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

**Minimum Requirements:** At least one LLM provider API key (OpenAI, Anthropic, Gemini, Groq, or Cerebras) and one STT provider API key (Deepgram, ElevenLabs, Groq, or Modulate). Local Whisper and Ollama work without API keys.

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
   GROQ_API_KEY=gsk_...
   CEREBRAS_API_KEY=csk-...

   # Speech-to-Text Providers
   DEEPGRAM_API_KEY=...
   ELEVENLABS_API_KEY=...
   MODULATE_API_KEY=...

   # Optional: Local Models
   OLLAMA_API_URL=http://localhost:11434

   # Optional: RAG Integration
   NEON_DATABASE_URL=postgresql://user:pass@host/database?sslmode=require

   # Optional: Knowledge Graph
   NEO4J_BOLT_URL=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=...
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

Query your document database with hybrid search:

1. Navigate to the **RAG** tab
2. Enter your search query (medical abbreviations are automatically expanded)
3. Results rendered in markdown with source attribution
4. Copy responses with the copy button
5. Follow-up queries maintain conversation context
6. Click **Knowledge Graph** to visualize entity relationships
7. Upload clinical guidelines via the **Guidelines** tab for searchable reference

---

## Configuration

### Unified Preferences (Ctrl+,)

Access all settings through the comprehensive Preferences dialog:

| Tab | Settings |
|-----|----------|
| **API Keys** | All LLM keys (OpenAI, Anthropic, Gemini, Groq, Cerebras) and STT keys (Deepgram, ElevenLabs, Groq, Modulate) |
| **Audio & STT** | Provider settings (ElevenLabs, Deepgram, Groq, Modulate), TTS voice selection, audio quality |
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
│   ├── Modulate Settings
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

- **Fernet Encryption:** API keys encrypted at rest using `cryptography` library with PBKDF2 (100K iterations)
- **Per-Installation Salt:** Unique 256-bit salt per installation (stored in `salt.bin`)
- **Machine-Specific Keys:** Encryption keys derived from machine identifiers (machine-id, filesystem UUID)
- **Legacy Migration:** Automatic migration from old static salt to per-install salt with version tracking
- **No Plaintext Storage:** Keys are never stored in plaintext on disk

### Security Features

- **Rate Limiting:** Per-provider rate limiting with configurable limits (e.g., 60 calls/minute for Anthropic)
- **Input Sanitization:** Prompt injection detection with optional strict mode that rejects dangerous content
- **API Key Validation:** Format validation with regex patterns for known provider key formats (OpenAI, Anthropic, Groq, Cerebras, Gemini)
- **PHI Redaction:** 60+ sensitive field types automatically redacted in application logs
- **Audit Logging:** Append-only audit trail tracking sensitive operations (API key access, data exports)
- **Database Protection:** POSIX 0600 permissions and Windows ACL enforcement on database files
- **Path Traversal Protection:** File paths validated after resolution to prevent encoded traversal attacks
- **Secure HTTP:** Explicit TLS verification on all HTTPS clients via centralized client manager
- **No Data Transmission:** Patient data only sent to configured AI providers
- **Local Processing Options:** Use Ollama + local Whisper for completely offline operation

### Best Practices

1. Use the in-app API key dialog (encrypted) rather than `.env` files
2. Keep API keys confidential and rotate them periodically
3. Use local Whisper or Ollama for sensitive data when possible
4. Review provider privacy policies for HIPAA compliance requirements
5. Monitor the audit log (`audit.log`) for unexpected access patterns

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
├── src/                       # ~150K LOC across 400+ modules
│   ├── ai/                    # AI providers and processors
│   │   ├── agents/            # 10 specialized AI agents
│   │   │   ├── base.py        # Base agent with caching, validation
│   │   │   ├── medication.py  # Drug interactions, dosing
│   │   │   ├── diagnostic.py  # Differential diagnosis
│   │   │   ├── compliance.py  # Documentation audit
│   │   │   ├── workflow.py    # Clinical workflows
│   │   │   ├── chat.py        # Conversational with tool use
│   │   │   └── models.py      # AgentConfig, AgentTask, AgentResponse
│   │   ├── providers/         # Modular AI provider implementations
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   ├── gemini_provider.py
│   │   │   ├── groq_provider.py
│   │   │   ├── cerebras_provider.py
│   │   │   ├── ollama_provider.py
│   │   │   └── router.py      # Intelligent provider routing
│   │   ├── ai_processor.py    # Core AI processing logic
│   │   ├── chat_processor.py  # Chat with TypedDict context
│   │   ├── rag_processor.py   # RAG facade (4 mixins)
│   │   ├── rag_query.py       # RagQueryMixin
│   │   ├── rag_response.py    # RagResponseMixin
│   │   ├── rag_ui.py          # RagUIMixin
│   │   └── rag_feedback.py    # RagFeedbackMixin
│   ├── audio/                  # Audio recording and processing
│   │   ├── audio.py           # AudioHandler facade (5 mixins)
│   │   ├── mixins/            # Decomposed audio functionality
│   │   │   ├── transcription_mixin.py
│   │   │   ├── recording_mixin.py
│   │   │   ├── processing_mixin.py
│   │   │   ├── device_mixin.py
│   │   │   └── file_mixin.py
│   │   ├── recording_manager.py
│   │   └── periodic_analysis.py
│   ├── core/                   # Application core
│   │   ├── app.py             # Main application class
│   │   ├── protocols.py       # AppProtocol for mixin contracts
│   │   ├── app_initializer.py
│   │   ├── env_schema.py      # 35 env vars documented
│   │   └── config.py
│   ├── database/               # Data persistence
│   │   ├── database.py        # Database with file-level security
│   │   ├── db_migrations.py   # 8+ versioned schema migrations
│   │   ├── db_pool.py         # Connection pooling with health checks
│   │   └── mixins/            # Query mixins (recordings, queue, diagnostics)
│   ├── exporters/              # Document export
│   │   ├── fhir_exporter.py   # HL7 FHIR R4
│   │   ├── docx_exporter.py   # Word documents
│   │   └── rag_exporter.py    # RAG document export
│   ├── managers/               # Singleton managers
│   │   ├── agent_manager.py
│   │   ├── api_key_manager.py
│   │   └── translation_manager.py
│   ├── processing/             # Document processing
│   │   ├── processing_queue.py # Queue facade (3 mixins)
│   │   ├── queue_types.py     # TypedDict task definitions
│   │   ├── task_executor_mixin.py
│   │   ├── task_lifecycle_mixin.py
│   │   ├── notification_mixin.py
│   │   └── generators/        # SOAP, referral, letter, diagnostic, etc.
│   ├── rag/                    # RAG subsystem (40 modules)
│   │   ├── hybrid_retriever.py
│   │   ├── streaming_retriever.py
│   │   ├── query_expander.py   # Medical term expansion
│   │   ├── bm25_search.py     # Full-text keyword search
│   │   ├── adaptive_threshold.py
│   │   ├── mmr_reranker.py    # Diversity reranking
│   │   ├── conversation_manager.py
│   │   ├── graph_data_provider.py  # Neo4j knowledge graph
│   │   ├── guidelines_upload_manager.py
│   │   └── neon_vector_store.py
│   ├── stt_providers/          # Speech-to-text (5 providers + failover)
│   │   ├── base.py
│   │   ├── deepgram.py        # Nova-2 Medical
│   │   ├── elevenlabs.py      # Scribe v2, diarization
│   │   ├── groq.py            # Whisper Large v3 Turbo
│   │   ├── modulate.py        # Velma with emotion detection
│   │   ├── whisper.py         # Local Whisper
│   │   └── failover.py        # Automatic provider failover
│   ├── tts_providers/          # Text-to-speech
│   │   ├── elevenlabs_tts.py  # Flash v2.5, Turbo v2.5, Multilingual v2
│   │   └── pyttsx_provider.py # Offline fallback
│   ├── translation/            # Translation providers
│   │   └── deep_translator_provider.py  # Google, DeepL, Microsoft
│   ├── ui/                     # User interface
│   │   ├── workflow_ui.py     # Main UI orchestration
│   │   ├── chat_ui.py         # Chat interface
│   │   ├── menu_manager.py    # Application menus
│   │   ├── theme_manager.py   # Dark/light themes
│   │   ├── dialogs/           # 25+ dialog windows
│   │   └── components/        # Reusable UI components
│   └── utils/                  # Utilities
│       ├── security.py        # SecurityManager facade
│       ├── security/          # Encryption, key storage, validators, rate limiting
│       ├── resilience.py      # Circuit breaker, retry, backoff
│       ├── validation.py      # API key patterns, input validation
│       ├── audit_logger.py    # HIPAA-compliant audit trail
│       └── structured_logging.py  # PHI redaction in logs
├── config/                     # Configuration files
├── tests/                      # 1,850+ tests
│   ├── unit/                  # Component tests
│   └── integration/           # End-to-end tests
└── scripts/                    # Build scripts (Windows, macOS, Linux)
```

### Key Design Patterns

| Pattern | Usage |
|---------|-------|
| **Mixin/Facade** | Large classes decomposed into focused mixins; facades preserve backward compatibility |
| **Protocol Contracts** | `AppProtocol` defines the ~50 attributes mixins expect from the app object |
| **TypedDict Schemas** | `ProcessingTask`, `ChatContextData`, `BatchTaskStatus` etc. for type-safe dict structures |
| **Provider Pattern** | All AI, STT, and TTS providers inherit from base classes for consistent interfaces |
| **Singleton Managers** | Agent, translation, and API key managers ensure single instances |
| **Circuit Breaker** | Resilient API calls with automatic failure detection and recovery |
| **Security Decorators** | Rate limiting and input sanitization applied via decorators |
| **Migration System** | Database schema evolution with versioned migrations |
| **Observer Pattern** | UI updates via event-driven architecture with thread-safe scheduling |
| **Queue System** | Background processing with priority, stale task eviction, and batch tracking |

### Data Flow

```
Audio Input → STT Provider (failover chain) → Transcript → AI Processing → Document Generation
                  ↓                                              ↓
           Emotion Data*                                  Agent System (10 agents)
                  ↓                                              ↓
           SOAP Integration                         Database Storage → Export (PDF/DOCX/FHIR)
                                                         ↓
                                                  RAG Vector Store → Knowledge Graph (Neo4j)
                                                         ↓
                                                  Hybrid Search (vector + BM25 + graph)

* Voice emotion analysis available with Modulate (Velma) STT provider
```

---

## Testing

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests with pytest
PYTHONPATH=src pytest tests/unit/ tests/integration/

# Run with coverage report
PYTHONPATH=src pytest --cov=src --cov-report=html

# Run specific test suites
PYTHONPATH=src pytest tests/unit/
PYTHONPATH=src pytest tests/integration/

# Run specific test files
PYTHONPATH=src pytest tests/unit/test_audio_extended.py
PYTHONPATH=src pytest tests/unit/test_processing_queue.py
PYTHONPATH=src pytest tests/unit/test_stt_providers/
```

### Test Suite (1,850+ tests)

| Suite | Tests | Coverage |
|-------|-------|----------|
| **Audio & Recording** | 101 | Audio handler, prefix caching, mixin decomposition |
| **STT Providers** | 150+ | Deepgram, ElevenLabs, Groq, Modulate, Whisper, failover |
| **Processing Queue** | 90+ | Task lifecycle, batch processing, stale eviction, thread safety |
| **Security** | 50+ | Encryption, key migration, validation, rate limiting |
| **Exporters** | 137 | PDF, DOCX, FHIR R4, RAG export |
| **RAG & Documents** | 57 | Document CRUD, hybrid search, query expansion |
| **Letter Generation** | 50 | All letter types, edge cases, template rendering |
| **Periodic Analysis** | 57 | Timer management, segment extraction, cleanup |
| **TTS & Translation** | 77 | Provider management, safe methods, fallbacks |
| **Integration** | 29 | Settings roundtrip, API key crypto, DB migrations |

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
| **Only One Speaker Detected** | In ElevenLabs Settings, leave "Number of Speakers" empty for auto-detection. Lower the "Diarization Threshold" (e.g. 0.3) for more sensitive speaker separation. |
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
| **Memory** | 4GB RAM | 8GB+ RAM (16GB with local Whisper) |
| **Storage** | 500MB | 2GB+ for recordings and RAG database |
| **Internet** | Required for cloud AI | Optional with Ollama + local Whisper |
| **Audio** | Any microphone | USB condenser microphone |
| **Optional** | - | PostgreSQL (Neon) for RAG, Neo4j for knowledge graph |

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

- [OpenAI](https://openai.com) - GPT models and Whisper
- [Anthropic](https://anthropic.com) - Claude models
- [Google AI](https://ai.google.dev) - Gemini models
- [Deepgram](https://deepgram.com) - Nova-2 Medical STT
- [ElevenLabs](https://elevenlabs.io) - Scribe STT and TTS
- [Groq](https://groq.com) - Fast LLM and Whisper inference
- [Cerebras](https://cerebras.ai) - Wafer-scale LLM inference
- [Modulate.ai](https://modulate.ai) - Velma voice emotion detection
- [Ollama](https://ollama.ai) - Local model hosting
- [Neon](https://neon.tech) - Serverless PostgreSQL with pgvector
- [Neo4j](https://neo4j.com) - Knowledge graph database
- [ttkbootstrap](https://ttkbootstrap.readthedocs.io) - Modern UI themes

---

<p align="center">
  Made with care for healthcare professionals
</p>
