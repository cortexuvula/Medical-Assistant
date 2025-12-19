"""Regression test fixtures and configuration.

These fixtures are specific to regression tests and supplement the shared fixtures
in tests/conftest.py.
"""
import os
import sys
import json
import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# TRANSCRIPT FIXTURES
# ============================================================================

@pytest.fixture
def short_medical_transcript():
    """Short medical transcript (~100 words) for testing."""
    return """
    Patient is a 45-year-old male presenting with chest pain for the past 2 hours.
    Pain is substernal, pressure-like, radiating to left arm.
    Associated with diaphoresis and shortness of breath.
    No prior cardiac history. Takes lisinopril for hypertension.
    Vital signs: BP 150/95, HR 88, RR 18, O2 sat 97% on room air.
    EKG shows ST elevation in leads V1-V4.
    Troponin pending. Cardiology consulted for emergent cath.
    """


@pytest.fixture
def long_medical_transcript():
    """Long medical transcript (~500 words) for testing."""
    return """
    Patient is a 62-year-old female with a complex medical history including type 2 diabetes
    mellitus, hypertension, hyperlipidemia, and chronic kidney disease stage 3, presenting
    today for follow-up of her multiple chronic conditions.

    Chief Complaint: Patient reports increased fatigue over the past month and has noticed
    some swelling in her ankles bilaterally. She denies chest pain, shortness of breath at
    rest, orthopnea, or paroxysmal nocturnal dyspnea.

    Current Medications:
    - Metformin 1000mg twice daily
    - Lisinopril 20mg daily
    - Atorvastatin 40mg at bedtime
    - Aspirin 81mg daily
    - Amlodipine 5mg daily

    Review of Systems: Positive for fatigue and bilateral ankle edema as noted above.
    Negative for chest pain, palpitations, syncope, dizziness, nausea, vomiting,
    abdominal pain, changes in bowel or bladder habits, joint pain, rash, or fever.

    Physical Examination:
    Vital Signs: Blood pressure 138/82 mmHg, heart rate 76 bpm regular, respiratory rate
    16 breaths per minute, temperature 98.4°F, oxygen saturation 98% on room air,
    weight 185 lbs (gained 4 lbs since last visit).

    General: Well-appearing, no acute distress
    HEENT: Normocephalic, atraumatic, pupils equal round reactive to light
    Cardiovascular: Regular rate and rhythm, no murmurs rubs or gallops, JVP not elevated
    Lungs: Clear to auscultation bilaterally, no wheezes rales or rhonchi
    Abdomen: Soft, non-tender, non-distended, normal bowel sounds
    Extremities: 1+ pitting edema bilateral lower extremities to mid-shin, warm and well-perfused

    Labs from today:
    - HbA1c: 7.8% (previous 7.2%)
    - Creatinine: 1.6 mg/dL (baseline 1.4)
    - eGFR: 38 mL/min/1.73m2
    - Potassium: 4.8 mEq/L
    - BNP: 450 pg/mL
    - Urinalysis: 2+ protein

    Assessment and Plan:
    1. Type 2 Diabetes Mellitus - suboptimally controlled with rising HbA1c. Will add
       empagliflozin 10mg daily which will also help with heart failure and CKD protection.
       Continue metformin. Reinforce diet and exercise counseling.

    2. Hypertension - reasonably controlled but could be better given proteinuria.
       Increase lisinopril to 40mg daily.

    3. Chronic Kidney Disease Stage 3b - worsening from stage 3a. New proteinuria concerning.
       Will refer to nephrology for co-management. Continue ACE inhibitor for renoprotection.

    4. New onset heart failure with preserved ejection fraction - likely given BNP elevation,
       lower extremity edema, and weight gain. Will start low-dose furosemide 20mg daily.
       Order echocardiogram to assess ejection fraction.

    5. Hyperlipidemia - continue current statin therapy.

    Follow up in 4 weeks to reassess. Patient educated on low sodium diet, daily weights,
    and when to call if symptoms worsen. Return precautions reviewed.
    """


@pytest.fixture
def transcript_with_medications():
    """Transcript containing a medication list for testing extraction."""
    return """
    Patient is currently on the following medications:
    1. Metformin 500mg twice daily for diabetes
    2. Lisinopril 10mg daily for blood pressure
    3. Atorvastatin 20mg at bedtime for cholesterol
    4. Aspirin 81mg daily for cardiac protection
    5. Omeprazole 20mg daily for GERD
    6. Gabapentin 300mg three times daily for neuropathy
    7. Metoprolol 25mg twice daily for heart rate control

    Patient reports good compliance with all medications.
    No adverse effects reported.
    """


@pytest.fixture
def transcript_with_conditions():
    """Transcript with multiple medical conditions for diagnosis testing."""
    return """
    Patient has history of:
    - Type 2 diabetes mellitus, diagnosed 10 years ago
    - Essential hypertension, on medication for 15 years
    - Coronary artery disease, status post CABG 2019
    - Chronic kidney disease stage 3
    - Osteoarthritis of bilateral knees
    - GERD with Barrett's esophagus
    - Depression, currently stable on SSRI

    Today presenting with worsening knee pain and elevated blood sugar.
    """


# ============================================================================
# EXPECTED OUTPUT FIXTURES
# ============================================================================

@pytest.fixture
def expected_soap_sections():
    """Expected sections that should be in a SOAP note."""
    return {
        'subjective': ['S:', 'Subjective:', 'SUBJECTIVE:'],
        'objective': ['O:', 'Objective:', 'OBJECTIVE:'],
        'assessment': ['A:', 'Assessment:', 'ASSESSMENT:'],
        'plan': ['P:', 'Plan:', 'PLAN:']
    }


