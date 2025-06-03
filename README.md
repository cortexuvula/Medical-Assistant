# Medical Assistant

Medical Assistant is a desktop application designed to transcribe and refine spoken medical notes. It leverages advanced AI APIs (OpenAI, Perplexity, Grok, and Ollama) and offers efficient audio-to-text conversion and note generation with context-aware capabilities.

## Features
- **Multi-Tab Interface:** Five-tab layout with Transcript, SOAP Note, Referral, Letter, and Context tabs for organized workflow
- **Context-Aware SOAP Notes:** New Context tab allows you to add previous medical information that gets automatically included in SOAP note generation
- **Transcription:** Convert speech to text using multiple providers (Deepgram, ElevenLabs, Groq, or Whisper)
- **AI Assistance:** Generate refined texts, improved clarity, SOAP notes, and referral paragraphs using OpenAI, Perplexity, Grok, or local Ollama models
- **Multiple AI Provider Support:** Choose between cloud services (OpenAI, Perplexity, Grok) or run models locally using Ollama
- **Smart Context Preservation:** Context information is preserved during SOAP recordings and only cleared on new sessions or manual clearing
- **Customizable Prompts:** Edit and import/export prompts and models for text refinement and note generation
- **SOAP Note Recording:** Record SOAP notes with options for transcription and automatic note extraction
- **Database Storage:** Automatic saving and retrieval of recordings, transcripts, and generated documents
- **File Logging System:** Track application activity with a built-in logging system that maintains the last 1000 entries
- **Cross-Platform Support:** Available for Windows, macOS, and Linux with platform-specific optimizations
- **User-friendly Interface:** Built with Tkinter and ttkbootstrap for a modern UI experience

## Installation

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

3. **Main Features**  
   - **Context Tab:** Add previous medical information that will be automatically included in SOAP note generation
   - **SOAP Note Recording:** Start recording a conversation followed by auto-transcription and context-aware SOAP Note creation
   - **Text Processing:** Use buttons to refine text, improve clarity, generate SOAP notes or referral paragraphs
   - **Document Generation:** Create referrals and letters from existing SOAP notes
   - **Smart Workflows:** Context is preserved during SOAP recordings but cleared on new sessions

4. **Using the Context Tab**
   - Navigate to the Context tab and paste or type previous medical information
   - This information will be automatically included as "Previous medical information" in SOAP note prompts
   - Use the "Clear Context" button to manually clear the context
   - Context is preserved when starting new SOAP recordings but cleared when starting a "New Session"

5. **Editing Prompts and Models**  
   Use the "Prompt Settings" menu to modify and update prompts and models for refine, improve, SOAP note, and referral functionalities. Each provider can have different model selections.

6. **Viewing Application Logs**
   - Access application logs through the "View Logs" option in the Help menu
   - Choose between opening the logs directory or viewing logs directly in the application
   - Logs automatically rotate to keep only the last 1000 entries, preventing excessive disk usage

## Troubleshooting

### **Common Issues**

- **API Keys**: If you need to update API keys after startup, use the "API Keys" option in the settings menu.

- **Context Tab Issues**: 
  - Context text is automatically preserved during SOAP recordings
  - Use "New Session" or the "Clear Context" button to clear previous medical information
  - Context is included as "Previous medical information" in SOAP note generation

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

### Version 1.0.27 (Latest)
- **New Context Tab**: Added dedicated tab for previous medical information that gets included in SOAP note generation
- **Smart Context Preservation**: Context is preserved during SOAP recordings but cleared on new sessions
- **Clear Context Button**: Easy way to manually clear context information
- **Code Cleanup**: Removed duplicate code and optimized imports for better performance
- **Enhanced UI**: Five-tab layout with improved workflow organization

### Key Improvements
- **Multi-Provider STT Support**: Added Groq and enhanced ElevenLabs integration
- **Database Enhancements**: Improved data storage and retrieval capabilities
- **Cross-Platform Icons**: Custom application icons for all supported platforms
- **Desktop Integration**: Automated desktop shortcut creation scripts
- **Performance Optimizations**: Reduced application startup time and memory usage

## System Requirements

- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **Python**: 3.8+ (for running from source)
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 500MB free space for application and dependencies
- **Internet**: Required for cloud AI services (optional for local Ollama models)
- **Audio**: Microphone for speech-to-text functionality

## Contribution

Contributions to the Medical Dictation Assistant are welcome.  
- Fork the repository.
- Create a feature branch.
- Submit a Pull Request with your enhancements.

## License

Distributed under the MIT License.
