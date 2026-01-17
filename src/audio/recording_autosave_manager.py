"""
Recording Auto-Save Manager Module

Periodically saves audio data during recordings to prevent data loss from crashes.
On application startup, checks for incomplete recordings and provides recovery.

Thread Safety:
    This class uses threading.Event for clean shutdown coordination.
    The save thread is a daemon to prevent blocking application exit.
"""

import json
import os
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, TYPE_CHECKING

import numpy as np
from pydub import AudioSegment

if TYPE_CHECKING:
    from audio.audio_state_manager import AudioStateManager

from managers.data_folder_manager import data_folder_manager
from settings.settings import SETTINGS
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class RecordingAutoSaveManager:
    """Manages periodic auto-saving of audio during recordings.

    This class saves audio segments incrementally to disk during recordings,
    allowing recovery if the application crashes or is terminated unexpectedly.

    File Structure:
        AppData/recording_autosave/
            session_{uuid}/
                metadata.json    - Recording state and metadata
                chunk_001.raw   - Raw audio bytes (numpy int16)
                chunk_002.raw
                ...
    """

    METADATA_FILENAME = "metadata.json"
    METADATA_VERSION = "1.0"

    def __init__(self, interval_seconds: Optional[int] = None):
        """Initialize the RecordingAutoSaveManager.

        Args:
            interval_seconds: Save interval in seconds (default from settings)
        """
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._save_complete = threading.Event()
        self._save_complete.set()  # Initially set (no save in progress)

        # Configuration
        self._interval_seconds = interval_seconds or SETTINGS.get("recording_autosave_interval", 60)

        # Session state (protected by _lock)
        self._is_running = False
        self._session_id: Optional[str] = None
        self._session_dir: Optional[Path] = None
        self._audio_state_manager: Optional['AudioStateManager'] = None
        self._metadata: Dict[str, Any] = {}
        self._chunks_saved: int = 0
        self._last_segment_index: int = 0
        self._last_chunk_index: int = 0

        # Save thread
        self._save_thread: Optional[threading.Thread] = None

        # Autosave directory
        self._autosave_dir = data_folder_manager.app_data_folder / "recording_autosave"
        self._ensure_autosave_dir()

        logger.info(f"RecordingAutoSaveManager initialized with {self._interval_seconds}s interval")

    def _ensure_autosave_dir(self) -> None:
        """Ensure the autosave directory exists."""
        self._autosave_dir.mkdir(exist_ok=True)

    @property
    def is_running(self) -> bool:
        """Thread-safe check if auto-save is running."""
        with self._lock:
            return self._is_running

    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID."""
        with self._lock:
            return self._session_id

    def start(self, audio_state_manager: 'AudioStateManager', metadata: Optional[Dict[str, Any]] = None) -> None:
        """Start auto-save for a new recording session.

        Args:
            audio_state_manager: Reference to get audio data
            metadata: Optional recording metadata (patient_context, device_name, etc.)
        """
        with self._lock:
            if self._is_running:
                logger.warning("Recording auto-save is already running")
                return

            # Check if enabled in settings
            if not SETTINGS.get("recording_autosave_enabled", True):
                logger.info("Recording auto-save is disabled in settings")
                return

            # Generate new session
            self._session_id = str(uuid.uuid4())[:8]
            self._session_dir = self._autosave_dir / f"session_{self._session_id}"
            self._session_dir.mkdir(exist_ok=True)

            # Store references
            self._audio_state_manager = audio_state_manager
            self._chunks_saved = 0
            self._last_segment_index = 0
            self._last_chunk_index = 0

            # Initialize metadata
            self._metadata = {
                "version": self.METADATA_VERSION,
                "session_id": self._session_id,
                "status": "recording",
                "start_time": datetime.now().isoformat(),
                "last_save_time": None,
                "patient_context": metadata.get("patient_context", "") if metadata else "",
                "device_name": metadata.get("device_name", "") if metadata else "",
                "sample_rate": None,
                "sample_width": None,
                "channels": None,
                "total_chunks": 0,
                "estimated_duration_seconds": 0.0,
            }

            # Save initial metadata
            self._save_metadata()

            # Start save loop
            self._is_running = True
            self._stop_event.clear()

            self._save_thread = threading.Thread(
                target=self._save_loop,
                daemon=True,
                name=f"RecordingAutoSave-{self._session_id}"
            )
            self._save_thread.start()

        logger.info(f"Started recording auto-save session {self._session_id}")

    def stop(self, completed_successfully: bool = False, timeout: float = 5.0) -> None:
        """Stop auto-save and optionally clean up files.

        Args:
            completed_successfully: If True, delete auto-save files (recording completed normally)
            timeout: Maximum time to wait for save completion
        """
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            self._stop_event.set()

            session_id = self._session_id
            session_dir = self._session_dir
            save_thread = self._save_thread

        # Wait for save thread to finish
        if save_thread and save_thread.is_alive():
            save_thread.join(timeout=timeout)

        # Wait for any in-progress save
        if not self._save_complete.wait(timeout=timeout):
            logger.warning("Save did not complete within timeout")

        if completed_successfully:
            # Recording completed normally - first update status, then clean up files
            # This ensures that even if cleanup fails, recovery won't be triggered
            # (recovery only looks for "recording" or "incomplete" status)
            with self._lock:
                if self._metadata and session_dir:
                    self._metadata["status"] = "completed"
                    try:
                        metadata_path = session_dir / self.METADATA_FILENAME
                        with open(metadata_path, 'w', encoding='utf-8') as f:
                            json.dump(self._metadata, f, indent=2)
                    except Exception as e:
                        logger.warning(f"Could not update session status to completed: {e}")

            # Now try to clean up the files
            self._cleanup_session(session_dir)
            logger.info(f"Recording auto-save session {session_id} completed and cleaned up")
        else:
            # Recording was cancelled or app is closing - mark as incomplete
            with self._lock:
                if self._metadata:
                    self._metadata["status"] = "incomplete"
                    self._save_metadata()
            logger.info(f"Recording auto-save session {session_id} marked as incomplete")

        # Clear state
        with self._lock:
            self._session_id = None
            self._session_dir = None
            self._audio_state_manager = None
            self._metadata = {}
            self._save_thread = None

    def _save_loop(self) -> None:
        """Background thread that periodically saves audio."""
        logger.debug("Auto-save loop started")

        while not self._stop_event.is_set():
            # Wait for interval (interruptible)
            if self._stop_event.wait(timeout=self._interval_seconds):
                # Stop event was set
                break

            # Perform save
            try:
                self._perform_save()
            except Exception as e:
                logger.error(f"Error in auto-save: {e}", exc_info=True)

        logger.debug("Auto-save loop stopped")

    def _perform_save(self) -> bool:
        """Save current audio state incrementally.

        Returns:
            True if save was successful
        """
        self._save_complete.clear()

        try:
            with self._lock:
                if not self._is_running or not self._audio_state_manager:
                    return False

                asm = self._audio_state_manager
                session_dir = self._session_dir

            # Get audio data from AudioStateManager
            # We need to access the internal state safely
            audio_data = self._extract_audio_for_save(asm)

            if audio_data is None:
                logger.debug("No new audio data to save")
                return True

            raw_bytes, metadata_update = audio_data

            # Save raw audio chunk
            with self._lock:
                self._chunks_saved += 1
                chunk_num = self._chunks_saved
                chunk_path = session_dir / f"chunk_{chunk_num:04d}.raw"

            # Write raw bytes to file
            with open(chunk_path, 'wb') as f:
                f.write(raw_bytes)

            # Update metadata
            with self._lock:
                self._metadata.update(metadata_update)
                self._metadata["total_chunks"] = self._chunks_saved
                self._metadata["last_save_time"] = datetime.now().isoformat()
                self._save_metadata()

            logger.info(f"Auto-saved chunk {chunk_num} ({len(raw_bytes)} bytes)")
            return True

        except Exception as e:
            logger.error(f"Error performing auto-save: {e}", exc_info=True)
            return False
        finally:
            self._save_complete.set()

    def _extract_audio_for_save(self, asm: 'AudioStateManager') -> Optional[tuple]:
        """Extract audio data from AudioStateManager for saving.

        This method accesses the AudioStateManager's combined audio
        and extracts just the portion since the last save.

        Args:
            asm: AudioStateManager instance

        Returns:
            Tuple of (raw_bytes, metadata_dict) or None if no new data
        """
        try:
            # Get combined audio (this triggers internal segment combining)
            combined = asm.get_combined_audio()

            if combined is None or len(combined) == 0:
                return None

            # Get audio format info
            recording_meta = asm.get_recording_metadata()

            # Export combined audio as raw bytes
            # We save the entire combined audio each time for simplicity
            # (incremental would be more complex with segment combining)
            raw_bytes = combined.raw_data

            metadata_update = {
                "sample_rate": combined.frame_rate,
                "sample_width": combined.sample_width,
                "channels": combined.channels,
                "estimated_duration_seconds": len(combined) / 1000.0,  # pydub uses milliseconds
            }

            return (raw_bytes, metadata_update)

        except Exception as e:
            logger.error(f"Error extracting audio for save: {e}")
            return None

    def _save_metadata(self) -> None:
        """Save metadata to JSON file. Must be called within lock or after acquiring it."""
        if not self._session_dir:
            return

        metadata_path = self._session_dir / self.METADATA_FILENAME
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")

    def _cleanup_session(self, session_dir: Optional[Path]) -> bool:
        """Delete a session directory and all its contents.

        Args:
            session_dir: Path to the session directory to delete

        Returns:
            True if cleanup was successful, False otherwise
        """
        if not session_dir:
            return True

        if not session_dir.exists():
            return True

        try:
            shutil.rmtree(session_dir)
            logger.debug(f"Cleaned up session directory: {session_dir}")
            return True
        except PermissionError as e:
            logger.warning(f"Permission denied cleaning up session (files may be in use): {session_dir} - {e}")
            return False
        except Exception as e:
            logger.error(f"Error cleaning up session {session_dir}: {e}")
            return False

    # =========================================================================
    # RECOVERY METHODS
    # =========================================================================

    def has_incomplete_recording(self) -> bool:
        """Check if there's an incomplete recording to recover.

        Also cleans up any "completed" sessions that should have been deleted.

        Returns:
            True if an incomplete recording session exists
        """
        self._ensure_autosave_dir()

        for session_dir in self._autosave_dir.iterdir():
            if session_dir.is_dir() and session_dir.name.startswith("session_"):
                metadata_path = session_dir / self.METADATA_FILENAME
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        status = metadata.get("status")
                        if status in ["recording", "incomplete"]:
                            return True
                        elif status == "completed":
                            # This session should have been cleaned up - try again
                            logger.info(f"Cleaning up leftover completed session: {session_dir.name}")
                            self._cleanup_session(session_dir)
                    except Exception as e:
                        logger.warning(f"Error reading session metadata: {e}")

        return False

    def get_recovery_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the recoverable recording.

        Returns:
            Dictionary with session info, or None if no recoverable session
        """
        self._ensure_autosave_dir()

        for session_dir in self._autosave_dir.iterdir():
            if session_dir.is_dir() and session_dir.name.startswith("session_"):
                metadata_path = session_dir / self.METADATA_FILENAME
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)

                        if metadata.get("status") in ["recording", "incomplete"]:
                            # Count chunk files
                            chunk_count = len(list(session_dir.glob("chunk_*.raw")))

                            return {
                                "session_id": metadata.get("session_id"),
                                "session_dir": str(session_dir),
                                "start_time": metadata.get("start_time"),
                                "last_save_time": metadata.get("last_save_time"),
                                "patient_context": metadata.get("patient_context", ""),
                                "estimated_duration_seconds": metadata.get("estimated_duration_seconds", 0),
                                "chunk_count": chunk_count,
                                "sample_rate": metadata.get("sample_rate"),
                                "sample_width": metadata.get("sample_width"),
                                "channels": metadata.get("channels"),
                            }
                    except Exception as e:
                        logger.warning(f"Error reading session for recovery info: {e}")

        return None

    def recover_recording(self) -> Optional[AudioSegment]:
        """Recover audio from an incomplete session.

        Returns:
            Combined AudioSegment or None if recovery fails
        """
        recovery_info = self.get_recovery_info()
        if not recovery_info:
            logger.warning("No incomplete recording found for recovery")
            return None

        session_dir = Path(recovery_info["session_dir"])
        sample_rate = recovery_info.get("sample_rate", 48000)
        sample_width = recovery_info.get("sample_width", 2)
        channels = recovery_info.get("channels", 1)

        try:
            # Find and sort chunk files
            chunk_files = sorted(session_dir.glob("chunk_*.raw"))

            if not chunk_files:
                logger.warning("No chunk files found for recovery")
                return None

            # Read the last chunk (contains full combined audio)
            # Since we save the full combined audio each time, we just need the last one
            last_chunk = chunk_files[-1]

            with open(last_chunk, 'rb') as f:
                raw_bytes = f.read()

            if not raw_bytes:
                logger.warning("Empty chunk file")
                return None

            # Create AudioSegment from raw bytes
            recovered_audio = AudioSegment(
                data=raw_bytes,
                sample_width=sample_width,
                frame_rate=sample_rate,
                channels=channels
            )

            logger.info(f"Recovered {len(recovered_audio) / 1000:.1f} seconds of audio "
                       f"from session {recovery_info['session_id']}")

            return recovered_audio

        except Exception as e:
            logger.error(f"Error recovering recording: {e}", exc_info=True)
            return None

    def cleanup_recovery_files(self) -> None:
        """Delete all auto-save files (after successful recovery or user decline)."""
        self._ensure_autosave_dir()

        for session_dir in self._autosave_dir.iterdir():
            if session_dir.is_dir() and session_dir.name.startswith("session_"):
                self._cleanup_session(session_dir)

        logger.info("Cleaned up all recovery files")

    def get_autosave_directory(self) -> Path:
        """Get the autosave directory path."""
        return self._autosave_dir
