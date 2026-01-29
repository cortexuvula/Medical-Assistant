"""Shared pytest fixtures and configuration."""
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
# Don't import ttkbootstrap here as it patches ttk globally
# import ttkbootstrap as ttk

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# Add src directory to path (matches main.py behavior for internal imports)
sys.path.insert(0, str(project_root / 'src'))

# Delay import of test utilities to avoid triggering ttkbootstrap early
# These will be imported lazily in fixtures that need them
TkinterTestCase = None
create_mock_workflow_ui = None


def _lazy_import_tkinter_utils():
    """Lazily import tkinter test utilities."""
    global TkinterTestCase, create_mock_workflow_ui
    if TkinterTestCase is None:
        try:
            from tests.unit.tkinter_test_utils import TkinterTestCase as _TkinterTestCase
            from tests.unit.tkinter_test_utils import create_mock_workflow_ui as _create_mock_workflow_ui
            TkinterTestCase = _TkinterTestCase
            create_mock_workflow_ui = _create_mock_workflow_ui
        except ImportError:
            pass
    return TkinterTestCase, create_mock_workflow_ui

# Set testing environment
os.environ['MEDICAL_ASSISTANT_ENV'] = 'testing'


@pytest.fixture(scope='session')
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_api_keys():
    """Mock API keys for testing."""
    keys = {
        "OPENAI_API_KEY": "test-openai-key-123",
        "DEEPGRAM_API_KEY": "test-deepgram-key-456",
        "GROQ_API_KEY": "test-groq-key-789",
        "ELEVENLABS_API_KEY": "test-elevenlabs-key-012",
        "PERPLEXITY_API_KEY": "test-perplexity-key-345",
        "GROK_API_KEY": "test-grok-key-678"
    }
    with patch.dict(os.environ, keys):
        yield keys


