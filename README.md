# Medical Assistant

Medical Assistant is a desktop application designed to transcribe and refine spoken medical notes. It leverages advanced AI APIs (OpenAI, Perplexity, Grok, and Ollama) and offers efficient audio-to-text conversion and note generation with context-aware capabilities.

## Features

### Core Features
- **Workflow-Based Interface:** Modern task-oriented design with 4 main workflow tabs (Record, Process, Generate, Recordings) plus 5 text editor tabs
- **AI-Powered Chat Interface:** ChatGPT-style interface with context-aware suggestions for interacting with your medical notes
- **Advanced Recording System:** Record medical conversations with visual feedback, timer display, and pause/resume capabilities
- **Queue System:** Background processing queue with "Quick Continue Mode" for efficient multi-patient recording sessions
- **Dedicated Recordings Manager:** New Recordings tab with search, filter, and document status indicators (✓, —, 🔄, ❌)

### Medical Documentation
- **Context-Aware SOAP Notes:** Side panel for adding previous medical information that automatically integrates into SOAP note generation
- **Smart Templates:** Pre-built and custom context templates for common scenarios (Follow-up, New Patient, Telehealth, etc.)
- **Multi-Format Document Generation:** Create SOAP notes, referral letters, and custom medical documents
- **Smart Context Preservation:** Context information is preserved during SOAP recordings and only cleared on new sessions or manual clearing
- **Medication Analysis Agent:** Comprehensive medication analysis including extraction, interaction checking, dosing validation, and prescription generation

### AI & Transcription
- **Multiple STT Providers:** Deepgram, ElevenLabs, Groq, or local Whisper for speech-to-text conversion
- **Multiple AI Providers:** OpenAI, Perplexity, Grok, or local Ollama models for text processing
- **Customizable Prompts:** Edit and import/export prompts and models for text refinement and note generation
- **Intelligent Text Processing:** Refine, improve clarity, and generate medical documentation with AI assistance

### Technical Features
- **Database Storage:** Automatic saving and retrieval of recordings, transcripts, and generated documents
- **Export Functionality:** Export recordings and documents in various formats
- **File Logging System:** Track application activity with a built-in logging system that maintains the last 1000 entries
- **Cross-Platform Support:** Available for Windows, macOS, and Linux with platform-specific optimizations
- **Modern UI/UX:** Built with Tkinter and ttkbootstrap featuring animations, visual indicators, and responsive design

## Installation

### Prerequisites
- Python 3.10 or higher (required for Deepgram SDK compatibility)
- FFmpeg (for audio processing)

1. **Clone or Download the Repository**
   ```
   git clone <repository-url>
   ```

2. **Install Dependencies**  
   Run the following command in the project directory:
   ```
   pip install -r requirements.txt
   ```

3. **Configuration**  
   - Create a `.env` file in the project root, or use the "API Keys" dialog in the application.
   - Add your API keys and configuration settings:
     - **LLM Services:** `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `GROK_API_KEY`
     - **Speech-to-Text Services:** `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, `GROQ_API_KEY`
     - **Local Models:** `OLLAMA_API_URL` (defaults to "http://localhost:11434")
     - **Language Settings:** `RECOGNITION_LANGUAGE` (defaults to "en-US")
   - **Minimum Requirements:** You need at least one LLM provider and one STT provider to use the application.

