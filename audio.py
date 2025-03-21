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
import tempfile

class AudioHandler:
    """Class to handle all audio-related functionality including recording, transcription, and file operations."""
    
    def __init__(self, elevenlabs_api_key: str = "", deepgram_api_key: str = "", recognition_language: str = "en-US", groq_api_key: str = ""):
        """Initialize the AudioHandler with necessary API keys and settings.
        
        Args:
            elevenlabs_api_key: API key for ElevenLabs
            deepgram_api_key: API key for Deepgram
            recognition_language: Language code for speech recognition
            groq_api_key: API key for GROQ (default STT provider)
        """
        self.elevenlabs_api_key = elevenlabs_api_key
        self.deepgram_api_key = deepgram_api_key
        self.groq_api_key = groq_api_key
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
        
        # Only use fallback if there's an actual error (empty string)
        # For successful API calls that return a result (even placeholders like "[Silence...]"), 
        # we'll keep that result and not fall back
        if transcript == "" and not fallback_attempted:
            fallback_providers = ["deepgram", "elevenlabs", "groq"]
            # Remove primary provider from fallbacks to avoid duplicate attempt
            if primary_provider in fallback_providers:
                fallback_providers.remove(primary_provider)
                
            for provider in fallback_providers:
                logging.info(f"Trying fallback provider: {provider}")
                
                # Notify UI about fallback through callback
                if self.fallback_callback:
                    self.fallback_callback(primary_provider, provider)
                
                transcript = self._try_transcription_with_provider(segment, provider)
                if transcript != "":
                    logging.info(f"Transcription successful with fallback provider: {provider}")
                    break
                    
        return transcript or ""  # Return empty string if all providers failed

    def _try_transcription_with_provider(self, segment: AudioSegment, provider: str) -> str:
        """Try to transcribe with a specific provider, handling errors.
        
        Args:
            segment: AudioSegment to transcribe
            provider: Provider name ('elevenlabs', 'deepgram', or 'groq')
            
        Returns:
            Transcription text or empty string if failed
        """
        try:
            if provider == "elevenlabs":
                return self._transcribe_with_elevenlabs(segment)
                
            elif provider == "deepgram" and self.deepgram_client:
                return self._transcribe_with_deepgram(segment)
                
            elif provider == "groq":
                return self._transcribe_with_groq(segment)
                
            else:
                logging.warning(f"Unknown provider: {provider}")
                return ""
                
        except Exception as e:
            logging.error(f"Error with {provider} transcription: {str(e)}", exc_info=True)
            return ""

    def _transcribe_with_elevenlabs(self, segment: AudioSegment) -> str:
        """Transcribe audio using ElevenLabs API.
        
        Args:
            segment: Audio segment to transcribe
            
        Returns:
            Transcription text
        """
        if not self.elevenlabs_api_key:
            logging.warning("ElevenLabs API key not found")
            return ""
        
        temp_file = None
        file_obj = None
        transcript = ""
            
        try:
            # Convert segment to WAV for API
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
                temp_file = temp.name
                segment.export(temp_file, format="wav")
                
            url = "https://api.elevenlabs.io/v1/speech-to-text"
            headers = {
                'xi-api-key': self.elevenlabs_api_key
            }
            
            # Check file size and adjust timeout accordingly
            file_size_kb = os.path.getsize(temp_file) / 1024
            
            # Add a minute of timeout for each 500KB of audio, with a minimum of 60 seconds
            timeout_seconds = max(60, int(file_size_kb / 500) * 60)
            logging.info(f"Setting ElevenLabs timeout to {timeout_seconds} seconds for {file_size_kb:.2f} KB file")
            
            # Prepare data for request
            data = {
                'model_id': 'scribe_v1'
            }
            
            # Add diarization parameters
            elevenlabs_settings = SETTINGS.get("elevenlabs", {})
            diarize = elevenlabs_settings.get("diarize", True)
            
            if diarize:
                # ElevenLabs API expects a boolean value
                data['diarize'] = True
                
                # Get number of speakers setting
                num_speakers = elevenlabs_settings.get("num_speakers", None)
                if num_speakers is not None:
                    data['num_speakers'] = num_speakers
                else:
                    data['num_speakers'] = 2  # Default to 2 speakers for diarization
                    
                # Setting additional parameters that might help with diarization
                language_code = elevenlabs_settings.get("language_code", "")
                if language_code:
                    data['language_code'] = language_code
                    
                timestamps_granularity = elevenlabs_settings.get("timestamps_granularity", "word")
                if timestamps_granularity:
                    data['timestamps_granularity'] = timestamps_granularity
            
            # Print API call details to terminal
            print("\n===== ELEVENLABS API CALL =====")
            print(f"URL: {url}")
            print(f"Headers: {{'xi-api-key': '****API_KEY_HIDDEN****'}}")
            print(f"Data parameters: {data}")
            print(f"File: {os.path.basename(temp_file)} (audio/wav)")
            print(f"Audio file size: {file_size_kb:.2f} KB")
            print(f"Timeout set to: {timeout_seconds} seconds")
            print("===============================\n")
            
            logging.info(f"ElevenLabs request data: {data}")
            
            # Open file in a way that ensures proper closing
            file_obj = open(temp_file, 'rb')
            
            # Create file tuple for request with the file object
            files = {
                'file': ('audio.wav', file_obj, 'audio/wav')
            }
            
            # Make the request
            response = requests.post(
                url, 
                headers=headers,
                files=files,
                data=data,
                timeout=timeout_seconds
            )
            
            # First, make sure we close the file object before trying to delete
            if file_obj:
                file_obj.close()
                file_obj = None
        
            # Process response
            if response.status_code == 200:
                result = response.json()
                
                # Print successful response info to terminal
                print("\n===== ELEVENLABS API RESPONSE =====")
                print(f"Status: {response.status_code} OK")
                print(f"Response size: {len(response.text)} bytes")
                
                if 'words' in result:
                    word_count = len(result['words'])
                    print(f"Words transcribed: {word_count}")
                if 'text' in result:
                    text_preview = result['text'][:100] + "..." if len(result['text']) > 100 else result['text']
                    print(f"Text preview: {text_preview}")

                # Print response structure for debugging
                print("\n=== Response Structure ===")
                for key in result:
                    print(f"Key: {key}, Type: {type(result[key])}")
                    if key == 'words' and result['words']:
                        print(f"Sample word entry: {result['words'][0]}")
                        print(f"Available fields in word entry: {list(result['words'][0].keys())}")
                
                # More detailed debug info for speaker diarization
                print("\n=== Diarization Debug ===")
                print(f"Diarization requested: {diarize}")
                
                # Check for diarization data in different possible locations
                has_speaker_info = False
                diarization_location = None
                
                # Check if the result itself has a 'speakers' field
                if 'speakers' in result:
                    has_speaker_info = True
                    diarization_location = "root.speakers"
                    print(f"Found speakers data at root level: {result['speakers']}")
                
                # Check if there's a separate 'diarization' field
                if 'diarization' in result:
                    has_speaker_info = True
                    diarization_location = "root.diarization"
                    print(f"Found diarization data: {result['diarization']}")
                
                # Check word-level speaker information
                if 'words' in result and result['words']:
                    word_fields = set()
                    for key in result['words'][0].keys():
                        word_fields.add(key)
                        if 'speaker' in key.lower():
                            has_speaker_info = True
                            diarization_location = f"words.{key}"
                    
                    print(f"Word-level fields: {word_fields}")
                    
                    # Print first 3 words with full details
                    print("\nFirst 3 word entries (full details):")
                    for i, word in enumerate(result['words'][:3]):
                        print(f"Word {i+1}: {word}")
                
                # Based on our findings, determine if and how to process diarization
                if has_speaker_info:
                    print(f"\nFound speaker information at: {diarization_location}")
                    
                    # Method 1: If we have word-level speaker info
                    if diarization_location and diarization_location.startswith("words."):
                        speaker_field = diarization_location.split('.')[1]
                        transcript = self._format_elevenlabs_diarized_transcript_with_field(result['words'], speaker_field)
                    
                    # Method 2: If we have a separate diarization structure, build transcript accordingly
                    elif diarization_location == "root.diarization" and 'diarization' in result:
                        transcript = self._format_elevenlabs_diarized_transcript_from_segments(result)
                    
                    # Method 3: If there's a root.speakers field but not word-level
                    elif diarization_location == "root.speakers" and 'speakers' in result:
                        transcript = self._format_elevenlabs_diarized_transcript_from_speakers(result)
                    
                    # Fallback: Use the general formatting approach
                    else:
                        transcript = self._format_elevenlabs_diarized_transcript(result['words'])
                    
                    print(f"\nGenerated diarized transcript with speaker labels")
                else:
                    # Use plain text if not diarized
                    transcript = result.get("text", "")
                    print(f"\nUsing plain text transcript (no speaker information found)")
                    
            else:
                error_msg = f"ElevenLabs API error: {response.status_code} - {response.text}"
                logging.error(error_msg)
                print(f"\n===== ELEVENLABS ERROR =====")
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")
                print("============================\n")
                
        except Exception as e:
            error_msg = f"Error with ElevenLabs transcription: {str(e)}"
            logging.error(error_msg, exc_info=True)
            
            # Print exception details to terminal
            print("\n===== ELEVENLABS EXCEPTION =====")
            print(f"Error: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            print("================================\n")
                
        finally:
            # Make sure file handle is closed
            if file_obj and not file_obj.closed:
                try:
                    file_obj.close()
                except Exception as e:
                    logging.warning(f"Error closing file handle: {str(e)}")
            
            # Try to clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    # On Windows, sometimes we need to wait a moment before the file can be deleted
                    import time
                    time.sleep(0.5)
                    os.unlink(temp_file)
                except Exception as e:
                    # Log but don't fail if cleanup fails - this shouldn't affect functionality
                    logging.warning(f"Failed to delete temp file {temp_file}: {str(e)}")
                    # We'll just let Windows clean it up later
            
        # Return whatever transcript we got, empty string if we failed
        return transcript

    def _format_elevenlabs_diarized_transcript(self, words: list) -> str:
        """Format diarized words from ElevenLabs into a readable transcript with speaker labels.
        
        Args:
            words: List of words from the ElevenLabs response
            
        Returns:
            Formatted text with speaker labels
        """
        if not words:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        # Debug the first few words to understand structure
        print("\nFormatting transcript with the following word data structure:")
        sample_words = words[:3] if len(words) > 3 else words
        for i, word in enumerate(sample_words):
            print(f"Sample word {i}: {word}")
        
        for word_data in words:
            # Check various possible field names for speaker information
            speaker = None
            
            # Try different possible field names for speaker information
            if "speaker" in word_data:
                speaker = word_data.get("speaker")
            elif "speaker_id" in word_data:
                speaker = word_data.get("speaker_id")
            elif "speaker_turn" in word_data:
                speaker = word_data.get("speaker_turn")
            
            # If we still don't have speaker info, try to get it from a nested field
            if speaker is None and "speaker_data" in word_data:
                speaker_data = word_data.get("speaker_data", {})
                if isinstance(speaker_data, dict):
                    speaker = speaker_data.get("id") or speaker_data.get("speaker") or speaker_data.get("speaker_id")
            
            # If we can't find any speaker info, skip this word or use default
            if speaker is None:
                # For debugging, print the problematic word data
                print(f"Warning: No speaker info found in word data: {word_data}")
                # Use previous speaker if available, otherwise use "Unknown"
                speaker = current_speaker if current_speaker is not None else "Unknown"
            
            # Get the actual word text
            word = word_data.get("word", "")
            if not word and "text" in word_data:
                word = word_data.get("text", "")
            
            # Skip empty words
            if not word.strip():
                continue
            
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
        
        # Debug the result
        formatted_result = "\n\n".join(result)
        print(f"\nDiarized transcript result has {len(result)} speaker sections")
        
        return formatted_result

    def _format_elevenlabs_diarized_transcript_with_field(self, words: list, speaker_field: str) -> str:
        """Format diarized words from ElevenLabs into a readable transcript with speaker labels.
        
        Args:
            words: List of words from the ElevenLabs response
            speaker_field: Field name for speaker information
            
        Returns:
            Formatted text with speaker labels
        """
        if not words:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        for word_data in words:
            speaker = word_data.get(speaker_field)
            
            # If we can't find any speaker info, skip this word or use default
            if speaker is None:
                # For debugging, print the problematic word data
                print(f"Warning: No speaker info found in word data: {word_data}")
                # Use previous speaker if available, otherwise use "Unknown"
                speaker = current_speaker if current_speaker is not None else "Unknown"
            
            # Get the actual word text
            word = word_data.get("word", "")
            if not word and "text" in word_data:
                word = word_data.get("text", "")
            
            # Skip empty words
            if not word.strip():
                continue
            
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

    def _format_elevenlabs_diarized_transcript_from_segments(self, result: dict) -> str:
        """Format diarized transcript from ElevenLabs segments.
        
        Args:
            result: ElevenLabs response with diarization data
            
        Returns:
            Formatted text with speaker labels
        """
        if not result or 'diarization' not in result:
            return ""
        
        diarization = result['diarization']
        if not diarization:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        for segment in diarization:
            speaker = segment.get("speaker")
            
            # If we can't find any speaker info, skip this segment or use default
            if speaker is None:
                # For debugging, print the problematic segment data
                print(f"Warning: No speaker info found in segment data: {segment}")
                # Use previous speaker if available, otherwise use "Unknown"
                speaker = current_speaker if current_speaker is not None else "Unknown"
            
            # Get the actual segment text
            text = segment.get("text", "")
            
            # Skip empty segments
            if not text.strip():
                continue
            
            # If new speaker, start a new paragraph
            if speaker != current_speaker:
                # Add previous paragraph if it exists
                if current_text:
                    speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
                    result.append(f"{speaker_label}{''.join(current_text)}")
                    current_text = []
                
                current_speaker = speaker
            
            # Add segment to current text
            current_text.append(text)
        
        # Add the last paragraph
        if current_text:
            speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
            result.append(f"{speaker_label}{''.join(current_text)}")
        
        return "\n\n".join(result)

    def _format_elevenlabs_diarized_transcript_from_speakers(self, result: dict) -> str:
        """Format diarized transcript from ElevenLabs speakers.
        
        Args:
            result: ElevenLabs response with speakers data
            
        Returns:
            Formatted text with speaker labels
        """
        if not result or 'speakers' not in result:
            return ""
        
        speakers = result['speakers']
        if not speakers:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        for speaker in speakers:
            speaker_id = speaker.get("id")
            segments = speaker.get("segments", [])
            
            # If we can't find any speaker info, skip this speaker or use default
            if speaker_id is None:
                # For debugging, print the problematic speaker data
                print(f"Warning: No speaker info found in speaker data: {speaker}")
                # Use previous speaker if available, otherwise use "Unknown"
                speaker_id = current_speaker if current_speaker is not None else "Unknown"
            
            # If new speaker, start a new paragraph
            if speaker_id != current_speaker:
                # Add previous paragraph if it exists
                if current_text:
                    speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
                    result.append(f"{speaker_label}{''.join(current_text)}")
                    current_text = []
                
                current_speaker = speaker_id
            
            # Add segments to current text
            for segment in segments:
                text = segment.get("text", "")
                current_text.append(text)
        
        # Add the last paragraph
        if current_text:
            speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
            result.append(f"{speaker_label}{''.join(current_text)}")
        
        return "\n\n".join(result)

    def _transcribe_with_groq(self, segment: AudioSegment) -> str:
        """Transcribe audio using GROQ API.
        
        Args:
            segment: Audio segment to transcribe
            
        Returns:
            Transcription text
        """
        if not self.groq_api_key:
            logging.warning("GROQ API key not found")
            return ""
        
        temp_file = None
        file_obj = None
        transcript = ""
            
        try:
            # Convert segment to WAV for API
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
                temp_file = temp.name
                segment.export(temp_file, format="wav")
                
            # Get file size and adjust timeout accordingly
            file_size_kb = os.path.getsize(temp_file) / 1024
            
            # Add a minute of timeout for each 500KB of audio, with a minimum of 60 seconds
            timeout_seconds = max(60, int(file_size_kb / 500) * 60)
            logging.info(f"Setting GROQ timeout to {timeout_seconds} seconds for {file_size_kb:.2f} KB file")

            # Using OpenAI client since GROQ uses a compatible API
            from openai import OpenAI
            
            # Initialize client with GROQ base URL
            client = OpenAI(api_key=self.groq_api_key, base_url="https://api.groq.com/openai/v1")
            
            # Print API call details to terminal
            print("\n===== GROQ API CALL =====")
            print(f"File: {os.path.basename(temp_file)} (audio/wav)")
            print(f"Audio file size: {file_size_kb:.2f} KB")
            print(f"Timeout set to: {timeout_seconds} seconds")
            print("=========================\n")
            
            # Open and read the audio file
            with open(temp_file, "rb") as audio_file:
                # Make API call with timeout
                response = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3-turbo",  # GROQ's Whisper model (updated name)
                    language=self.recognition_language.split('-')[0],  # Use language code without region
                    timeout=timeout_seconds
                )
            
            # Process response
            if hasattr(response, 'text'):
                transcript = response.text
                
                # Print successful response info to terminal
                print("\n===== GROQ API RESPONSE =====")
                print(f"Response successfully received")
                if transcript:
                    text_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
                    print(f"Text preview: {text_preview}")
                print("============================\n")
            else:
                logging.error("Unexpected response format from GROQ API")
                print("\n===== GROQ API ERROR =====")
                print(f"Unexpected response format: {response}")
                print("==========================\n")
                
        except Exception as e:
            error_msg = f"Error with GROQ transcription: {str(e)}"
            logging.error(error_msg, exc_info=True)
            
            # Print exception details to terminal
            print("\n===== GROQ EXCEPTION =====")
            print(f"Error: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            print("==========================\n")
                
        finally:
            # Try to clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    # On Windows, sometimes we need to wait a moment before the file can be deleted
                    import time
                    time.sleep(0.5)
                    os.unlink(temp_file)
                except Exception as e:
                    # Log but don't fail if cleanup fails - this shouldn't affect functionality
                    logging.warning(f"Failed to delete temp file {temp_file}: {str(e)}")
                    # We'll just let Windows clean it up later
            
        # Return whatever transcript we got, empty string if we failed
        return transcript

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
        
        # Prepare a buffer outside the retry loop so we can close it properly
        buf = None
        transcript = ""
        
        try:
            while attempt <= max_retries:
                try:
                    logging.info(f"Deepgram transcription attempt {attempt+1}/{max_retries+1}")
                    
                    # Clean up previous buffer if it exists
                    if buf:
                        buf.close()
                        
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
                    
                    # Print API call details to terminal
                    print("\n===== DEEPGRAM API CALL =====")
                    print(f"Attempt: {attempt+1}/{max_retries+1}")
                    print(f"Model: {options.model}")
                    print(f"Language: {options.language}")
                    print(f"Smart Format: {options.smart_format}")
                    print(f"Diarize: {options.diarize}")
                    print(f"Profanity Filter: {options.profanity_filter}")
                    print(f"Redact: {options.redact}")
                    print(f"Alternatives: {options.alternatives}")
                    print(f"Buffer size: {buf.getbuffer().nbytes / 1024:.2f} KB")
                    print("==============================\n")
                    
                    # Set higher timeout for large files
                    timeout_seconds = max(60, int(buf.getbuffer().nbytes / (500 * 1024)) * 60)
                    logging.info(f"Setting Deepgram timeout to {timeout_seconds} seconds")
                    
                    # Make API call
                    response = self.deepgram_client.listen.rest.v("1").transcribe_file(
                        {"buffer": buf}, 
                        options,
                        timeout=timeout_seconds
                    )
                    
                    # Process response
                    response_json = json.loads(response.to_json(indent=4))
                    
                    # Print successful response info to terminal
                    print("\n===== DEEPGRAM API RESPONSE =====")
                    print(f"Request ID: {response_json.get('request_id', 'unknown')}")
                    
                    # Extract metadata
                    if "metadata" in response_json:
                        metadata = response_json["metadata"]
                        print(f"Duration: {metadata.get('duration', 'unknown')} seconds")
                        print(f"Channels: {metadata.get('channels', 'unknown')}")
                        print(f"Sample rate: {metadata.get('sample_rate', 'unknown')} Hz")
                    
                    # Extract transcript for preview
                    transcript_preview = ""
                    if "results" in response_json and response_json["results"].get("channels"):
                        alternatives = response_json["results"]["channels"][0].get("alternatives", [])
                        if alternatives and "transcript" in alternatives[0]:
                            transcript = alternatives[0]["transcript"]
                            transcript_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
                            print(f"Transcript preview: {transcript_preview}")
                    
                    print("=================================\n")
                    
                    # Check if diarization is enabled
                    is_diarized = deepgram_settings.get("diarize", False)
                    
                    # Check for results
                    if "results" in response_json and response_json["results"].get("channels"):
                        alternatives = response_json["results"]["channels"][0].get("alternatives", [])
                        
                        if alternatives and "transcript" in alternatives[0]:
                            transcript = alternatives[0]["transcript"]
                            
                            # Process diarization if enabled
                            if is_diarized and "words" in alternatives[0]:
                                transcript = self._format_deepgram_diarized_transcript(alternatives[0]["words"])
                            
                            # If we got a transcript, we can break out of the retry loop
                            break
                    
                    # If we get here, response structure wasn't as expected
                    logging.warning(f"Unexpected Deepgram response structure on attempt {attempt+1}")
                    
                    # Increment attempt counter and retry if needed
                    attempt += 1
                    if attempt <= max_retries:
                        logging.info(f"Retrying Deepgram transcription in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                
                except Exception as e:
                    logging.error(f"Deepgram transcription error on attempt {attempt+1}: {str(e)}", exc_info=True)
                    print(f"\n===== DEEPGRAM ERROR =====")
                    print(f"Attempt {attempt+1}/{max_retries+1}")
                    print(f"Error: {str(e)}")
                    print("===========================\n")
                    
                    # Increment attempt counter and retry if needed
                    attempt += 1
                    if attempt <= max_retries:
                        logging.info(f"Retrying Deepgram transcription in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        logging.error("Maximum retry attempts reached for Deepgram transcription")
                        break
        
        finally:
            # Clean up the buffer
            if buf:
                try:
                    buf.close()
                except Exception as e:
                    logging.warning(f"Error closing buffer: {str(e)}")
        
        # Return whatever transcript we have (or empty string on failure)
        return transcript

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
                combined.export(file_path, format="mp3")
                logging.info(f"Audio saved to {file_path}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error saving audio: {str(e)}", exc_info=True)
            return False