@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing."""
    import numpy as np
    
    sample_rate = 44100
    duration = 2  # seconds
    frequency = 440  # A4 note
    
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * t)
    
    return (audio * 32767).astype(np.int16)


@pytest.fixture
def sample_transcript():
    """Sample medical transcript for testing."""
    return """
    Patient presents today with complaints of persistent headache for the past three days.
    The headache is described as throbbing, primarily on the right side.
    Patient denies any fever, nausea, or visual disturbances.
    Blood pressure measured at 120/80.
    Physical examination reveals no neurological deficits.
    Prescribed ibuprofen 400mg every 6 hours as needed for pain.
    Advised to return if symptoms worsen or persist beyond one week.
    """


@pytest.fixture
def sample_soap_note():
    """Sample SOAP note for testing."""
    return """
    S: Patient reports persistent headache x3 days, throbbing quality, right-sided. 
       Denies fever, nausea, visual disturbances.
    
    O: Vital signs: BP 120/80, afebrile
       Physical exam: No neurological deficits noted
       
    A: Tension-type headache, likely stress-related
    
    P: 1. Ibuprofen 400mg PO q6h PRN pain
       2. Stress reduction techniques discussed
       3. Follow up in 1 week if symptoms persist
       4. Return precautions reviewed
    """


@pytest.fixture
def mock_database(temp_dir):
    """Create a mock database for testing."""
    from database.database import Database
    
    db_path = temp_dir / "test_database.db"
    db = Database(str(db_path))
    db.create_table()
    
    yield db
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-3.5-turbo",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a mocked response from OpenAI"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }


@pytest.fixture
def mock_deepgram_response():
    """Mock Deepgram transcription response."""
    return {
        "metadata": {
            "transaction_key": "test123",
            "request_id": "test-request-123",
            "sha256": "test-sha",
            "created": "2023-01-01T00:00:00.000Z",
            "duration": 2.5,
            "channels": 1
        },
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": "This is a test transcription",
                    "confidence": 0.95,
                    "words": [{
                        "word": "This",
                        "start": 0.0,
                        "end": 0.2,
                        "confidence": 0.99
                    }]
                }]
            }]
        }
    }


@pytest.fixture(scope='session')
def tk_root():
    """Create a Tk root window for UI tests."""
    root = tk.Tk()
    root.withdraw()  # Hide the window
    yield root
    try:
        root.quit()
        root.destroy()
    except:
        pass


@pytest.fixture(autouse=True)
def cleanup_audio_handler_class_state():
    """Clean up AudioHandler class-level state before and after each test."""
    # Import here to avoid import errors if audio module isn't loaded
    try:
        from audio.audio import AudioHandler
        # Clear class-level state before test
        AudioHandler._active_streams.clear()
    except (ImportError, AttributeError):
        pass

    yield

    # Clear class-level state after test
    try:
        from audio.audio import AudioHandler
        AudioHandler._active_streams.clear()
    except (ImportError, AttributeError):
        pass


def _cleanup_ttkbootstrap_state():
    """Helper to clean up ttkbootstrap cached state."""
    # Reset ttkbootstrap Publisher subscriptions
    try:
        from ttkbootstrap.publisher import Publisher
        Publisher.clear_subscribers()
    except (ImportError, AttributeError):
        pass

    # Reset ttkbootstrap Style singleton
    try:
        import ttkbootstrap.style as ttkbs_style
        ttkbs_style.Style.instance = None
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def cleanup_ttkbootstrap_style():
    """Clean up ttkbootstrap cached state before and after each test.

    ttkbootstrap caches its Style instance and maintains widget subscriptions
    via Publisher. When a Tk root window is destroyed, these caches still
    reference the old window, causing errors when creating new widgets in
    subsequent tests.

    We clean up BEFORE each test to ensure a fresh state, and AFTER each test
    for good hygiene.
    """
    # Clean up before test to ensure fresh state
    _cleanup_ttkbootstrap_state()

    yield

    # Clean up after test
    _cleanup_ttkbootstrap_state()


@pytest.fixture
def mock_audio_handler():
    """Mock audio handler for testing."""
    handler = Mock()
    handler.sample_rate = 44100
    handler.channels = 1
    handler.is_recording = False
    handler.soap_mode = False
    handler.silence_threshold = 0.001

    return handler


@pytest.fixture
def mock_ai_processor():
    """Mock AI processor for testing."""
    processor = Mock()
    processor.current_provider = "openai"

    processor.refine_text.return_value = {
        "success": True,
        "text": "Refined text"
    }

    processor.improve_text.return_value = {
        "success": True,
        "text": "Improved text"
    }

    processor.generate_soap.return_value = {
        "success": True,
        "text": "Generated SOAP note"
    }

    return processor


# =========================================================================
# Agent System Fixtures
# =========================================================================

@pytest.fixture
def mock_ai_caller():
    """Create a mock AI caller for testing agents without making real API calls."""
    from ai.agents.ai_caller import MockAICaller
    return MockAICaller(default_response="Mock response")


@pytest.fixture
def mock_ai_caller_json():
    """Create a mock AI caller that returns JSON responses."""
    from ai.agents.ai_caller import MockAICaller
    return MockAICaller(default_response='{"key": "value", "status": "success"}')


@pytest.fixture
def sample_agent_config():
    """Create a sample AgentConfig for testing."""
    from ai.agents.models import AgentConfig
    return AgentConfig(
        name="TestAgent",
        description="Test agent for unit tests",
        system_prompt="You are a helpful test assistant.",
        model="gpt-4",
        temperature=0.5,
        max_tokens=500
    )


@pytest.fixture
def sample_agent_task():
    """Create a sample AgentTask for testing."""
    from ai.agents.models import AgentTask
    return AgentTask(
        task_description="Test task description",
        context="Test context for the task",
        input_data={"key": "value", "clinical_text": "Patient presents with headache."}
    )


@pytest.fixture
def sample_agent_task_with_soap():
    """Create a sample AgentTask with a SOAP note."""
    from ai.agents.models import AgentTask
    return AgentTask(
        task_description="Process SOAP note",
        context="Medical consultation",
        input_data={
            "soap_note": """S: Patient reports persistent headache x3 days.
