"""
SOAP Audio Processor Module

Handles audio processing for SOAP note recording including numpy array handling,
audio segment creation, silence detection, and incremental combination logic.
"""

import logging
import numpy as np
from pydub import AudioSegment


class SOAPAudioProcessor:
    """Manages SOAP-specific audio processing functionality."""
    
    def __init__(self, parent_app):
        """Initialize the SOAP audio processor.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        
    def process_soap_callback(self, audio_data) -> None:
        """Callback for SOAP note recording using RecordingManager."""
        # Add audio segment to recording manager
        if isinstance(audio_data, np.ndarray):
            self.app.recording_manager.add_audio_segment(audio_data)
            # Log for debugging
            logging.debug(f"Added audio segment to RecordingManager: shape={audio_data.shape}, dtype={audio_data.dtype}")
        
        # Original processing for UI updates
        try:
            # Directly handle numpy array data for potential efficiency
            if isinstance(audio_data, np.ndarray):
                max_amp = np.abs(audio_data).max()
                
                # Basic silence detection - adjust threshold as needed
                if self.app.audio_handler.soap_mode or max_amp > 0.0001: # Avoid processing completely silent chunks unless in SOAP mode
                    try:
                        # Ensure data is in the correct format (int16)
                        if audio_data.dtype != np.int16:
                            # Scale float32/64 [-1.0, 1.0] to int16 [-32768, 32767]
                            if audio_data.dtype in [np.float32, np.float64]:
                                # Clip to prevent overflow
                                audio_clipped = np.clip(audio_data, -1.0, 1.0)
                                audio_data = (audio_clipped * 32767).astype(np.int16)
                            else:
                                # Attempt conversion for other types, log warning
                                logging.warning(f"Unexpected audio data type {audio_data.dtype}, attempting conversion to int16")
                                audio_data = audio_data.astype(np.int16)
                        
                        new_segment = AudioSegment(
                            data=audio_data.tobytes(), 
                            sample_width=self.app.audio_handler.sample_width, 
                            frame_rate=self.app.audio_handler.sample_rate,
                            channels=self.app.audio_handler.channels
                        )
                        # Add to segments list for later processing
                        self.app.pending_soap_segments.append(new_segment)
                        
                        # Visual feedback that audio is being recorded
                        self.app.after(0, lambda: self.app.update_status("Recording SOAP note...", "info"))
                        return # Successfully processed, exit callback
                    except Exception as e:
                        logging.error(f"Error processing direct SOAP audio data (np.ndarray): {str(e)}", exc_info=True)
                        # Fall through to standard processing if direct fails
                        logging.warning("Falling back to standard audio processing for np.ndarray.")
                else:
                    logging.debug(f"SOAP audio segment skipped (np.ndarray) - amplitude too low ({max_amp:.8f})")
                    # Do not return here, let it potentially fall through if needed, although unlikely for low amplitude
            
            # Fall back to standard processing for non-ndarray types or if direct processing failed
            new_segment, _ = self.app.audio_handler.process_audio_data(audio_data)
            
            if new_segment:
                # Add to segments list for later processing
                self.app.pending_soap_segments.append(new_segment)
                
                # Visual feedback that audio is being recorded
                self.app.after(0, lambda: self.app.update_status("Recording SOAP note...", "info"))
            else:
                # Log the issue with audio data
                logging.warning(f"SOAP recording: No audio segment created via standard process from data of type {type(audio_data)}")
                max_amp_fallback = 0
                if isinstance(audio_data, np.ndarray):
                    max_amp_fallback = np.abs(audio_data).max()
                elif hasattr(audio_data, 'max_dBFS'): # Check for AudioData attribute
                    # Note: max_dBFS is logarithmic, not directly comparable to amplitude
                    max_amp_fallback = audio_data.max_dBFS 
                    logging.warning(f"SOAP recording: AudioData max_dBFS was {max_amp_fallback}")
                else:
                     logging.warning("SOAP recording: Could not determine max amplitude/dBFS for this data type.")
                     
                
                if isinstance(audio_data, np.ndarray):
                     logging.warning(f"SOAP recording (standard process): Max amplitude was {max_amp_fallback}")
                
                # Visual feedback for user if likely low volume
                if isinstance(audio_data, np.ndarray) and max_amp_fallback < 0.005:
                    self.app.after(0, lambda: self.app.update_status("Audio level too low - check microphone settings", "warning"))
                elif hasattr(audio_data, 'max_dBFS') and audio_data.max_dBFS < -40: # Heuristic for low dBFS
                     self.app.after(0, lambda: self.app.update_status("Audio level might be low - check microphone settings", "warning"))
                    
        except Exception as e:
            logging.error(f"Critical Error in SOAP callback: {str(e)}", exc_info=True)

        # --- Incremental Combination Logic ---            
        if new_segment:
            # Add the newly created segment to the pending list
            self.app.pending_soap_segments.append(new_segment)
            
            # Check if we reached the threshold to combine pending segments
            if len(self.app.pending_soap_segments) >= self.app.soap_combine_threshold:
                logging.debug(f"SOAP callback: Reached threshold ({self.app.soap_combine_threshold}), combining {len(self.app.pending_soap_segments)} pending segments.")
                # Combine the pending segments
                chunk_to_add = self.app.audio_handler.combine_audio_segments(self.app.pending_soap_segments)
                
                if chunk_to_add:
                    # Add the newly combined chunk to our list of larger chunks
                    self.app.combined_soap_chunks.append(chunk_to_add)
                    # logging.info(f"SOAP chunk combined and added. Total chunks: {len(self.app.combined_soap_chunks)}")
                else:
                    logging.warning("SOAP callback: Combining pending segments resulted in None.")
                    
                # Clear the pending list
                self.app.pending_soap_segments = []

            # Visual feedback (can be less frequent if needed)
            # Update status less frequently to avoid flooding UI updates
            if len(self.app.pending_soap_segments) % 10 == 1: # Update status every 10 segments added
                 self.app.after(0, lambda: self.app.update_status("Recording SOAP note...", "info"))
        # else: # Removed logging for no segment created to reduce noise
            # logging.warning(f"SOAP recording: No audio segment created from data of type {type(audio_data)}")