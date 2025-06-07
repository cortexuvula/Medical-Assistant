# Medical Assistant Testing Guide

## Overview

The Medical Assistant application has a comprehensive test suite with over 80% code coverage on critical modules. This guide explains the testing infrastructure, how to run tests, and how to add new tests.

## Test Coverage Status

As of the latest implementation:
- **Overall Coverage**: 80.68% (core modules)
- **Key Module Coverage**:
  - `database.py`: 96.17%
  - `ai_processor.py`: 80.13%
  - `audio.py`: 81.12%
  - `recording_manager.py`: 90.76%
  - `security.py`: 71.14%
  - `validation.py`: 83.25%
  - STT Providers: 85-98% average

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_setup.py            # Basic setup verification
├── unit/                    # Unit tests
│   ├── test_ai_processor.py
│   ├── test_audio.py
│   ├── test_audio_extended.py
│   ├── test_database.py
│   ├── test_recording_manager.py
│   ├── test_security.py
│   ├── test_validation.py
│   └── test_stt_providers/  # STT provider tests
│       ├── test_base.py
│       ├── test_deepgram.py
│       ├── test_elevenlabs.py
│       ├── test_groq.py
│       ├── test_whisper.py
│       └── test_all_providers.py
└── integration/             # Integration tests
    └── test_recording_pipeline.py
```

## Running Tests

### Prerequisites

Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

### Running All Tests

```bash
# Run all tests
python -m pytest

# Run with coverage report
python -m pytest --cov=. --cov-report=term-missing

# Run with HTML coverage report
python -m pytest --cov=. --cov-report=html
```

### Running Specific Tests

```bash
# Run unit tests only
python -m pytest tests/unit/

# Run integration tests only
python -m pytest tests/integration/

# Run a specific test file
python -m pytest tests/unit/test_database.py

# Run a specific test method
python -m pytest tests/unit/test_database.py::TestDatabase::test_add_recording_minimal

# Run tests matching a pattern
python -m pytest -k "test_transcribe"
```

### Using the Test Runner Script

A convenience script is provided for common testing scenarios:

```bash
# Run all tests with coverage
python run_tests.py --cov

# Run only unit tests
python run_tests.py --unit

# Run tests with HTML coverage report
python run_tests.py --cov-html

# Run tests in parallel
python run_tests.py -n auto

# Run previously failed tests
python run_tests.py --failed
```

## Test Markers

Tests are marked with categories for selective execution:

- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.ui` - UI tests requiring Qt

Run tests excluding certain markers:
```bash
pytest -m "not slow"
pytest -m "not ui"
```

## Writing Tests

### Test Structure Example

```python
import pytest
from unittest.mock import Mock, patch

class TestMyModule:
    """Test cases for my_module."""
    
    @pytest.fixture
    def my_fixture(self):
        """Create a test fixture."""
        return MyClass()
    
    def test_basic_functionality(self, my_fixture):
        """Test basic functionality."""
        result = my_fixture.do_something()
        assert result == expected_value
    
    @patch('my_module.external_api')
    def test_with_mock(self, mock_api, my_fixture):
        """Test with mocked external dependency."""
        mock_api.return_value = {"status": "success"}
        result = my_fixture.call_api()
        assert result["status"] == "success"
        mock_api.assert_called_once()
```

### Common Test Patterns

1. **Testing Error Handling**:
```python
def test_error_handling(self):
    with pytest.raises(ValueError, match="Invalid input"):
        function_that_should_raise("bad input")
```

2. **Testing File Operations**:
```python
def test_file_operations(self, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    result = read_file(str(test_file))
    assert result == "content"
```

3. **Testing Async Code**:
```python
@pytest.mark.asyncio
async def test_async_function(self):
    result = await async_function()
    assert result == expected
```

## Coverage Guidelines

### Target Coverage
- Critical business logic: 90%+
- API integrations: 80%+
- Utility functions: 70%+
- UI code: 50%+ (where feasible)

### Checking Coverage

```bash
# Generate coverage report
pytest --cov=module_name --cov-report=term-missing

# View HTML coverage report
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

### Improving Coverage

1. Identify uncovered lines:
   - Look for red lines in HTML coverage report
   - Check "Missing" column in terminal report

2. Write tests for:
   - Error paths
   - Edge cases
   - Different input types
   - Configuration variations

## CI/CD Integration

Tests run automatically on:
- Push to main/development branches
- Pull requests
- Manual workflow dispatch

The CI pipeline:
1. Runs on multiple OS (Ubuntu, Windows, macOS)
2. Tests against Python 3.8-3.11
3. Runs linting checks
4. Generates coverage reports
5. Performs security scans

## Pre-commit Hooks

Enable pre-commit hooks for automatic code quality checks:

```bash
pre-commit install
```

This will run:
- Black (code formatting)
- isort (import sorting)
- Flake8 (linting)
- MyPy (type checking)
- Basic pytest smoke tests

## Debugging Failed Tests

### Verbose Output
```bash
pytest -vv tests/unit/test_failing.py
```

### Show print statements
```bash
pytest -s tests/unit/test_failing.py
```

### Drop into debugger on failure
```bash
pytest --pdb tests/unit/test_failing.py
```

### Run specific test with debugging
```bash
python -m pdb -m pytest tests/unit/test_specific.py::test_method
```

## Mock Best Practices

1. **Mock at boundaries**: Mock external services, not internal methods
2. **Use specific assertions**: Verify mock calls with exact arguments
3. **Reset mocks**: Use `mock.reset_mock()` between test cases
4. **Patch locations**: Patch where the object is used, not where it's defined

Example:
```python
# Good
@patch('module_using_api.requests.post')
def test_api_call(self, mock_post):
    mock_post.return_value.json.return_value = {"status": "ok"}
    
# Bad - patching at definition
@patch('requests.post')
```

## Troubleshooting

### Common Issues

1. **Import Errors**:
   - Ensure test file is in correct location
   - Check PYTHONPATH includes project root
   - Verify `__init__.py` files exist

2. **Fixture Not Found**:
   - Check fixture is in conftest.py or same file
   - Verify fixture scope matches usage

3. **Mock Not Working**:
   - Verify patch target path
   - Check import style (from X import Y vs import X)
   - Use `patch.object()` for instance methods

4. **Async Test Issues**:
   - Add `@pytest.mark.asyncio` decorator
   - Ensure pytest-asyncio is installed

## Contributing Tests

When adding new features:
1. Write tests first (TDD approach)
2. Ensure tests cover happy path and error cases
3. Mock external dependencies
4. Add appropriate test markers
5. Verify coverage meets targets
6. Update this documentation if needed

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Python Mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://testdriven.io/blog/testing-best-practices/)