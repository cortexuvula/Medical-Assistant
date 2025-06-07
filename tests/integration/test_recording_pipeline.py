"""Test complete recording pipeline integration."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import tempfile
from pathlib import Path
import time
from pydub import AudioSegment

from recording_manager import RecordingManager
from audio import AudioHandler
from ai_processor import AIProcessor
from database import Database
from processing_queue import ProcessingQueue


class TestRecordingPipeline:
    """Test full recording pipeline integration."""
    
    @pytest.fixture
    def temp_db_path(self, temp_dir):
        """Create temporary database path."""
        return temp_dir / "test_pipeline.db"
    
    @pytest.fixture
    def pipeline_components(self, temp_db_path, mock_api_keys):
        """Create all pipeline components."""
        with patch.dict('os.environ', mock_api_keys):
            # Create audio handler first
            audio_handler = AudioHandler(
                deepgram_api_key=mock_api_keys['DEEPGRAM_API_KEY'],
                elevenlabs_api_key=mock_api_keys['ELEVENLABS_API_KEY'],
                groq_api_key=mock_api_keys['GROQ_API_KEY']
            )
            
            # Create mock status manager
            mock_status_manager = Mock()
            mock_status_manager.update_status = Mock()
            mock_status_manager.show_progress = Mock()
            mock_status_manager.hide_progress = Mock()
            mock_status_manager.update_provider_info = Mock()
            
            # Create recording manager with dependencies
            recording_manager = RecordingManager(
                audio_handler=audio_handler,
                status_manager=mock_status_manager
            )
            
            components = {
                'recording_manager': recording_manager,
                'audio_handler': audio_handler,
                'ai_processor': AIProcessor(),
                'database': Database(str(temp_db_path)),
                'processing_queue': ProcessingQueue(),
                'status_manager': mock_status_manager
            }
            
            # Initialize database
            components['database'].create_tables()
            
            yield components
    
    @pytest.fixture
    def mock_audio_stream(self):
        """Create mock audio stream data."""
        sample_rate = 44100
        duration = 3.0  # 3 seconds of audio
        
        # Generate audio segments (simulate chunks coming from microphone)
        chunk_size = 1024
        total_samples = int(sample_rate * duration)
        
        segments = []
        for i in range(0, total_samples, chunk_size):
            chunk = np.random.randn(min(chunk_size, total_samples - i)) * 0.1
            segments.append((chunk * 32767).astype(np.int16))
        
        return segments
    
    @pytest.mark.integration
    def test_complete_recording_flow(self, pipeline_components, mock_audio_stream):
        """Test complete flow: record → transcribe → process → save."""
        recording_manager = pipeline_components['recording_manager']
        audio_handler = pipeline_components['audio_handler']
        ai_processor = pipeline_components['ai_processor']
        database = pipeline_components['database']
        
        # Mock transcription and AI responses
        with patch.object(audio_handler, 'transcribe_audio') as mock_transcribe:
            with patch.object(ai_processor, 'create_soap_note') as mock_generate_soap:
                mock_transcribe.return_value = "Patient presents with persistent cough for one week."
                
                mock_generate_soap.return_value = {
                    "success": True,
                    "text": "S: Persistent cough x1 week\nO: Lungs clear\nA: Viral URI\nP: Supportive care"
                }
                
                # Start recording
                audio_received = []
                def capture_audio(audio_data):
                    audio_received.append(audio_data)
                    recording_manager.add_audio_segment(audio_data)
                
                recording_manager.start_recording(capture_audio)
                
                # Simulate audio streaming
                for segment in mock_audio_stream[:10]:  # Use first 10 segments
                    capture_audio(segment)
                    time.sleep(0.01)  # Simulate real-time
                
                # Stop recording
                recording_data = recording_manager.stop_recording()
                
                assert recording_data is not None
                assert recording_data['segment_count'] == 10
                assert recording_data['duration'] > 0
                
                # Get combined audio from recording data
                audio_segment = recording_data['audio']
                assert audio_segment is not None
                
                # Transcribe
                transcript_text = audio_handler.transcribe_audio(audio_segment)
                assert transcript_text == "Patient presents with persistent cough for one week."
                
                # Generate SOAP note
                soap_result = ai_processor.create_soap_note(transcript_text)
                assert soap_result["success"] is True
                
                # Save to database
                rec_id = database.add_recording("test_recording.mp3")
                success = database.update_recording(
                    rec_id,
                    transcript=transcript_text,
                    soap_note=soap_result["text"]
                )
                assert success is True
                
                # Verify saved data
                saved_recording = database.get_recording(rec_id)
                assert saved_recording is not None
                assert "persistent cough" in saved_recording['transcript']
                assert "Viral URI" in saved_recording['soap_note']
    
    @pytest.mark.integration
    def test_recording_with_pause_resume(self, pipeline_components, mock_audio_stream):
        """Test recording with pause and resume functionality."""
        recording_manager = pipeline_components['recording_manager']
        
        segments_received = []
        def capture_audio(audio_data):
            segments_received.append(audio_data)
            if not recording_manager.is_paused:
                recording_manager.add_audio_segment(audio_data)
        
        # Start recording
        recording_manager.start_recording(capture_audio)
        
        # Record first part
        for segment in mock_audio_stream[:5]:
            capture_audio(segment)
        
        # Pause
        recording_manager.pause_recording()
        pause_duration = 0.1
        time.sleep(pause_duration)
        
        # Try to add segments while paused (should not be added)
        for segment in mock_audio_stream[5:7]:
            capture_audio(segment)
        
        # Resume
        recording_manager.resume_recording()
        
        # Record more
        for segment in mock_audio_stream[7:10]:
            capture_audio(segment)
        
        # Stop
        recording_data = recording_manager.stop_recording()
        
        # Should have 8 segments (5 + 3), not 10
        assert recording_data['segment_count'] == 8
        assert recording_data['pause_duration'] >= pause_duration * 0.9  # Allow some tolerance
    
    @pytest.mark.integration
    def test_queue_processing_pipeline(self, pipeline_components, mock_audio_stream):
        """Test background queue processing of recordings."""
        queue = pipeline_components['processing_queue']
        database = pipeline_components['database']
        
        # Add recording to database
        rec_id = database.add_recording("queued_recording.mp3")
        
        # Create task data
        audio_data = np.concatenate(mock_audio_stream[:10])
        task_data = {
            'recording_id': rec_id,
            'audio_data': audio_data,
            'context': 'Follow-up visit'
        }
        
        # Mock the internal processing method
        with patch.object(queue, '_process_recording') as mock_process:
            # Add to queue
            task_id = queue.add_recording(task_data)
            assert task_id is not None
            
            # Wait a bit for the background thread to pick it up
            time.sleep(0.1)
            
            # Check that task was added
            with queue.lock:
                assert task_id in queue.active_tasks
                
            # Check the recording is in the database
            recording = database.get_recording(rec_id)
            assert recording is not None
    
    @pytest.mark.integration
    def test_error_handling_in_pipeline(self, pipeline_components):
        """Test error handling throughout the pipeline."""
        recording_manager = pipeline_components['recording_manager']
        audio_handler = pipeline_components['audio_handler']
        ai_processor = pipeline_components['ai_processor']
        database = pipeline_components['database']
        
        # Test with empty audio
        recording_manager.start_recording(lambda x: None)
        recording_data = recording_manager.stop_recording()
        
        # Should handle gracefully
        assert recording_data is not None
        assert recording_data['segment_count'] == 0
        
        # Test transcription failure
        with patch.object(audio_handler, 'transcribe_audio') as mock_transcribe:
            mock_transcribe.return_value = ""  # Empty string indicates failure
            
            # Create a dummy AudioSegment
            dummy_segment = AudioSegment.silent(duration=1000)  # 1 second of silence
            result = audio_handler.transcribe_audio(dummy_segment)
            assert result == ""
        
        # Test AI processing failure
        with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
            mock_adjust.side_effect = Exception("API Error")
            
            result = ai_processor.refine_text("test")
            assert result["success"] is False
            assert "error" in result
    
    @pytest.mark.integration
    def test_multiple_recordings_sequential(self, pipeline_components):
        """Test multiple recordings in sequence."""
        recording_manager = pipeline_components['recording_manager']
        database = pipeline_components['database']
        
        recording_ids = []
        
        for i in range(3):
            # Start recording
            recording_manager.start_recording(lambda x: recording_manager.add_audio_segment(x))
            
            # Add some audio
            for j in range(5):
                segment = np.ones(1000) * (i + 1)  # Different pattern for each
                recording_manager.add_audio_segment(segment)
            
            # Stop
            recording_data = recording_manager.stop_recording()
            assert recording_data['segment_count'] == 5
            
            # Save to database
            rec_id = database.add_recording(f"recording_{i}.mp3")
            recording_ids.append(rec_id)
        
        # Verify all recordings saved
        all_recordings = database.get_all_recordings()
        assert len(all_recordings) >= 3
        
        for rec_id in recording_ids:
            assert any(r['id'] == rec_id for r in all_recordings)
    
    @pytest.mark.integration
    def test_concurrent_recording_and_processing(self, pipeline_components):
        """Test recording while previous recording is being processed."""
        recording_manager = pipeline_components['recording_manager']
        queue = pipeline_components['processing_queue']
        
        # First recording
        recording_manager.start_recording(lambda x: recording_manager.add_audio_segment(x))
        for i in range(5):
            recording_manager.add_audio_segment(np.ones(1000))
        
        first_recording = recording_manager.stop_recording()
        
        # Queue first recording for processing
        task1 = {
            'recording_id': 1,
            'audio_data': first_recording['audio']
        }
        queue.add_recording(task1)
        
        # Start second recording immediately (start_recording resets the state)
        recording_manager.start_recording(lambda x: recording_manager.add_audio_segment(x))
        
        # Add audio to second recording while first would process in background
        for i in range(3):
            recording_manager.add_audio_segment(np.ones(500))
            time.sleep(0.01)
        
        # Stop second recording
        second_recording = recording_manager.stop_recording()
        
        # Both should complete successfully
        assert first_recording['segment_count'] == 5
        assert second_recording['segment_count'] == 3
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_long_recording_session(self, pipeline_components):
        """Test handling of long recording sessions."""
        recording_manager = pipeline_components['recording_manager']
        
        recording_manager.start_recording(lambda x: recording_manager.add_audio_segment(x))
        
        # Simulate 2 minutes of recording with periodic pauses
        segment_count = 0
        for minute in range(2):
            for second in range(60):
                # Add audio segment
                segment = np.random.randn(1000) * 0.1
                recording_manager.add_audio_segment(segment)
                segment_count += 1
                
                # Pause every 30 seconds
                if second == 30:
                    recording_manager.pause_recording()
                    time.sleep(0.1)
                    recording_manager.resume_recording()
                
                # Small delay to simulate real-time
                time.sleep(0.001)
        
        # Stop recording
        recording_data = recording_manager.stop_recording()
        
        assert recording_data['segment_count'] == segment_count
        assert recording_data['duration'] >= 0.1  # At least 0.1 seconds (sped up)
        assert recording_data['pause_duration'] > 0
        
        # Verify memory usage is reasonable
        audio_segment = recording_data['audio']
        if audio_segment:
            # AudioSegment length is in milliseconds, convert to sample count
            expected_samples = segment_count * 1000
            actual_samples = len(audio_segment.raw_data) // 2  # 16-bit samples
            # Allow some tolerance due to audio processing
            assert abs(actual_samples - expected_samples) < expected_samples * 0.1