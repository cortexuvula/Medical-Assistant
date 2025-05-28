# Medical Assistant

Medical Assistant is a desktop application designed to transcribe and refine spoken medical notes. It leverages advanced AI APIs (OpenAI, Perplexity, Grok, and Ollama) and offers efficient audio-to-text conversion and note generation.

## Features
- **Transcription:** Convert speech to text using Deepgram or Elevenlabs.
- **AI Assistance:** Generate refined texts, improved clarity, SOAP notes, and referral paragraphs using OpenAI, Perplexity, Grok, or local Ollama models.
- **Multiple AI Provider Support:** Choose between cloud services (OpenAI, Perplexity, Grok) or run models locally using Ollama.
- **Customizable Prompts:** Edit and import/export prompts and models for text refinement and note generation.
- **SOAP Note Recording:** Record SOAP notes with options for transcription and automatic note extraction.
- **File Logging System:** Track application activity with a built-in logging system that maintains the last 1000 entries.
- **User-friendly Interface:** Built with Tkinter and ttkbootstrap for a modern UI experience.

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
   - Create a `.env` file in the project root.
   - Add your API keys and configuration settings:
     - Cloud services: `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `GROK_API_KEY`
     - Speech services: `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`
     - Local models: `OLLAMA_API_URL` (defaults to "http://localhost:11434")
   - Or use the "API Keys" dialog in the application to set these values.

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
   - **SOAP Note Recording:** Start recording a conversation followed by auto-transcription and SOAP Note creation.
   - **Text Processing:** Use buttons to refine text, improve clarity, generate SOAP notes or referral paragraphs.
   - **Prompt Settings:** Adjust prompts via the Settings menu.

4. **Editing Prompts and Models**  
   Use the "Prompt Settings" menu to modify and update prompts and models for refine, improve, SOAP note, and referral functionalities. Each provider can have different model selections.

5. **Viewing Application Logs**
   - Access application logs through the "View Logs" option in the Help menu
   - Choose between opening the logs directory or viewing logs directly in the application
   - Logs automatically rotate to keep only the last 1000 entries, preventing excessive disk usage

## Troubleshooting

- **Ollama Connection Issues**: If you experience timeouts with Ollama models, try:
  - Using a smaller model variant (e.g., `mistral:small` instead of `mistral:7b`)
  - Ensuring your computer has adequate resources (CPU/RAM)
  - Testing your connection with the "Test Ollama Connection" button

- **API Keys**: If you need to update API keys after startup, use the "API Keys" option in the settings menu.

- **Application Errors**: Check the application logs through Help → View Logs for detailed error information that can help diagnose issues.

## Contribution

Contributions to the Medical Dictation Assistant are welcome.  
- Fork the repository.
- Create a feature branch.
- Submit a Pull Request with your enhancements.

## License

Distributed under the MIT License.
