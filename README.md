# Medical Dictation/Assistant

Medical Dictation/Assistant is a desktop application designed to transcribe and refine spoken medical notes. It leverages advanced AI APIs (OpenAI and Perplexity) and offers voice command controls, ensuring efficient audio-to-text conversion and note generation.

## Features
- **Real-time transcription:** Convert speech to text using Google Speech Recognition or Deepgram.
- **AI Assistance:** Generate refined texts, improved clarity, SOAP notes, and referral paragraphs using OpenAI/Perplexity.
- **Voice Commands:** Control the application via voice commands (e.g., "new paragraph", "full stop").
- **Customizable Prompts:** Edit and import/export prompts and models for text refinement and note generation.
- **Audio Recording:** Record and save audio with options for live transcription and SOAP note extraction.
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
   - Add your API keys and configuration settings (e.g., `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `DEEPGRAM_API_KEY`, etc.).

4. **FFmpeg Installation**  
   FFmpeg is required for audio processing. Download FFmpeg from [ffmpeg.org](https://ffmpeg.org) and follow the instructions for Windows.  
   For a step-by-step guide, watch this YouTube tutorial: [How to Install FFmpeg on Windows](https://youtu.be/JR36oH35Fgg?si=MoabHE-pi3NrJo4U).

## Usage

1. **Launching the Application**  
   Execute the following command:
   ```
   python main.py
   ```

2. **Buttons and Voice Commands**  
   - **Record/Stop:** Start and stop dictation.
   - **SOAP Note / Referral:** Generate a SOAP note or referral paragraph without formatting markdown.
   - **Prompt Settings:** Adjust prompts via the Settings menu.

3. **Editing Prompts**  
   Use the "Prompt Settings" menu to modify and update prompts and models for refine, improve, SOAP note, and referral functionalities.

## Contribution

Contributions to the Medical Dictation Assistant are welcome.  
- Fork the repository.
- Create a feature branch.
- Submit a Pull Request with your enhancements.

## License

Distributed under the MIT License.