O: BP 120/80, afebrile. Neuro exam normal.
A: Tension headache.
P: Ibuprofen 400mg PRN, follow up in 1 week.""",
            "clinical_text": "Patient with headache for 3 days"
        }
    )


@pytest.fixture
def sample_clinical_text():
    """Sample clinical text for data extraction testing."""
    return """
    Chief Complaint: 45-year-old male with chest pain and shortness of breath.

    Vital Signs:
    - Blood Pressure: 145/92 mmHg
    - Heart Rate: 88 bpm
    - Temperature: 98.6°F
    - Respiratory Rate: 18/min
    - O2 Saturation: 97% on room air

    Laboratory Values:
    - Hemoglobin: 14.2 g/dL (13.5-17.5)
    - WBC: 8,500/µL (4,500-11,000)
    - Troponin I: 0.02 ng/mL (<0.04)
    - BNP: 150 pg/mL (<100) [H]
    - Creatinine: 1.1 mg/dL (0.7-1.3)

    Current Medications:
    - Lisinopril 10mg PO daily
    - Metformin 500mg PO BID
    - Aspirin 81mg PO daily

    Assessment:
    1. Hypertension (I10)
    2. Type 2 Diabetes Mellitus (E11.9)
    3. Chest pain, unspecified (R07.9)

    Plan:
    - ECG and chest X-ray
    - Continue current medications
    - Follow up in 2 weeks
    """


# =========================================================================
# RAG System Fixtures
# =========================================================================

@pytest.fixture
def mock_postgresql_pool():
    """Create a mock PostgreSQL connection pool for RAG testing."""
    pool = Mock()
    conn = MagicMock()
    cursor = MagicMock()

    # Setup connection context manager
    pool.connection.return_value.__enter__ = Mock(return_value=conn)
    pool.connection.return_value.__exit__ = Mock(return_value=False)

    # Setup cursor context manager
    conn.cursor.return_value.__enter__ = Mock(return_value=cursor)
    conn.cursor.return_value.__exit__ = Mock(return_value=False)

    # Default cursor behavior
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None

    return pool, conn, cursor


@pytest.fixture
def search_quality_config():
    """Create a SearchQualityConfig for RAG testing."""
    try:
        from rag.search_config import SearchQualityConfig
        return SearchQualityConfig()
    except ImportError:
        # Return a mock if the module isn't available
        config = Mock()
        config.enable_adaptive_threshold = True
        config.enable_query_expansion = True
        config.enable_bm25 = True
        config.enable_mmr = True
        config.vector_weight = 0.5
        config.bm25_weight = 0.3
        config.graph_weight = 0.2
        config.mmr_lambda = 0.7
        config.min_threshold = 0.2
        config.max_threshold = 0.8
        config.target_result_count = 5
        return config


@pytest.fixture
def mock_embedding_manager():
    """Create a mock embedding manager for RAG testing."""
    manager = Mock()
    manager.model = "text-embedding-ada-002"
    manager.generate_embedding.return_value = [0.1] * 1536  # Standard embedding size
    manager.generate_embeddings_batch.return_value = [[0.1] * 1536 for _ in range(5)]
    return manager


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store for RAG testing."""
    from unittest.mock import Mock

    store = Mock()
    store.health_check.return_value = True
    store.get_stats.return_value = {"document_count": 100, "chunk_count": 500}
    store.search.return_value = []
    return store


