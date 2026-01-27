"""
Whisper STT provider implementation.
"""

import os
import sys
import tempfile
from typing import Optional
from pydub import AudioSegment

from .base import BaseSTTProvider


def _ensure_whisper_assets():
    """Ensure Whisper asset files are accessible in PyInstaller bundles.

    In a frozen PyInstaller app, whisper's audio.py looks for mel_filters.npz
    at os.path.dirname(whisper.__file__) / assets /. If the assets were bundled
    to a different location within _MEIPASS, copy them to where whisper expects.
    """
    if not getattr(sys, 'frozen', False):
        return

    try:
        import whisper as _whisper_pkg
        whisper_dir = os.path.dirname(_whisper_pkg.__file__)
        assets_dir = os.path.join(whisper_dir, 'assets')
        mel_path = os.path.join(assets_dir, 'mel_filters.npz')

        if os.path.exists(mel_path):
            return  # Assets already in place

        # Check if assets are elsewhere in _MEIPASS
        meipass = getattr(sys, '_MEIPASS', '')
        alt_assets = os.path.join(meipass, 'whisper', 'assets')
        alt_mel = os.path.join(alt_assets, 'mel_filters.npz')

        if os.path.exists(alt_mel):
            # Assets are in _MEIPASS/whisper/assets but whisper.__file__
            # points elsewhere. Create the expected directory and symlink.
            os.makedirs(assets_dir, exist_ok=True)
            for fname in os.listdir(alt_assets):
                src = os.path.join(alt_assets, fname)
                dst = os.path.join(assets_dir, fname)
                if not os.path.exists(dst):
                    try:
                        os.symlink(src, dst)
                    except OSError:
                        import shutil
                        shutil.copy2(src, dst)
    except Exception:
        pass  # Best-effort; transcribe() will report the real error


class WhisperProvider(BaseSTTProvider):
    """Implementation of the local Whisper STT provider."""

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "whisper"

    @property
    def requires_api_key(self) -> bool:
        """Whisper runs locally and does not require an API key."""
        return False

    @property
    def supports_diarization(self) -> bool:
        """Local Whisper does not support speaker diarization."""
        return False

    @property
    def is_configured(self) -> bool:
        """Check if Whisper is available on this system."""
        return self.is_available

    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the Whisper provider.

        Args:
            api_key: Not used for local Whisper
            language: Language code for speech recognition
        """
        super().__init__(api_key, language)
        self.is_available = self._check_whisper_available()

    def test_connection(self) -> bool:
        """Test if Whisper is available.

        Returns:
            True if Whisper can be imported and used
        """
        return self.is_available

    def _check_whisper_available(self) -> bool:
        """Check if Whisper is available on the system.

        Returns:
            True if Whisper is available, False otherwise
        """
        try:
            import whisper
            self.logger.info("Local Whisper model is available")
            return True
        except ImportError:
            self.logger.warning("Local Whisper model is not available")
            return False

    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using local Whisper model.

        Args:
            segment: Audio segment to transcribe

        Returns:
            Transcription text
        """
        if not self.is_available:
            self.logger.warning("Whisper is not available")
            return ""

        temp_file = None
        transcript = ""

        try:
            # Import inside function to avoid startup delays
            import whisper

            # Ensure asset files are accessible in bundled apps
            _ensure_whisper_assets()
            
            # Convert segment to WAV for Whisper
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
                temp_file = temp.name
                segment.export(temp_file, format="wav")
            
            # Get file size for logging
            file_size_kb = os.path.getsize(temp_file) / 1024
            
            # Print API call details to terminal
            self.logger.debug("\n===== LOCAL WHISPER TRANSCRIPTION =====")
            self.logger.debug(f"File: {os.path.basename(temp_file)} (audio/wav)")
            self.logger.debug(f"Audio file size: {file_size_kb:.2f} KB")
            self.logger.debug(f"Language: {self.language}")
            self.logger.debug("======================================\n")
            
            # Load model - use turbo model (default since 2025, better accuracy than small)
            model = whisper.load_model("turbo")
            
            # Perform transcription
            result = model.transcribe(
                temp_file,
                language=self.language.split('-')[0],  # Use language code without region
                fp16=False  # Avoid GPU errors on some systems
            )
            
            # Extract transcript text
            if "text" in result:
                transcript = result["text"].strip()
                
                # Print successful response info to terminal
                self.logger.debug("\n===== WHISPER RESULT =====")
                if transcript:
                    text_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
                    self.logger.debug(f"Text preview: {text_preview}")
                self.logger.debug("========================\n")
            else:
                self.logger.error("Unexpected response format from Whisper")
            
        except Exception as e:
            error_msg = f"Error with Whisper transcription: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            # Print exception details to terminal
            self.logger.debug("\n===== WHISPER EXCEPTION =====")
            self.logger.debug(f"Error: {str(e)}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            self.logger.debug("============================\n")
            
        finally:
            # Try to clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    # Log but don't fail if cleanup fails - this shouldn't affect functionality
                    self.logger.warning(f"Failed to delete temp file {temp_file}: {str(e)}")
            
        # Return whatever transcript we got, empty string if we failed
        return transcript
