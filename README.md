# Medical Dictation App

Medical Dictation App is a Python-based application that leverages speech recognition and AI assistance to help users transcribe, refine, and improve audio dictations. The application is designed with a focus on medical transcription, using APIs like Deepgram for specialized speech recognition and OpenAI for text refinement.

## Features

- **Audio Transcription:** Record audio through a selected microphone and transcribe it in real-time.
- **Voice Commands:** Use predefined voice commands (e.g., "full stop", "new paragraph", "delete last word") to insert punctuation and formatting.
- **AI Assistance:**  
  - **Refine Text:** Correct punctuation and capitalization using OpenAI GPT-3.5.
  - **Improve Text:** Enhance clarity and readability using OpenAI GPT-4.
- **User-Friendly Interface:** Built with Tkinter and ttkbootstrap for a modern GUI.
- **Multiple Microphone Support:** Easily refresh and select from available microphones.
- **Clipboard & File Operations:** Copy transcribed text to the clipboard and save it as a text file.
- **Responsive Layout:** All widgets expand with the window to maintain an optimal layout.

## Requirements

- **Python:** 3.7 or higher
- **Python Packages:**  
  - [SpeechRecognition](https://pypi.org/project/SpeechRecognition/)
  - [pydub](https://pypi.org/project/pydub/)
  - [deepgram-sdk](https://pypi.org/project/deepgram-sdk/)
  - [ttkbootstrap](https://pypi.org/project/ttkbootstrap/)
  - [python-dotenv](https://pypi.org/project/python-dotenv/)
  - [openai](https://pypi.org/project/openai/)

You can install the required packages using pip:

```bash
pip install SpeechRecognition pydub deepgram-sdk ttkbootstrap python-dotenv openai
```

## Usage

- Record audio through a selected microphone.
- Use voice commands to insert punctuation and formatting.
- Refine and improve text using AI assistance.
- Copy transcribed text to the clipboard or save it as a text file.
- Note: The application adjusts its layout when expanded or set to full screen.

