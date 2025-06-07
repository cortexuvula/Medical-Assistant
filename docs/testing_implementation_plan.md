# Testing & Quality Assurance Implementation Plan

## Overview
This document outlines a comprehensive plan to implement testing and quality assurance for the Medical Assistant application, targeting 80%+ code coverage with automated CI/CD pipelines.

## Phase 1: Testing Infrastructure Setup (Week 1)

### 1.1 Install Testing Dependencies
```bash
# Add to requirements-dev.txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-qt>=4.2.0
pytest-mock>=3.11.1
pytest-asyncio>=0.21.1
pytest-timeout>=2.1.0
pytest-xdist>=3.3.1  # For parallel testing
coverage>=7.3.0
tox>=4.6.4
black>=23.7.0
flake8>=6.1.0
mypy>=1.5.0
isort>=5.12.0
pre-commit>=3.3.3
```

### 1.2 Project Structure for Tests
```
Medical-Assistant/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── unit/                    # Unit tests
│   │   ├── __init__.py
│   │   ├── test_ai_processor.py
│   │   ├── test_audio.py
│   │   ├── test_database.py
│   │   ├── test_recording_manager.py
│   │   ├── test_security.py
│   │   └── test_stt_providers/
│   │       ├── __init__.py
│   │       ├── test_base.py
│   │       ├── test_deepgram.py
│   │       └── test_groq.py
│   ├── integration/             # Integration tests
│   │   ├── __init__.py
│   │   ├── test_recording_pipeline.py
│   │   ├── test_processing_queue.py
│   │   └── test_document_generation.py
│   ├── ui/                      # UI tests
│   │   ├── __init__.py
│   │   ├── test_main_window.py
│   │   ├── test_workflow_ui.py
│   │   ├── test_recordings_tab.py
│   │   └── test_chat_interface.py
│   └── fixtures/                # Test data
│       ├── audio_samples/
│       ├── test_configs/
│       └── mock_responses/
├── .coveragerc                  # Coverage configuration
├── pytest.ini                   # Pytest configuration
├── tox.ini                      # Tox configuration
└── .pre-commit-config.yaml      # Pre-commit hooks
```

### 1.3 Configuration Files

**pytest.ini**
```ini
[tool:pytest]
minversion = 7.0
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --tb=short
    --cov=.
    --cov-report=html
    --cov-report=term-missing
    --cov-report=xml
    -v
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    ui: marks tests as UI tests
    requires_api_key: marks tests that require API keys
```

**.coveragerc**
```ini
[run]
source = .
omit = 
    */tests/*
    */venv/*
    */migrations/*
    setup.py
    main.py
    */__pycache__/*
    */site-packages/*

[report]
precision = 2
show_missing = True
skip_covered = False

[html]
directory = htmlcov
```

## Phase 2: Unit Tests Implementation (Week 2-3)

### 2.1 Core Components Testing

**test_ai_processor.py**
```python
import pytest
from unittest.mock import Mock, patch
from ai_processor import AIProcessor

class TestAIProcessor:
    @pytest.fixture
    def ai_processor(self):
        return AIProcessor()
    
    @pytest.fixture
    def mock_openai_response(self):
        return {
            "choices": [{
                "message": {"content": "Refined text"}
            }]
        }
    
    def test_refine_text_success(self, ai_processor, mock_openai_response):
        with patch('openai.ChatCompletion.create', return_value=mock_openai_response):
            result = ai_processor.refine_text("test text")
            assert result["success"] is True
            assert result["text"] == "Refined text"
    
    def test_refine_text_empty_input(self, ai_processor):
        result = ai_processor.refine_text("")
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.parametrize("provider", ["openai", "grok", "perplexity"])
    def test_provider_switching(self, ai_processor, provider):
        ai_processor.set_provider(provider)
        assert ai_processor.current_provider == provider
```

**test_database.py**
```python
import pytest
import tempfile
from database import Database

class TestDatabase:
    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db') as f:
            db = Database(f.name)
            db.create_table()
            yield db
    
    def test_add_recording(self, temp_db):
        rec_id = temp_db.add_recording("test.mp3")
        assert rec_id is not None
        assert isinstance(rec_id, int)
    
    def test_update_recording(self, temp_db):
        rec_id = temp_db.add_recording("test.mp3")
        success = temp_db.update_recording(
            rec_id, 
            transcript="Test transcript"
        )
        assert success is True
        
        recording = temp_db.get_recording(rec_id)
        assert recording["transcript"] == "Test transcript"
    
    def test_search_recordings(self, temp_db):
        # Add test recordings
        temp_db.add_recording("patient1.mp3")
        temp_db.update_recording(1, transcript="Patient has fever")
        
        results = temp_db.search_recordings("fever")
        assert len(results) == 1
```

### 2.2 Security Testing