4. **Ollama Setup (Optional)**  
   To use local AI models:
   - Install Ollama from [ollama.ai](https://ollama.ai)
   - Pull models using `ollama pull <model_name>` (e.g., `ollama pull llama3`)
   - The application will automatically detect available models

5. **FFmpeg Installation**  
   FFmpeg is required for audio processing. Download FFmpeg from [ffmpeg.org](https://ffmpeg.org) and follow the instructions for Windows.  
   For a step-by-step guide, watch this YouTube tutorial: [How to Install FFmpeg on Windows](https://youtu.be/JR36oH35Fgg?si=MoabHE-pi3NrJo4U).

## Building Standalone Executables

The application can be packaged as a standalone executable for Windows, macOS, and Linux using PyInstaller.

### Prerequisites
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- For Windows: Have Python and pip in your PATH
- For macOS: May need to install Xcode command line tools
- For Linux: Ensure python3-tk is installed system-wide

### Building

**Windows:**
```batch
build_windows.bat
```
The executable will be in `dist/MedicalAssistant.exe`

**macOS:**
```bash
./build_macos.sh
```
The app bundle will be in `dist/MedicalAssistant.app`

**Linux:**
```bash
# First, ensure FFmpeg is installed:
sudo apt-get install ffmpeg  # For Ubuntu/Debian
# or
sudo dnf install ffmpeg      # For Fedora
# or
sudo pacman -S ffmpeg        # For Arch

# Then build:
./build_linux.sh
```
The executable will be in `dist/MedicalAssistant`

**Important for Linux:** Run the application using the launcher script:
```bash
./dist/linux_launcher.sh
```
This ensures system FFmpeg libraries are used correctly.

### Distribution Notes
- The executable includes all Python dependencies
- Users still need to have FFmpeg installed separately
- API keys can be configured via the application's settings dialog
- First run may be slower as antivirus software scans the executable

### Desktop Shortcuts (Optional)
Create desktop shortcuts for easy access:

**Windows:**
```batch
create_desktop_shortcut.bat
```

**Linux:**
```bash
./install_desktop_entry.sh
```

**macOS:**
Desktop shortcuts are automatically created during the build process.

## Usage

1. **Launching the Application**  
   Execute the following command:
   ```
   python main.py
   ```

2. **Setting Up AI Provider**
   - Select your preferred AI provider from the dropdown (OpenAI, Perplexity, Grok, or Ollama)
   - For cloud services, ensure you've entered valid API keys
   - For Ollama, click "Test Ollama Connection" in settings to verify your setup

3. **Main Workflow Tabs**
   - **Record Tab:** Start/stop recordings with visual feedback, timer display, and pause/resume controls
   - **Process Tab:** Refine and improve transcribed text with AI assistance
   - **Generate Tab:** Create SOAP notes, referrals, letters, and perform medication analysis
   - **Recordings Tab:** View, search, and manage all saved recordings with document status indicators

4. **Using the Chat Interface**
   - Located at the bottom of the main content area
   - Press `Ctrl+/` (or `Cmd+/` on Mac) to quickly focus the chat input
   - Context-aware suggestions based on your current tab and content
   - Interact with any text in the editor tabs
   - Get intelligent suggestions for next steps

5. **Working with Context**
   - Click the "Context" button to open the collapsible side panel
   - Add previous medical information that will be automatically included in SOAP notes
   - Use pre-built templates or create custom ones
   - Context is preserved during SOAP recordings but cleared on new sessions
   - Use the "Clear Context" button to manually clear information

6. **Queue System and Quick Continue Mode**
   - Enable "Quick Continue Mode" to queue recordings while starting new ones
   - Monitor queue status in the status bar
   - Perfect for busy clinics with back-to-back patients
   - Background processing ensures smooth workflow

7. **Managing Recordings**
   - Access the Recordings tab to view all saved recordings
   - Document status indicators show completion state:
     - ✓ (green) = Document generated
     - — (gray) = Not generated
     - 🔄 (blue) = In progress
     - ❌ (red) = Error
   - Search and filter recordings by date or content
   - Load recordings to continue working on them
   - Export recordings and documents

8. **Using Medication Analysis**
   - Click the medication analysis button in the Generate tab
   - Choose your content source (transcript, SOAP note, or context information)
   - Select analysis type:
     - Extract medications from text
     - Check drug interactions
     - Validate dosing
     - Suggest alternatives
     - Generate prescriptions
     - Comprehensive analysis
   - View detailed results with warnings and recommendations

9. **Editing Prompts and Models**  
   Use the "Prompt Settings" menu to modify and update prompts and models for refine, improve, SOAP note, and referral functionalities. Each provider can have different model selections.

10. **Viewing Application Logs**
    - Access application logs through the "View Logs" option in the Help menu
    - Choose between opening the logs directory or viewing logs directly in the application
    - Logs automatically rotate to keep only the last 1000 entries, preventing excessive disk usage

## Troubleshooting

### **Common Issues**

- **API Keys**: If you need to update API keys after startup, use the "API Keys" option in the settings menu.

- **Context Panel Issues**: 
  - Context panel is accessed via the "Context" button, not a tab
  - Context text is automatically preserved during SOAP recordings
  - Use "New Session" or the "Clear Context" button to clear previous medical information
  - Context is included as "Previous medical information" in SOAP note generation

- **Chat Interface Issues**:
  - If chat suggestions don't appear, ensure you have content in the active tab
  - Use keyboard shortcut `Ctrl+/` (`Cmd+/` on Mac) to quickly access chat
  - Chat context is based on the currently active tab

- **Queue System Issues**:
  - Monitor the status bar for queue progress
  - If recordings are stuck in queue, check the logs for errors
  - Disable "Quick Continue Mode" if you prefer sequential processing

- **Ollama Connection Issues**: If you experience timeouts with Ollama models, try:
  - Using a smaller model variant (e.g., `mistral:small` instead of `mistral:7b`)
  - Ensuring your computer has adequate resources (CPU/RAM)
  - Testing your connection with the "Test Ollama Connection" button

- **Audio/Recording Issues**:
  - Ensure FFmpeg is properly installed and accessible
  - Check microphone permissions in your operating system
  - Verify your selected audio device in the application settings

- **Performance Issues**:
  - Close unused tabs and applications to free up system resources
  - For large context text, consider breaking it into smaller sections
  - Use local Ollama models if experiencing cloud API rate limits

### **Getting Help**

- **Application Logs**: Check application logs through Help → View Logs for detailed error information
- **Database Issues**: Use the migration tools if you encounter database errors after updates
- **Settings Reset**: Delete the application's settings files to reset to defaults if needed

## Recent Updates

### Version 2.1.0 (Latest)
- **Medication Analysis Agent**: New AI-powered medication agent with comprehensive analysis capabilities
  - Extract medications from clinical text
  - Check drug-drug interactions with severity levels
  - Validate dosing appropriateness
  - Suggest medication alternatives
  - Generate prescriptions
  - Comprehensive medication analysis with safety warnings
- **Enhanced Generate Tab**: Added medication analysis button alongside existing document generation
- **Context Support**: Medication analysis can now use context information as input source
- **Agent Framework**: Extensible agent system for specialized medical AI tasks

### Version 2.0.0
- **New Recordings Tab**: Dedicated tab for managing all recordings with visual status indicators
- **AI Chat Interface**: ChatGPT-style interface for intelligent interaction with medical notes
- **Workflow-Based UI**: Completely redesigned interface organized by tasks (Record, Process, Generate)
- **Queue System**: Background processing with "Quick Continue Mode" for efficient multi-patient workflows
- **Context Panel Redesign**: Context moved from tab to collapsible side panel with template support
- **Visual Enhancements**: Recording animations, timer display, and improved status indicators
- **Document Status Tracking**: Visual indicators (✓, —, 🔄, ❌) show completion state of each document type

### Version 1.0.27
- **Context Feature**: Added previous medical information support for SOAP note generation
- **Smart Context Preservation**: Context preserved during SOAP recordings
- **Code Optimization**: Removed duplicate code and improved performance

### Key Improvements
- **Modern UI/UX**: Task-oriented workflow with visual feedback and animations
- **Enhanced Recording**: Pause/resume capabilities with timer display
- **Smart Templates**: Pre-built and custom context templates for common scenarios
- **Export Functionality**: Export recordings and documents in various formats
- **Multi-Provider STT Support**: Deepgram, ElevenLabs, Groq, and Whisper integration
- **Performance Optimizations**: Reduced startup time and improved memory usage

## System Requirements

- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **Python**: 3.8+ (for running from source)
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 500MB free space for application and dependencies
- **Internet**: Required for cloud AI services (optional for local Ollama models)
- **Audio**: Microphone for speech-to-text functionality

## Documentation

### User Documentation
- [User Guide](docs/user_guide.md) - Comprehensive user documentation
- [Keyboard Shortcuts](SHORTCUTS.md) - Quick reference for keyboard shortcuts
- [Security Features](docs/security_features.md) - Security implementation details
- [Database Schema](docs/database_improvements.md) - Database structure and improvements

### Development Documentation
- [Testing Guide](docs/testing_guide.md) - Comprehensive testing documentation (80%+ coverage)
- [Testing Quick Start](docs/testing_quickstart.md) - Quick reference for running tests
- [UI Testing Setup](docs/ui_testing_setup.md) - Guide for UI testing with PyQt5
- [CLAUDE.md](CLAUDE.md) - Development guide for AI-assisted development

### Testing Infrastructure
The project includes a comprehensive test suite with:
- **352 total tests** (327 unit tests + 25 UI tests)
- **80.68% code coverage** on core modules
- Unit tests for all major components
- Integration tests for the recording pipeline
- UI tests demonstrating PyQt5 testing patterns
- Pre-commit hooks for code quality
- CI/CD pipeline for automated testing

To run tests:
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
python -m pytest

# Run with coverage
python run_tests.py --cov

# Run UI tests
python tests/run_ui_tests.py
```

## Contribution

Contributions to the Medical Dictation Assistant are welcome.  
- Fork the repository.
- Create a feature branch.
- Submit a Pull Request with your enhancements.
- Ensure all tests pass and maintain 80%+ coverage

## License

Distributed under the MIT License.
