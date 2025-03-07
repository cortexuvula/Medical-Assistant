import os
import json
import uuid
import time
import logging
from io import BytesIO
import speech_recognition as sr
from pydub import AudioSegment
import requests
from typing import List, Optional, Callable, Any, Dict
from deepgram import DeepgramClient, PrerecordedOptions
from pathlib import Path
from settings import SETTINGS

class AudioHandler:
    """Class to handle all audio-related functionality including recording, transcription, and file operations."""
    
    def __init__(self, elevenlabs_api_key: str = "", deepgram_api_key: str = "", recognition_language: str = "en-US"):
        """Initialize the AudioHandler with necessary API keys and settings.
        
        Args:
            elevenlabs_api_key: API key for ElevenLabs
            deepgram_api_key: API key for Deepgram
            recognition_language: Language code for speech recognition
        """
        self.elevenlabs_api_key = elevenlabs_api_key
        self.deepgram_api_key = deepgram_api_key
        self.recognition_language = recognition_language
        self.recognizer = sr.Recognizer()
        
        # Initialize Deepgram client if API key is provided
        self.deepgram_client = DeepgramClient(api_key=self.deepgram_api_key) if self.deepgram_api_key else None
        
        # Initialize fallback callback to None
        self.fallback_callback = None

    def combine_audio_segments(self, segments: List[AudioSegment]) -> Optional[AudioSegment]:
        """Combine multiple audio segments into a single segment.
        
        Args:
            segments: List of AudioSegment objects
            
        Returns:
            Combined AudioSegment or None if list is empty
        """
        if not segments:
            return None
        combined = segments[0]
        for segment in segments[1:]:
            combined += segment
        return combined

    def set_fallback_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set a callback function to be called when service fallback occurs.
        
        Args:
            callback: Function taking (primary_provider, fallback_provider) as parameters
        """
        self.fallback_callback = callback

    def transcribe_audio(self, segment: AudioSegment) -> str:
        """Transcribe audio using selected provider with fallback options.
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if transcription failed
        """
        # Get the selected STT provider from settings
        primary_provider = SETTINGS.get("stt_provider", "deepgram")
        
        # Track if we've already tried fallback options
        fallback_attempted = False
        
        # First attempt with selected provider
        transcript = self._try_transcription_with_provider(segment, primary_provider)
        
        # If primary provider failed, try fallbacks in sequence
        if not transcript and not fallback_attempted:
            fallback_providers = ["deepgram", "elevenlabs", "google"]
            # Remove primary provider from fallbacks to avoid duplicate attempt
            if primary_provider in fallback_providers:
                fallback_providers.remove(primary_provider)
                
            for provider in fallback_providers:
                logging.info(f"Trying fallback provider: {provider}")
                
                # Notify UI about fallback through callback
                if self.fallback_callback:
                    self.fallback_callback(primary_provider, provider)
                
                transcript = self._try_transcription_with_provider(segment, provider)
                if transcript:
                    logging.info(f"Transcription successful with fallback provider: {provider}")
                    break
                    
        return transcript or ""  # Return empty string if all providers failed

    def _try_transcription_with_provider(self, segment: AudioSegment, provider: str) -> str:
        """Try to transcribe with a specific provider, handling errors.
        
        Args:
            segment: AudioSegment to transcribe
            provider: Provider name ('elevenlabs', 'deepgram', or 'google')
            
        Returns:
            Transcription text or empty string if failed
        """
        try:
            if provider == "elevenlabs":
                return self._transcribe_with_elevenlabs(segment)
                
            elif provider == "deepgram" and self.deepgram_client:
                return self._transcribe_with_deepgram(segment)
                
            elif provider == "google":
                return self._transcribe_with_google(segment)
                
            else:
                logging.warning(f"Unknown provider: {provider}")
                return ""
                
        except Exception as e:
            logging.error(f"Error with {provider} transcription: {str(e)}", exc_info=True)
            return ""

    def _transcribe_with_elevenlabs(self, segment: AudioSegment) -> str:
        """Transcribe audio using ElevenLabs API with proper diarization parameters.
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if failed
        """
        api_key = self.elevenlabs_api_key
        if not api_key:
            logging.warning("ElevenLabs API key not found")
            return ""
        
        # Fetch ElevenLabs settings
        elevenlabs_settings = SETTINGS.get("elevenlabs", {})
        default_settings = {
            "model_id": "scribe_v1",
            "language_code": "",
            "tag_audio_events": True,
            "num_speakers": None,
            "timestamps_granularity": "word",
            "diarize": False
        }
        
        # Get configuration with fallbacks to defaults
        model_id = elevenlabs_settings.get("model_id", default_settings["model_id"])
        diarize = elevenlabs_settings.get("diarize", default_settings["diarize"])
        num_speakers = elevenlabs_settings.get("num_speakers", default_settings["num_speakers"])
        
        # Create a unique temp file with UUID
        temp_file = f"temp_elevenlabs_{uuid.uuid4().hex}.wav"
        
        try:
            # Export audio segment to temp file
            segment.export(temp_file, format="wav")
            
            # Setup the API request
            url = "https://api.elevenlabs.io/v1/speech-to-text"
            headers = {"xi-api-key": api_key}
            
            # Open the file in binary mode
            with open(temp_file, 'rb') as audio_file:
                # Set up files parameter with mime type
                files = {'file': (os.path.basename(temp_file), audio_file, 'audio/wav')}
                
                # Set up data for optimal diarization results
                data = {'model_id': model_id}
                
                # Always set diarize as a string 'true', not a boolean
                if diarize:
                    data['diarize'] = 'true'
                    
                    # Always include num_speakers when diarizing (default to 2 if None)
                    if num_speakers is not None:
                        data['num_speakers'] = num_speakers
                    else:
                        data['num_speakers'] = 2  # Default to 2 speakers for diarization
                
                logging.info(f"ElevenLabs request data: {data}")
                
                # Make the request
                response = requests.post(
                    url, 
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=30
                )
            
            # Process response
            if response.status_code == 200:
                result = response.json()
                
                # Save a copy of the full response for debugging
                debug_file = f"elevenlabs_response_{uuid.uuid4().hex[:8]}.json"
                with open(debug_file, "w") as f:
                    json.dump(result, f, indent=2)
                    
                # Format text with speaker labels if diarization was enabled
                if diarize and 'words' in result and result['words']:
                    formatted_text = self._format_diarized_text(result['words'])
                    return formatted_text
                else:
                    return result.get("text", "")
            else:
                logging.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                return ""
                
        except Exception as e:
            logging.error(f"Error with ElevenLabs transcription: {str(e)}", exc_info=True)
            return ""
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logging.warning(f"Failed to delete temp file {temp_file}: {str(e)}")

    def _format_diarized_text(self, words) -> str:
        """Format diarized text from ElevenLabs with speaker labels.
        
        Args:
            words: List of word objects from ElevenLabs response
            
        Returns:
            Formatted text with speaker labels
        """
        if not words:
            return ""
        
        formatted_text = []
        current_speaker = None
        current_paragraph = []
        
        for word in words:
            # Skip non-word entries like spacing
            if word.get("type") != "word":
                continue
                
            speaker = word.get("speaker_id")
            text = word.get("text", "")
            
            # If this is a new speaker, start a new paragraph
            if speaker and speaker != current_speaker:
                # Add the previous paragraph if it exists
                if current_paragraph:
                    formatted_text.append(" ".join(current_paragraph))
                    current_paragraph = []
                
                # Start new paragraph with speaker label
                current_speaker = speaker
                display_speaker = f"Speaker {speaker.split('_')[-1]}: " if speaker else ""
                current_paragraph.append(display_speaker + text)
            else:
                # Same speaker, just add the word
                current_paragraph.append(text)
        
        # Add the final paragraph
        if current_paragraph:
            formatted_text.append(" ".join(current_paragraph))
        
        # Join paragraphs with double newlines for clear separation
        return "\n\n".join(formatted_text)

    def _transcribe_with_deepgram(self, segment: AudioSegment) -> str:
        """Transcribe audio using Deepgram API with improved error handling.
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if failed
        """
        if not self.deepgram_client:
            logging.warning("Deepgram client not initialized - check API key")
            return ""
        
        max_retries = 2
        retry_delay = 2  # seconds
        attempt = 0
        
        # Get Deepgram settings from SETTINGS
        from settings import SETTINGS, _DEFAULT_SETTINGS
        deepgram_settings = SETTINGS.get("deepgram", _DEFAULT_SETTINGS["deepgram"])
        
        while attempt <= max_retries:
            try:
                logging.info(f"Deepgram transcription attempt {attempt+1}/{max_retries+1}")
                
                # Prepare audio for Deepgram
                buf = BytesIO()
                segment.export(buf, format="wav")
                buf.seek(0)
                
                # Set up options using the settings
                options = PrerecordedOptions(
                    model=deepgram_settings.get("model", "nova-2-medical"), 
                    language=deepgram_settings.get("language", "en-US"),
                    smart_format=deepgram_settings.get("smart_format", True),
                    diarize=deepgram_settings.get("diarize", False),
                    profanity_filter=deepgram_settings.get("profanity_filter", False),
                    redact=deepgram_settings.get("redact", False),
                    alternatives=deepgram_settings.get("alternatives", 1)
                )
                
                # Make API call
                response = self.deepgram_client.listen.rest.v("1").transcribe_file(
                    {"buffer": buf}, 
                    options
                )
                
                # Process response
                response_json = json.loads(response.to_json(indent=4))
                
                # For debugging
                debug_file = f"deepgram_response_debug_{uuid.uuid4().hex[:8]}.json"
                with open(debug_file, "w") as f:
                    json.dump(response_json, f, indent=2)
                logging.info(f"Saved Deepgram response for debugging to: {debug_file}")
                
                # Check if diarization is enabled
                is_diarized = deepgram_settings.get("diarize", False)
                
                # Check for results
                if "results" in response_json and response_json["results"].get("channels"):
                    alternatives = response_json["results"]["channels"][0].get("alternatives", [])
                    
                    if alternatives and "transcript" in alternatives[0]:
                        transcript = alternatives[0]["transcript"]
                        
                        # Process diarization if enabled
                        if is_diarized and "words" in alternatives[0]:
                            return self._format_deepgram_diarized_transcript(alternatives[0]["words"])
                        
                        return transcript
                    
                # If we get here, response structure wasn't as expected
                logging.warning(f"Unexpected Deepgram response structure: {response_json}")
                return ""
                
            except Exception as e:
                error_message = str(e)
                
                # Check for specific error types
                if "rate limit" in error_message.lower() or "429" in error_message:
                    if attempt < max_retries:
                        logging.warning(f"Deepgram API rate limited, retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        attempt += 1
                        continue
                elif "unauthorized" in error_message.lower() or "401" in error_message:
                    logging.error("Deepgram API: Authentication failed - check your API key")
                    return ""
                elif "connection" in error_message.lower():
                    if attempt < max_retries:
                        logging.warning("Deepgram API: Connection error, retrying...")
                        time.sleep(retry_delay)
                        attempt += 1
                        continue
                    
                # Log error and increment attempt counter
                logging.error(f"Deepgram transcription error: {error_message}", exc_info=True)
                
                if attempt < max_retries:
                    logging.warning(f"Deepgram error, retrying ({attempt+1}/{max_retries})...")
                    time.sleep(retry_delay)
                    attempt += 1
                else:
                    logging.error(f"Deepgram transcription failed after {max_retries+1} attempts")
                    return ""
        
        return ""  # Return empty string if all attempts failed

    def _format_deepgram_diarized_transcript(self, words: list) -> str:
        """Format diarized words from Deepgram into a readable transcript with speaker labels.
        
        Args:
            words: List of words from the Deepgram response
            
        Returns:
            Formatted text with speaker labels
        """
        if not words:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        for word_data in words:
            # Check if this word has speaker info
            if "speaker" not in word_data:
                continue
                
            speaker = word_data.get("speaker")
            word = word_data.get("word", "")
            
            # If new speaker, start a new paragraph
            if speaker != current_speaker:
                # Add previous paragraph if it exists
                if current_text:
                    speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
                    result.append(f"{speaker_label}{''.join(current_text)}")
                    current_text = []
                
                current_speaker = speaker
            
            # Add word to current text
            # Add space before word if needed
            if current_text and not word.startswith(("'", ".", ",", "!", "?", ":", ";")):
                current_text.append(" ")
            current_text.append(word)
        
        # Add the last paragraph
        if current_text:
            speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
            result.append(f"{speaker_label}{''.join(current_text)}")
        
        return "\n\n".join(result)

    def _transcribe_with_google(self, segment: AudioSegment) -> str:
        """Transcribe audio using Google Speech Recognition with improved error handling.
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if failed
        """
        temp_file = f"temp_google_{uuid.uuid4().hex}.wav"
        
        try:
            # Export audio to temp file
            segment.export(temp_file, format="wav")
            
            # Use Google Speech Recognition
            with sr.AudioFile(temp_file) as source:
                audio_data = self.recognizer.record(source)
            
            transcript = self.recognizer.recognize_google(audio_data, language=self.recognition_language)
            return transcript
            
        except sr.UnknownValueError:
            logging.warning("Google Speech Recognition could not understand audio")
            return ""
        except sr.RequestError as e:
            logging.error(f"Google Speech Recognition service error: {e}")
            return ""
        except Exception as e:
            logging.error(f"Error with Google transcription: {str(e)}", exc_info=True)
            return ""
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logging.warning(f"Failed to remove temp file {temp_file}: {str(e)}")

    def process_audio_data(self, audio_data: sr.AudioData) -> tuple[Optional[AudioSegment], str]:
        """Process audio data to get an AudioSegment and transcription.
        
        Args:
            audio_data: SpeechRecognition AudioData object
            
        Returns:
            Tuple of (AudioSegment, transcription_text)
        """
        try:
            # Extract audio metadata
            channels = getattr(audio_data, "channels", 1)
            sample_width = getattr(audio_data, "sample_width", None)
            sample_rate = getattr(audio_data, "sample_rate", None)
            
            # Log diagnostic info
            logging.debug(f"Processing audio: channels={channels}, width={sample_width}, rate={sample_rate}")
            
            # Validate audio data
            if not audio_data.get_raw_data():
                logging.warning("Empty audio data received")
                return None, ""
                
            # Convert to AudioSegment
            segment = AudioSegment(
                data=audio_data.get_raw_data(),
                sample_width=sample_width,
                frame_rate=sample_rate,
                channels=channels
            )
            
            # Get transcript
            transcript = self.transcribe_audio(segment)
            
            return segment, transcript
                
        except Exception as e:
            error_msg = f"Audio processing error: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return None, ""

    def load_audio_file(self, file_path: str) -> tuple[Optional[AudioSegment], str]:
        """Load and transcribe audio from a file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (AudioSegment, transcription_text)
        """
        try:
            if (file_path.lower().endswith(".mp3")):
                seg = AudioSegment.from_file(file_path, format="mp3")
            elif (file_path.lower().endswith(".wav")):
                seg = AudioSegment.from_file(file_path, format="wav")
            else:
                raise ValueError("Unsupported audio format. Only .wav and .mp3 supported.")
                
            transcript = self.transcribe_audio(seg)
            return seg, transcript
            
        except Exception as e:
            logging.error(f"Error loading audio file: {str(e)}", exc_info=True)
            return None, ""

    def save_audio(self, segments: List[AudioSegment], file_path: str) -> bool:
        """Save combined audio segments to file.
        
        Args:
            segments: List of AudioSegment objects
            file_path: Path to save the combined audio
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not segments:
                logging.warning("No audio segments to save")
                return False
                
            combined = self.combine_audio_segments(segments)
            if combined:
                # Ensure directory exists
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                combined.export(file_path, format="wav")
                logging.info(f"Audio saved to {file_path}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error saving audio: {str(e)}", exc_info=True)
            return False