@pytest.fixture
def sample_vector_search_results():
    """Create sample vector search results for testing."""
    # Using a simple dict-based approach for flexibility
    return [
        {
            "document_id": "doc1",
            "chunk_index": 0,
            "chunk_text": "Hypertension management guidelines recommend BP < 140/90.",
            "similarity_score": 0.85,
            "metadata": {"filename": "guidelines.pdf", "created_at": "2024-01-15"}
        },
        {
            "document_id": "doc2",
            "chunk_index": 1,
            "chunk_text": "Diabetes treatment with metformin as first-line therapy.",
            "similarity_score": 0.72,
            "metadata": {"filename": "diabetes.pdf", "created_at": "2024-02-20"}
        }
    ]


# =========================================================================
# Audio System Fixtures
# =========================================================================

@pytest.fixture
def mock_audio_state_manager():
    """Create a mock AudioStateManager for recording tests."""
    from unittest.mock import Mock

    state_manager = Mock()
    state_manager.get_state.return_value = None  # Will be set per test
    state_manager.is_recording.return_value = False
    state_manager.is_paused.return_value = False
    state_manager.has_audio.return_value = False
    state_manager.get_recording_metadata.return_value = {
        'recording_duration': 0.0,
        'start_time': None,
        'pause_duration': 0.0
    }
    state_manager.get_segment_stats.return_value = (0, 0, 0)
    state_manager.get_combined_audio.return_value = None

    return state_manager


@pytest.fixture
def mock_status_manager():
    """Create a mock StatusManager for recording tests."""
    status_manager = Mock()
    status_manager.info = Mock()
    status_manager.warning = Mock()
    status_manager.error = Mock()
    status_manager.update = Mock()
    return status_manager


# =========================================================================
# Document Generator Fixtures
# =========================================================================

@pytest.fixture
def mock_app_for_streaming():
    """Create a mock app object for streaming mixin tests."""
    app = Mock()
    app.after = Mock(side_effect=lambda ms, func: func())  # Execute immediately
    return app


@pytest.fixture
def mock_text_widget():
    """Create a mock text widget for streaming tests."""
    widget = Mock()
    widget.configure = Mock()
    widget.insert = Mock()
    widget.see = Mock()
    widget.delete = Mock()
    widget.get.return_value = ""
    return widget


# Pytest hooks
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "ui: marks tests as UI tests requiring display"
    )
    config.addinivalue_line(
        "markers", "requires_api_key: marks tests that require real API keys"
    )
    config.addinivalue_line(
        "markers", "network: marks tests that require network access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "ui" in str(item.fspath) or "tkinter" in str(item.fspath):
            item.add_marker(pytest.mark.ui)

        # Skip UI tests if no display is available (Linux only)
        if ("ui" in str(item.fspath) or "tkinter" in str(item.fspath)):
            if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
                item.add_marker(pytest.mark.skip(reason="No display available for UI tests"))


@pytest.fixture
def tkinter_app():
    """Create a tkinter application for testing."""
    # Use regular tk.Tk() instead of ttkbootstrap Window
    root = tk.Tk()
    root.withdraw()  # Hide window by default
    
    yield root
    
    try:
        root.quit()
        root.destroy()
    except:
        pass


@pytest.fixture
def mock_workflow_ui(tkinter_app):
    """Create a mock WorkflowUI instance for testing."""
    _, create_mock_workflow_ui_func = _lazy_import_tkinter_utils()
    if create_mock_workflow_ui_func is None:
        pytest.skip("tkinter_test_utils not available")

    return create_mock_workflow_ui_func()


@pytest.fixture
def tkinter_test_case():
    """Provide TkinterTestCase functionality as a fixture."""
    TkinterTestCaseClass, _ = _lazy_import_tkinter_utils()
    if TkinterTestCaseClass is None:
        pytest.skip("tkinter_test_utils not available")

    class TestHelper(TkinterTestCaseClass):
        def __init__(self):
            pass

    helper = TestHelper()
    yield helper

    if hasattr(helper, 'teardown_method'):
        helper.teardown_method(None)