@pytest.fixture
def expected_referral_elements():
    """Expected elements in a referral letter."""
    return [
        'referring',
        'patient',
        'diagnosis',
        'reason for referral',
        'history',
        'medications'
    ]


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_settings():
    """Mock settings dictionary for testing."""
    return {
        "ai_provider": "openai",
        "ai_model": "gpt-4",
        "temperature": 0.7,
        "stt_provider": "deepgram",
        "theme": "darkly",
        "auto_save": True,
        "auto_save_interval": 300,
        "deepgram": {
            "api_key": "test-key",
            "model": "nova-2-medical"
        },
        "groq": {
            "api_key": "test-key",
            "model": "whisper-large-v3-turbo"
        },
        "agent_config": {
            "synopsis": {"enabled": True, "model": "gpt-4", "temperature": 0.7},
            "diagnostic": {"enabled": True, "model": "gpt-4", "temperature": 0.5},
            "medication": {"enabled": True, "model": "gpt-4", "temperature": 0.3}
        }
    }


@pytest.fixture
def mock_ai_response():
    """Generic mock AI response for testing."""
    return "This is a mocked AI response for testing purposes."


@pytest.fixture
def mock_transcription_result():
    """Mock TranscriptionResult for STT testing."""
    from dataclasses import dataclass

    @dataclass
    class MockTranscriptionResult:
        text: str = "This is a test transcription"
        success: bool = True
        error: str = None
        confidence: float = 0.95
        duration: float = 2.5
        provider: str = "mock"

    return MockTranscriptionResult()


@pytest.fixture
def mock_agent_response():
    """Mock AgentResponse for agent testing."""
    try:
        from src.ai.agents.models import AgentResponse
        return AgentResponse(
            success=True,
            content="Mocked agent response content",
            error=None,
            metadata={"test": True}
        )
    except ImportError:
        # Fallback if models not available
        return {
            "success": True,
            "content": "Mocked agent response content",
            "error": None,
            "metadata": {"test": True}
        }


@pytest.fixture
def mock_database_record():
    """Mock database record for testing."""
    return {
        "id": 1,
        "filename": "test_recording.wav",
        "transcript": "Test transcript content",
        "soap_note": "Test SOAP note",
        "referral": None,
        "letter": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture
def temp_database(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_regression.db"

    # Create database with basic schema
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            transcript TEXT,
            soap_note TEXT,
            referral TEXT,
            letter TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def populated_database(temp_database):
    """Database with sample data for testing."""
    conn = sqlite3.connect(str(temp_database))

    # Insert sample records
    records = [
        ("recording1.wav", "Transcript 1", "SOAP 1", None, None),
        ("recording2.wav", "Transcript 2", "SOAP 2", "Referral 2", None),
        ("recording3.wav", "Transcript 3", None, None, "Letter 3"),
    ]

    conn.executemany("""
        INSERT INTO recordings (filename, transcript, soap_note, referral, letter)
        VALUES (?, ?, ?, ?, ?)
    """, records)
    conn.commit()
    conn.close()

    yield temp_database


# ============================================================================
# SETTINGS FIXTURES
# ============================================================================

@pytest.fixture
def temp_settings_file(tmp_path, mock_settings):
    """Create a temporary settings file for testing."""
    settings_path = tmp_path / "settings.json"

    with open(settings_path, 'w') as f:
        json.dump(mock_settings, f, indent=2)

    yield settings_path

    if settings_path.exists():
        settings_path.unlink()


# ============================================================================
# AUDIO FIXTURES
# ============================================================================

@pytest.fixture
def mock_audio_segment():
    """Mock AudioSegment for STT testing."""
    try:
        from pydub import AudioSegment
        import numpy as np

        # Create 2 seconds of silence
        sample_rate = 44100
        duration_ms = 2000
        silence = AudioSegment.silent(duration=duration_ms, frame_rate=sample_rate)
        return silence
    except ImportError:
        # Return mock if pydub not available
        mock = Mock()
        mock.duration_seconds = 2.0
        mock.frame_rate = 44100
        mock.channels = 1
        return mock


@pytest.fixture
def mock_audio_with_speech():
    """Mock AudioSegment with speech-like content."""
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine

        # Create a simple tone to simulate speech
        tone = Sine(440).to_audio_segment(duration=2000)
        return tone
    except ImportError:
        mock = Mock()
        mock.duration_seconds = 2.0
        mock.frame_rate = 44100
        mock.channels = 1
        return mock


# ============================================================================
# PROVIDER MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Mocked OpenAI response"
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = "Mocked Anthropic response"
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_deepgram_client():
    """Mock Deepgram client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.results.channels = [MagicMock()]
    mock_response.results.channels[0].alternatives = [MagicMock()]
    mock_response.results.channels[0].alternatives[0].transcript = "Mocked Deepgram transcription"
    mock_client.listen.rest.v.return_value.transcribe_file.return_value = mock_response
    return mock_client


# ============================================================================
# SECURITY FIXTURES
# ============================================================================

@pytest.fixture
def encryption_test_key():
    """Test API key for encryption testing."""
    return "sk-test-key-12345678901234567890"


@pytest.fixture
def mock_security_manager():
    """Mock SecurityManager for testing."""
    mock = MagicMock()
    mock.encrypt.return_value = b"encrypted_data"
    mock.decrypt.return_value = "decrypted_data"
    mock.validate_api_key.return_value = True
    mock.sanitize_input.return_value = "sanitized input"
    return mock


# ============================================================================
# MARKERS
# ============================================================================

def pytest_configure(config):
    """Add regression marker."""
    config.addinivalue_line(
        "markers", "regression: marks tests as regression tests"
    )
