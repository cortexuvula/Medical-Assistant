# Testing Quick Start Guide

This guide provides quick reference commands for using the Medical Assistant testing infrastructure.

## Quick Start

### 1. Install Test Dependencies
```bash
pip install -r requirements-dev.txt
```

### 2. Run All Tests
```bash
# Simple run
python -m pytest

# With coverage report
python -m pytest --cov=. --cov-report=term-missing

# Using the convenience script
python run_tests.py --cov
```

## Common Testing Commands

### Run Specific Test Categories
```bash
# Unit tests only
python -m pytest tests/unit/

# Integration tests only
python -m pytest tests/integration/

# STT provider tests
python -m pytest tests/unit/test_stt_providers/
```

### Run Individual Test Files
```bash
# Test database functionality
python -m pytest tests/unit/test_database.py

# Test audio handling
python -m pytest tests/unit/test_audio.py

# Test AI processor
python -m pytest tests/unit/test_ai_processor.py
```

### Run Tests with Different Options
```bash
# Show print statements during tests
python -m pytest -s

# Very verbose output
python -m pytest -vv

# Run tests matching a pattern
python -m pytest -k "transcribe"

# Run failed tests from last run
python -m pytest --lf

# Run tests in parallel (faster)
python -m pytest -n auto
```

## Using the Test Runner Script

The `run_tests.py` script provides convenient shortcuts:

```bash
# Run with coverage and open HTML report
python run_tests.py --cov-html

# Run only unit tests
python run_tests.py --unit

# Run only integration tests
python run_tests.py --integration

# Run with verbose output
python run_tests.py -vv

# Run specific test file
python run_tests.py tests/unit/test_database.py
```

## Viewing Coverage Reports

### Terminal Report
```bash
python -m pytest --cov=. --cov-report=term-missing
```

### HTML Report (Interactive)
```bash
# Generate and open HTML report
python -m pytest --cov=. --cov-report=html
# Then open htmlcov/index.html in your browser

# Or use the script
python run_tests.py --cov-html
# This automatically opens the report in your browser
```

## Pre-commit Hooks Setup

To enable automatic code quality checks before commits:

```bash
# Install pre-commit hooks (one-time setup)
pre-commit install

# Now when you commit, it will automatically:
# - Format code with Black
# - Sort imports with isort
# - Check for linting issues
# - Run basic tests
```

## Debugging Failed Tests

### If a test fails:
```bash
# Show full error details
python -m pytest tests/unit/test_audio.py::TestAudioHandler::test_save_audio -vv

# Drop into debugger on failure
python -m pytest --pdb tests/unit/test_failing.py

# Show local variables in traceback
python -m pytest -l
```

## Quick Test During Development

### Test a specific function you're working on:
```bash
# Test just one method
python -m pytest tests/unit/test_database.py::TestDatabase::test_add_recording_minimal

# Test with pattern matching
python -m pytest -k "add_recording"
```

### Skip slow tests during development:
```bash
python -m pytest -m "not slow"
```

## Checking What's Covered

### See which lines need tests:
```bash
# For a specific module
python -m pytest tests/unit/test_audio.py --cov=audio --cov-report=term-missing

# Check coverage for multiple modules
python -m pytest --cov=database --cov=ai_processor --cov-report=term-missing
```

## Example Test Run Output

Here's what you'll see:
```bash
$ python run_tests.py --cov

Running: python -m pytest tests/ --cov=. --cov-report=term-missing
--------------------------------------------------
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.3, pluggy-1.6.0
collected 275 items

tests/test_setup.py .......                                              [  2%]
tests/integration/test_recording_pipeline.py .......                     [  5%]
tests/unit/test_ai_processor.py .....................                    [ 13%]
tests/unit/test_audio.py ....................                            [ 20%]
...

---------- coverage: platform linux, python 3.12.3-final-0 -----------
Name                          Stmts   Miss Branch BrPart   Cover   Missing
--------------------------------------------------------------------------
ai_processor.py                 117     19     34     11  80.13%   98, 115-117...
audio.py                        531     88    200     30  81.12%   195->206...
database.py                     155      3     28      4  96.17%   21->exit...
...
TOTAL                          2035    323    755    126  80.68%

======================= 275 passed in 35.90s ========================
```

## Most Useful Commands for Daily Development

```bash
# 1. Quick test while coding
python -m pytest tests/unit/test_<module>.py -v

# 2. Check if you broke anything
python run_tests.py

# 3. Full test before committing
python run_tests.py --cov

# 4. Debug a failing test
python -m pytest path/to/test.py::test_name -vv --pdb
```

## Test File Locations

| Module | Test File |
|--------|-----------|
| `database.py` | `tests/unit/test_database.py` |
| `ai_processor.py` | `tests/unit/test_ai_processor.py` |
| `audio.py` | `tests/unit/test_audio.py`, `test_audio_extended.py` |
| `recording_manager.py` | `tests/unit/test_recording_manager.py` |
| `security.py` | `tests/unit/test_security.py` |
| `validation.py` | `tests/unit/test_validation.py` |
| STT Providers | `tests/unit/test_stt_providers/` |
| UI Components | `tests/unit/test_ui_basic.py`, `test_ui_medical_assistant.py` |
| Integration Tests | `tests/integration/test_recording_pipeline.py` |

## Tips for Writing Tests

### Quick Test Template
```python
import pytest
from unittest.mock import Mock, patch

def test_my_function():
    # Arrange
    input_data = "test"
    expected = "result"
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result == expected

@patch('module.external_api')
def test_with_mock(mock_api):
    mock_api.return_value = {"status": "ok"}
    result = function_using_api()
    assert result["status"] == "ok"
    mock_api.assert_called_once()
```

### Common Assertions
```python
# Basic assertions
assert value == expected
assert value is None
assert value is not None
assert len(items) == 3
assert "substring" in text
assert value > 0

# Exception testing
with pytest.raises(ValueError):
    function_that_should_fail()

# Mock assertions
mock.assert_called_once()
mock.assert_called_with(arg1, arg2)
mock.assert_not_called()
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Import errors | Make sure you're in the project root directory |
| Fixture not found | Check if fixture is in `conftest.py` or the test file |
| Mock not working | Verify you're patching where the object is used, not defined |
| Tests hanging | Use `pytest --timeout=10` to add timeout |
| Can't find tests | Ensure test files start with `test_` and functions too |

## Coverage Goals

- **Critical modules**: 80%+ coverage ✅
- **Database operations**: 96% ✅ 
- **AI/Audio processing**: 80%+ ✅
- **Security/Validation**: 70%+ ✅
- **Overall**: 80%+ ✅
- **Total Tests**: 352 (327 unit + 25 UI)

## UI Testing

### Running UI Tests
```bash
# Install UI dependencies
pip install PyQt5 pytest-qt

# Run UI tests
pytest tests/unit/test_ui_*.py -v

# Run headless (Linux)
xvfb-run -a pytest tests/unit/test_ui_*.py

# Use the UI test runner
python tests/run_ui_tests.py
```

Note: The app uses tkinter, but the PyQt5 tests demonstrate UI testing patterns.

The testing setup is designed to be fast and easy to use during development while providing comprehensive coverage reporting when needed!