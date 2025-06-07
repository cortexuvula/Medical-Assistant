# Testing Implementation Roadmap

## Quick Start Guide

### Step 1: Create Testing Infrastructure (Day 1-2)

1. **Create requirements-dev.txt**
```bash
pytest==7.4.3
pytest-cov==4.1.0
pytest-qt==4.2.0
pytest-mock==3.12.0
pytest-asyncio==0.21.1
pytest-timeout==2.2.0
coverage[toml]==7.3.2
black==23.11.0
flake8==6.1.0
mypy==1.7.1
isort==5.12.0
pre-commit==3.5.0
```

2. **Create pytest.ini**
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --cov=.
    --cov-report=term-missing
    --cov-report=html
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    ui: marks tests as UI tests
```

3. **Create .coveragerc**
```ini
[run]
source = .
omit = 
    */tests/*
    */venv/*
    setup.py
    */__pycache__/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
```

### Step 2: First Unit Tests (Day 3-5)

Create `tests/unit/test_security.py`:
```python
"""Test security module functionality."""
import pytest
from security import encrypt_api_key, decrypt_api_key, get_machine_id
from security_decorators import rate_limited, sanitize_inputs
from cryptography.fernet import InvalidToken


class TestSecurity:
    """Test security functions."""
    
    def test_encrypt_decrypt_api_key(self):
        """Test API key encryption and decryption."""
        original_key = "sk-test123456789"
        encrypted = encrypt_api_key(original_key)
        
        # Encrypted should be different from original
        assert encrypted != original_key
        assert isinstance(encrypted, str)
        
        # Should decrypt back to original
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original_key
    
    def test_decrypt_invalid_key(self):
        """Test decrypting invalid encrypted data."""
        with pytest.raises(InvalidToken):
            decrypt_api_key("invalid_encrypted_data")
    
    def test_machine_id_consistency(self):
        """Test machine ID is consistent."""
        id1 = get_machine_id()
        id2 = get_machine_id()
        
        assert id1 == id2
        assert len(id1) > 0