**test_security.py**
```python
import pytest
from security import encrypt_api_key, decrypt_api_key, sanitize_input

class TestSecurity:
    def test_api_key_encryption_decryption(self):
        original = "sk-test123456789"
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)
        
        assert encrypted != original
        assert decrypted == original
    
    @pytest.mark.parametrize("malicious_input,expected", [
        ("normal text", "normal text"),
        ("<script>alert('xss')</script>", "alert('xss')"),
        ("'; DROP TABLE recordings;--", "'; DROP TABLE recordings;--"),
    ])
    def test_input_sanitization(self, malicious_input, expected):
        sanitized = sanitize_input(malicious_input)
        assert "<script>" not in sanitized
        assert sanitized == expected
```

## Phase 3: Integration Tests (Week 3-4)

### 3.1 Recording Pipeline Test

**test_recording_pipeline.py**
```python
import pytest
import asyncio
from unittest.mock import Mock, patch
import numpy as np

class TestRecordingPipeline:
    @pytest.fixture
    def mock_audio_data(self):
        # Generate mock audio data
        sample_rate = 44100
        duration = 5  # seconds
        samples = np.random.rand(sample_rate * duration)
        return samples
    
    @pytest.mark.integration
    async def test_full_recording_pipeline(self, mock_audio_data):
        """Test recording → transcription → processing → storage"""
        with patch('recording_manager.RecordingManager.get_audio') as mock_audio:
            mock_audio.return_value = mock_audio_data
            
            # Start recording
            recording_manager = RecordingManager()
            recording_manager.start_recording()
            
            # Simulate recording
            await asyncio.sleep(1)
            
            # Stop and process
            result = recording_manager.stop_recording()
            
            assert result is not None
            assert 'audio' in result
            assert 'duration' in result
    
    @pytest.mark.integration
    def test_queue_processing(self):
        """Test background queue processing"""
        from processing_queue import ProcessingQueue
        
        queue = ProcessingQueue()
        
        # Add test task
        task_data = {
            'recording_id': 1,
            'audio_data': b'mock_audio',
            'context': 'Test context'
        }
        
        task_id = queue.add_recording(task_data)
        assert task_id is not None
        
        # Wait for processing
        queue.process_next()
        
        # Check status
        stats = queue.get_stats()
        assert stats['processed'] >= 1
```

### 3.2 Document Generation Tests

**test_document_generation.py**
```python
import pytest
from document_generators import DocumentGenerators

class TestDocumentGeneration:
    @pytest.fixture
    def sample_transcript(self):
        return """
        Patient presents with headache for 3 days.
        No fever, no nausea. Blood pressure 120/80.
        Prescribed ibuprofen 400mg.
        """
    
    @pytest.mark.integration
    def test_soap_note_generation(self, sample_transcript):
        generator = DocumentGenerators(None)  # Mock parent
        
        with patch('ai_processor.AIProcessor.generate_soap') as mock_soap:
            mock_soap.return_value = {
                "success": True,
                "text": "S: Headache x3 days\nO: BP 120/80\nA: Tension headache\nP: Ibuprofen 400mg"
            }
            
            result = generator.create_soap_note_from_transcript(sample_transcript)
            assert result is not None
            assert "S:" in result
            assert "O:" in result
            assert "A:" in result
            assert "P:" in result
```

## Phase 4: UI Testing (Week 4-5)

### 4.1 Main Window Tests

**test_main_window.py**
```python
import pytest
from pytestqt.qtbot import QtBot
from app import MedicalDictationApp

class TestMainWindow:
    @pytest.fixture
    def app(self, qtbot):
        app = MedicalDictationApp()
        qtbot.addWidget(app)
        return app
    
    def test_window_initialization(self, app):
        assert app.title() == "Medical Assistant"
        assert app.winfo_width() >= 800
        assert app.winfo_height() >= 600
    
    def test_workflow_tabs_exist(self, app):
        # Check all workflow tabs exist
        tabs = app.workflow_notebook.tabs()
        assert len(tabs) == 4
        
        tab_texts = [app.workflow_notebook.tab(tab, "text") for tab in tabs]
        assert "Record" in tab_texts
        assert "Process" in tab_texts
        assert "Generate" in tab_texts
        assert "Recordings" in tab_texts
    
    @pytest.mark.ui
    def test_recording_button_click(self, app, qtbot):
        # Find record button
        record_btn = app.ui.components['main_record_button']
        
        # Initial state
        assert record_btn['text'] == "Start Recording"
        
        # Click button
        qtbot.mouseClick(record_btn, Qt.LeftButton)
        
        # Check state changed
        assert record_btn['text'] == "Stop Recording"
```

### 4.2 Workflow UI Tests

