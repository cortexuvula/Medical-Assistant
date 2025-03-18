# Medical Assistant

Medical Assistant is a desktop application designed to transcribe and refine spoken medical notes. It leverages advanced AI APIs (OpenAI, Perplexity, Grok, and Ollama) and offers voice command controls, ensuring efficient audio-to-text conversion and note generation.

## Features
- **Real-time transcription:** Convert speech to text using Google Speech Recognition, Deepgram or Elevenlabs.
- **AI Assistance:** Generate refined texts, improved clarity, SOAP notes, and referral paragraphs using OpenAI, Perplexity, Grok, or local Ollama models.
- **Multiple AI Provider Support:** Choose between cloud services (OpenAI, Perplexity, Grok) or run models locally using Ollama.
- **Voice Commands:** Control the application via voice commands (e.g., "new paragraph", "full stop").
- **Customizable Prompts:** Edit and import/export prompts and models for text refinement and note generation.
- **Audio Recording:** Record and save audio with options for live transcription and SOAP note extraction.
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

3. **Buttons and Voice Commands**  
   - **Record/Stop:** Start and stop dictation.
   - **SOAP Note / Referral:** Generate a SOAP note or referral paragraph without formatting markdown.
   - **Prompt Settings:** Adjust prompts via the Settings menu.
   - **Record SOAP Note:** Start recording a conversation followed by auto-transcription and SOAP Note creation. 

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