class TestSecurityDecorators:
    """Test security decorators."""
    
    def test_rate_limiting(self):
        """Test rate limiting decorator."""
        call_count = 0
        
        @rate_limited(calls=2, period=1)
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        # First two calls should succeed
        assert test_function() == "success"
        assert test_function() == "success"
        assert call_count == 2
        
        # Third call should be rate limited
        with pytest.raises(Exception, match="Rate limit exceeded"):
            test_function()
    
    def test_sanitize_inputs(self):
        """Test input sanitization decorator."""
        @sanitize_inputs
        def test_function(text):
            return text
        
        # Normal input should pass through
        assert test_function("normal text") == "normal text"
        
        # Script tags should be removed
        result = test_function("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "</script>" not in result
```

Create `tests/unit/test_validation.py`:
```python
"""Test validation functions."""
import pytest
from validation import (
    validate_api_key,
    validate_file_path,
    validate_audio_format,
    validate_model_name
)


class TestValidation:
    """Test validation functions."""
    
    @pytest.mark.parametrize("provider,key,expected", [
        ("openai", "sk-" + "a" * 48, True),
        ("openai", "invalid", False),
        ("deepgram", "a" * 32, True),
        ("deepgram", "short", False),
        ("groq", "gsk_" + "a" * 52, True),
        ("groq", "invalid", False),
    ])
    def test_validate_api_key(self, provider, key, expected):
        """Test API key validation."""
        is_valid, _ = validate_api_key(provider, key)
        assert is_valid == expected
    
    def test_validate_file_path(self, tmp_path):
        """Test file path validation."""
        # Valid file
        valid_file = tmp_path / "test.txt"
        valid_file.write_text("test")
        assert validate_file_path(str(valid_file), must_exist=True)
        
        # Non-existent file
        assert not validate_file_path("/nonexistent/file.txt", must_exist=True)
        assert validate_file_path("/nonexistent/file.txt", must_exist=False)
    
    @pytest.mark.parametrize("format,expected", [
        ("mp3", True),
        ("wav", True),
        ("m4a", True),
        ("invalid", False),
        ("exe", False),
    ])
    def test_validate_audio_format(self, format, expected):
        """Test audio format validation."""
        assert validate_audio_format(f"file.{format}") == expected
```

### Step 3: Database Tests (Day 6-7)

Create `tests/unit/test_database.py`:
```python
"""Test database functionality."""
import pytest
import tempfile
from pathlib import Path
from database import Database
from datetime import datetime


class TestDatabase:
    """Test database operations."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db = Database(db_path)
        db.create_table()
        yield db
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    def test_create_table(self, temp_db):
        """Test table creation."""
        # Table should already be created
        temp_db.connect()
        temp_db.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='recordings'"
        )
        result = temp_db.cursor.fetchone()
        temp_db.disconnect()
        
        assert result is not None
        assert result[0] == 'recordings'
    
    def test_add_recording(self, temp_db):
        """Test adding a recording."""
        rec_id = temp_db.add_recording("test_recording.mp3")
        
        assert rec_id is not None
        assert isinstance(rec_id, int)
        assert rec_id > 0
    
    def test_update_recording(self, temp_db):
        """Test updating a recording."""
        # Add recording
        rec_id = temp_db.add_recording("test.mp3")
        
        # Update with various fields
        success = temp_db.update_recording(
            rec_id,
            transcript="Test transcript",
            soap_note="Test SOAP note",
            patient_name="John Doe"
        )
        
        assert success is True
        
        # Verify update
        recording = temp_db.get_recording(rec_id)
        assert recording['transcript'] == "Test transcript"
        assert recording['soap_note'] == "Test SOAP note"
    
    def test_search_recordings(self, temp_db):
        """Test searching recordings."""
        # Add test data
        temp_db.add_recording("patient1.mp3")
        temp_db.update_recording(1, transcript="Patient has headache")
        
        temp_db.add_recording("patient2.mp3")
        temp_db.update_recording(2, transcript="Patient has fever")
        
        # Search
        results = temp_db.search_recordings("headache")
        assert len(results) == 1
        assert results[0]['id'] == 1
        
        # Search multiple results
        results = temp_db.search_recordings("Patient")
        assert len(results) == 2
    
    def test_delete_recording(self, temp_db):
        """Test deleting a recording."""
        rec_id = temp_db.add_recording("test.mp3")
        
        # Delete
        success = temp_db.delete_recording(rec_id)
        assert success is True
        
        # Verify deletion
        recording = temp_db.get_recording(rec_id)
        assert recording is None
```

### Step 4: AI Processor Tests (Day 8-9)

Create `tests/unit/test_ai_processor.py`:
```python
"""Test AI processor functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from ai_processor import AIProcessor
import openai


class TestAIProcessor:
    """Test AI processing functionality."""
    
    @pytest.fixture
    def ai_processor(self):
        """Create AI processor instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            processor = AIProcessor()
            yield processor
    
    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response."""
        return {
            "choices": [{
                "message": {"content": "Mocked AI response"}
            }]
        }
    
    def test_initialization(self, ai_processor):
        """Test AI processor initialization."""
        assert ai_processor.current_provider == "openai"
        assert hasattr(ai_processor, 'refine_text')
        assert hasattr(ai_processor, 'improve_text')
    
    @patch('openai.ChatCompletion.create')
    def test_refine_text_success(self, mock_create, ai_processor, mock_openai_response):
        """Test successful text refinement."""
        mock_create.return_value = mock_openai_response
        
        result = ai_processor.refine_text("test text.")
        
        assert result["success"] is True
        assert result["text"] == "Mocked AI response"
        assert "error" not in result
        
        # Verify API was called correctly
        mock_create.assert_called_once()
    
    def test_refine_text_empty_input(self, ai_processor):
        """Test refinement with empty input."""
        result = ai_processor.refine_text("")
        
        assert result["success"] is False
        assert "error" in result
        assert "empty" in result["error"].lower()
    
    @patch('openai.ChatCompletion.create')
    def test_api_error_handling(self, mock_create, ai_processor):
        """Test API error handling."""
        mock_create.side_effect = openai.error.APIError("API Error")
        
        result = ai_processor.refine_text("test text")
        
        assert result["success"] is False
        assert "error" in result
        assert "API Error" in result["error"]
    
    @pytest.mark.parametrize("provider", ["openai", "grok", "perplexity"])
    def test_provider_switching(self, ai_processor, provider):
        """Test switching between providers."""
        ai_processor.set_provider(provider)
        assert ai_processor.current_provider == provider
```

### Step 5: Integration Tests (Day 10-12)

Create `tests/integration/test_recording_pipeline.py`:
```python
"""Test complete recording pipeline."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from recording_manager import RecordingManager
from audio import AudioHandler
from ai_processor import AIProcessor
from database import Database
import tempfile


class TestRecordingPipeline:
    """Test full recording pipeline integration."""
    
    @pytest.fixture
    def mock_components(self):
        """Mock all components for integration testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        components = {
            'db': Database(db_path),
            'audio_handler': Mock(spec=AudioHandler),
            'ai_processor': Mock(spec=AIProcessor),
            'recording_manager': RecordingManager()
        }
        
        components['db'].create_table()
        
        yield components
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.mark.integration
    def test_complete_recording_flow(self, mock_components):
        """Test complete flow: record → transcribe → process → save."""
        # Mock audio data
        sample_rate = 44100
        duration = 5
        audio_data = np.random.rand(sample_rate * duration).astype(np.float32)
        
        # Setup mocks
        mock_components['audio_handler'].combine_audio_segments.return_value = audio_data
        mock_components['ai_processor'].transcribe.return_value = {
            "success": True,
            "text": "Patient presents with headache."
        }
        mock_components['ai_processor'].generate_soap.return_value = {
            "success": True,
            "text": "S: Headache\nO: Normal\nA: Tension headache\nP: Rest"
        }
        
        # Execute pipeline
        recording_manager = mock_components['recording_manager']
        recording_manager.audio_handler = mock_components['audio_handler']
        
        # Start recording
        recording_manager.start_recording(lambda x: None)
        assert recording_manager.is_recording is True
        
        # Stop recording
        result = recording_manager.stop_recording()
        assert result is not None
        
        # Process recording
        transcript = mock_components['ai_processor'].transcribe(audio_data)
        assert transcript["success"] is True
        
        soap = mock_components['ai_processor'].generate_soap(transcript["text"])
        assert soap["success"] is True
        
        # Save to database
        rec_id = mock_components['db'].add_recording("test.mp3")
        success = mock_components['db'].update_recording(
            rec_id,
            transcript=transcript["text"],
            soap_note=soap["text"]
        )
        assert success is True
        
        # Verify saved data
        saved = mock_components['db'].get_recording(rec_id)
        assert saved["transcript"] == "Patient presents with headache."
        assert "Headache" in saved["soap_note"]
```

### Step 6: UI Tests (Day 13-15)

Create `tests/ui/test_main_window.py`:
```python
"""Test main application window."""
import pytest
from unittest.mock import Mock, patch
import tkinter as tk
from app import MedicalDictationApp


class TestMainWindow:
    """Test main window functionality."""
    
    @pytest.fixture
    def app(self):
        """Create app instance for testing."""
        with patch('app.check_api_keys', return_value=True):
            with patch('app.load_dotenv'):
                # Create root window
                root = tk.Tk()
                root.withdraw()  # Hide window during tests
                
                # Create app
                app = MedicalDictationApp()
                yield app
                
                # Cleanup
                app.destroy()
                root.destroy()
    
    def test_window_creation(self, app):
        """Test window is created correctly."""
        assert app.winfo_exists()
        assert app.title() == "Medical Assistant"
    
    def test_workflow_tabs(self, app):
        """Test workflow tabs are created."""
        # Check workflow notebook exists
        assert hasattr(app, 'workflow_notebook')
        
        # Check tabs
        tabs = app.workflow_notebook.tabs()
        assert len(tabs) == 4
    
    def test_recording_button_state(self, app):
        """Test recording button state changes."""
        # Get record button
        record_btn = app.ui.components.get('main_record_button')
        assert record_btn is not None
        
        # Initial state
        assert record_btn['text'] == "Start Recording"
        
        # Simulate recording start
        app.ui.set_recording_state(True, False)
        assert record_btn['text'] == "Stop Recording"
```

### Step 7: GitHub Actions Setup (Day 16-17)

Create `.github/workflows/tests.yml`:
```yaml
name: Tests

on:
  push:
    branches: [ main, development ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y ffmpeg portaudio19-dev
    
    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      env:
        MEDICAL_ASSISTANT_ENV: testing
      run: |
        pytest --cov=. --cov-report=xml --cov-report=term-missing
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Execution Checklist

### Week 1: Foundation
- [ ] Create `requirements-dev.txt`
- [ ] Create `pytest.ini` and `.coveragerc`
- [ ] Set up test directory structure
- [ ] Install all testing dependencies
- [ ] Configure VS Code for testing

### Week 2: Core Unit Tests
- [ ] Write security tests
- [ ] Write validation tests
- [ ] Write database tests
- [ ] Achieve 50% coverage on core modules

### Week 3: Advanced Unit Tests
- [ ] Write AI processor tests
- [ ] Write audio handler tests
- [ ] Write STT provider tests
- [ ] Achieve 70% overall coverage

### Week 4: Integration Tests
- [ ] Write recording pipeline tests
- [ ] Write queue processing tests
- [ ] Write document generation tests
- [ ] Test error scenarios

### Week 5: UI Tests
- [ ] Set up pytest-qt
- [ ] Write main window tests
- [ ] Write workflow UI tests
- [ ] Test critical user paths

### Week 6: CI/CD & Polish
- [ ] Set up GitHub Actions
- [ ] Configure coverage reporting
- [ ] Add pre-commit hooks
- [ ] Document testing procedures
- [ ] Achieve 80%+ coverage

## Running Tests Locally

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_security.py

# Run only fast tests
pytest -m "not slow"

# Run with verbose output
pytest -v

# View coverage report
open htmlcov/index.html
```

## Success Indicators

1. **Week 1**: Testing infrastructure ready, first test passes
2. **Week 2**: 20+ unit tests, 50% coverage
3. **Week 3**: 50+ tests, 70% coverage
4. **Week 4**: Integration tests passing
5. **Week 5**: UI tests working
6. **Week 6**: CI/CD pipeline active, 80%+ coverage achieved