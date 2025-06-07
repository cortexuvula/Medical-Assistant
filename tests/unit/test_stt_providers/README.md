# STT Provider Tests

This directory contains comprehensive unit tests for all Speech-to-Text (STT) providers in the Medical Assistant application.

## Test Structure

- `test_base.py` - Tests for the base STT provider class
- `test_deepgram.py` - Tests for the Deepgram STT provider
- `test_elevenlabs.py` - Tests for the ElevenLabs STT provider
- `test_groq.py` - Tests for the Groq STT provider
- `test_whisper.py` - Tests for the local Whisper STT provider
- `test_all_providers.py` - Integration tests across all providers
- `run_tests.py` - Convenience script to run all STT provider tests

## Test Coverage

Each provider test covers:

### 1. Initialization
- With and without API keys
- With custom language settings
- Error handling during initialization

### 2. Transcription
- Successful transcription with mocked API responses
- Handling of diarization (speaker separation) where supported
- Language code extraction and formatting
- Timeout calculations based on audio file size

### 3. Error Handling
- Missing API keys
- API errors (401, 500, etc.)
- Network errors
- Invalid audio data
- Unexpected response formats
- Rate limiting
- Service unavailability

### 4. Resource Management
- Temporary file creation and cleanup
- Buffer management
- Cleanup on both success and error paths

### 5. Configuration
- Custom settings from SETTINGS
- Default fallbacks
- Provider-specific options

## Running Tests

### Run all STT provider tests:
```bash
python tests/unit/test_stt_providers/run_tests.py
```

### Run specific test file:
```bash
pytest tests/unit/test_stt_providers/test_deepgram.py -v
```

### Run tests matching a pattern:
```bash
pytest tests/unit/test_stt_providers -k "test_transcribe" -v
```

### Run with coverage:
```bash
pytest tests/unit/test_stt_providers --cov=stt_providers --cov-report=html
```

## Mocking Strategy

All external API calls are mocked to ensure:
- Tests run offline
- No API keys are required for testing
- Tests are fast and deterministic
- No costs are incurred from API usage

### Key Mocks:
- **Deepgram**: `DeepgramClient` and response objects
- **ElevenLabs**: `requests.post` for API calls
- **Groq**: `OpenAI` client (Groq uses OpenAI-compatible API)
- **Whisper**: `whisper` module import and model loading

## Adding New Tests

When adding a new STT provider:

1. Create `test_<provider_name>.py` following the existing pattern
2. Mock all external dependencies
3. Test all scenarios listed above
4. Add the provider to `test_all_providers.py`
5. Update this README

## Common Test Fixtures

From `conftest.py`:
- `mock_audio_segment` - Creates test audio data
- `mock_api_keys` - Provides test API keys
- `temp_dir` - Temporary directory for file operations

## Dependencies

Required for running tests:
- pytest
- pytest-cov (optional, for coverage)
- numpy
- pydub
- All provider dependencies (mocked)

## Notes

- Tests use consistent patterns across all providers
- Each test is independent and can run in isolation
- Temporary files are always cleaned up
- Logger output is captured and can be verified
- All tests follow the AAA pattern (Arrange, Act, Assert)