**test_workflow_ui.py**
```python
import pytest
from workflow_ui import WorkflowUI

class TestWorkflowUI:
    @pytest.fixture
    def workflow_ui(self, qtbot):
        parent = Mock()
        ui = WorkflowUI(parent)
        return ui
    
    def test_recording_state_changes(self, workflow_ui):
        # Test recording state
        workflow_ui.set_recording_state(True, False)
        
        record_btn = workflow_ui.components['main_record_button']
        assert record_btn['text'] == "Stop Recording"
        
        # Test paused state
        workflow_ui.set_recording_state(True, True)
        pause_btn = workflow_ui.components['pause_button']
        assert pause_btn['text'] == "Resume"
    
    def test_timer_updates(self, workflow_ui):
        workflow_ui.start_timer()
        
        # Wait and check timer
        import time
        time.sleep(2)
        
        timer_text = workflow_ui.components['timer_label']['text']
        assert timer_text != "00:00"
```

## Phase 5: CI/CD Pipeline (Week 5-6)

### 5.1 GitHub Actions Workflow

**.github/workflows/test.yml**
```yaml
name: Tests

on:
  push:
    branches: [ main, development ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.8', '3.9', '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install system dependencies (Ubuntu)
      if: runner.os == 'Linux'
      run: |
        sudo apt-get update
        sudo apt-get install -y ffmpeg portaudio19-dev
    
    - name: Install system dependencies (macOS)
      if: runner.os == 'macOS'
      run: |
        brew install ffmpeg portaudio
    
    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run linting
      run: |
        black --check .
        flake8 .
        mypy . --ignore-missing-imports
    
    - name: Run tests with coverage
      env:
        MEDICAL_ASSISTANT_ENV: testing
      run: |
        pytest --cov=. --cov-report=xml --cov-report=term
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

  build:
    needs: test
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller
    
    - name: Build executable
      run: |
        pyinstaller medical_assistant.spec
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: medical-assistant-${{ matrix.os }}
        path: dist/
```

### 5.2 Pre-commit Configuration

**.pre-commit-config.yaml**
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-merge-conflict
  
  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.10
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: ["--max-line-length=88", "--extend-ignore=E203,W503"]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## Phase 6: Testing Best Practices

### 6.1 Test Data Management
```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def test_data_dir():
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_audio_file(test_data_dir):
    return test_data_dir / "audio_samples" / "sample_recording.mp3"

@pytest.fixture
def mock_api_keys():
    return {
        "OPENAI_API_KEY": "test-key-123",
        "DEEPGRAM_API_KEY": "test-key-456",
        "GROQ_API_KEY": "test-key-789"
    }
```

### 6.2 Mocking External Services
```python
# Mock AI providers
@pytest.fixture
def mock_openai(monkeypatch):
    def mock_create(*args, **kwargs):
        return {
            "choices": [{
                "message": {"content": "Mocked response"}
            }]
        }
    monkeypatch.setattr("openai.ChatCompletion.create", mock_create)

# Mock STT providers
@pytest.fixture
def mock_deepgram(monkeypatch):
    def mock_transcribe(*args, **kwargs):
        return {
            "results": {
                "channels": [{
                    "alternatives": [{
                        "transcript": "Mocked transcription"
                    }]
                }]
            }
        }
    monkeypatch.setattr("deepgram.Deepgram.transcription.sync", mock_transcribe)
```

## Implementation Timeline

### Week 1: Infrastructure Setup
- [ ] Create test directory structure
- [ ] Install testing dependencies
- [ ] Configure pytest, coverage, and linting tools
- [ ] Set up pre-commit hooks

### Week 2-3: Unit Tests
- [ ] Write unit tests for core components (80% coverage target)
- [ ] Mock external dependencies
- [ ] Create test fixtures and utilities

### Week 3-4: Integration Tests
- [ ] Test recording pipeline end-to-end
- [ ] Test queue processing system
- [ ] Test document generation workflows

### Week 4-5: UI Tests
- [ ] Set up pytest-qt
- [ ] Test main window functionality
- [ ] Test workflow interactions
- [ ] Test critical user paths

### Week 5-6: CI/CD Pipeline
- [ ] Configure GitHub Actions
- [ ] Set up multi-platform testing
- [ ] Configure code coverage reporting
- [ ] Set up automated builds

## Success Metrics

1. **Code Coverage**: Achieve and maintain 80%+ coverage
2. **Test Execution Time**: Full test suite runs in < 5 minutes
3. **CI/CD Pipeline**: All tests pass on all platforms
4. **Code Quality**: Zero linting errors, type checking passes
5. **Test Reliability**: < 1% flaky tests

## Maintenance Plan

1. **Daily**: Run tests locally before commits
2. **Per PR**: All tests must pass in CI
3. **Weekly**: Review coverage reports, add tests for gaps
4. **Monthly**: Update dependencies, review test performance
5. **Quarterly**: Refactor tests, update testing strategies

## Resources Needed

1. **Testing Environment**: Separate test database, mock API keys
2. **CI/CD Resources**: GitHub Actions runners
3. **Monitoring**: Codecov or similar for coverage tracking
4. **Documentation**: Testing guidelines and best practices