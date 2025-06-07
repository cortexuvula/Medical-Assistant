# UI Testing Setup Guide

This guide walks you through setting up UI tests for the Medical Assistant application using pytest-qt.

## Prerequisites

### 1. Install Required Packages

```bash
# Install PyQt5 (if not already installed)
pip install PyQt5

# Install pytest-qt
pip install pytest-qt

# For headless testing on Linux
sudo apt-get install xvfb  # Ubuntu/Debian
# or
sudo yum install xorg-x11-server-Xvfb  # RHEL/CentOS
```

### 2. Verify Installation

```python
# Test if PyQt5 is working
python -c "from PyQt5.QtWidgets import QApplication; print('PyQt5 OK')"

# Test if pytest-qt is working
python -c "import pytest_qt; print('pytest-qt OK')"
```

## Running UI Tests

### Method 1: Using the UI Test Runner

```bash
# Run all UI tests
python tests/run_ui_tests.py

# Run with coverage
python tests/run_ui_tests.py --cov=app --cov-report=html

# Run specific test
python tests/run_ui_tests.py tests/unit/test_ui_basic.py
```

### Method 2: Using pytest directly

```bash
# Run all UI tests
pytest -m ui

# Run UI tests with verbose output
pytest -m ui -v

# Run specific UI test file
pytest tests/unit/test_ui_basic.py

# Exclude UI tests from regular test run
pytest -m "not ui"
```

### Method 3: Headless Testing (Linux)

```bash
# Using Xvfb directly
xvfb-run -a pytest tests/unit/test_ui_*.py

# Using the test runner (handles Xvfb automatically)
python tests/run_ui_tests.py
```

## Writing UI Tests

### Basic Structure

```python
import pytest
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt

@pytest.mark.ui
class TestMyUI:
    def test_button_click(self, qtbot):
        # Create widget
        button = QPushButton("Click me")
        qtbot.addWidget(button)  # Important: register widget
        
        # Test interaction
        qtbot.mouseClick(button, Qt.LeftButton)
        
        # Assert results
        assert button.isEnabled()
```

### Common qtbot Methods

| Method | Description |
|--------|-------------|
| `qtbot.addWidget(widget)` | Register widget for cleanup |
| `qtbot.mouseClick(widget, button)` | Simulate mouse click |
| `qtbot.keyClick(widget, key, modifier)` | Simulate key press |
| `qtbot.keyClicks(widget, text)` | Type text |
| `qtbot.wait(ms)` | Wait for milliseconds |
| `qtbot.waitSignal(signal, timeout)` | Wait for signal emission |
| `qtbot.waitUntil(callable, timeout)` | Wait for condition |

### Testing Patterns

#### 1. Testing Widget States
```python
def test_widget_states(self, qtbot):
    record_btn = QPushButton("Record")
    qtbot.addWidget(record_btn)
    
    # Initial state
    assert record_btn.isEnabled()
    assert record_btn.text() == "Record"
    
    # Change state
    record_btn.setEnabled(False)
    record_btn.setText("Recording...")
    
    # Verify change
    assert not record_btn.isEnabled()
    assert record_btn.text() == "Recording..."
```

#### 2. Testing Signals and Slots
```python
def test_signal_slot(self, qtbot):
    button = QPushButton("Test")
    qtbot.addWidget(button)
    
    # Track signal
    with qtbot.waitSignal(button.clicked, timeout=1000):
        button.click()
    
    # Signal was emitted within timeout
```

#### 3. Testing Async Operations
```python
def test_async_operation(self, qtbot):
    def check_condition():
        return some_async_result.is_ready()
    
    # Wait up to 5 seconds for condition
    qtbot.waitUntil(check_condition, timeout=5000)
    
    assert some_async_result.value == expected_value
```

#### 4. Testing Dialogs
```python
def test_dialog(self, qtbot, monkeypatch):
    # Mock dialog response
    monkeypatch.setattr(
        QMessageBox, 'question',
        lambda *args: QMessageBox.Yes
    )
    
    # Code that shows dialog will get mocked response
    result = show_confirmation_dialog()
    assert result == QMessageBox.Yes
```

## Troubleshooting

### Common Issues

#### 1. "Cannot connect to X server"
**Solution**: Use virtual display
```bash
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &
pytest tests/unit/test_ui_*.py
```

#### 2. "No Qt platform plugin could be initialized"
**Solution**: Install platform dependencies
```bash
# Ubuntu/Debian
sudo apt-get install libxcb-xinerama0 libxcb-cursor0

# Set platform
export QT_QPA_PLATFORM=offscreen  # For headless
```

#### 3. Tests hang or timeout
**Solution**: Always use timeouts
```python
with qtbot.waitSignal(signal, timeout=1000):  # 1 second timeout
    # trigger signal
```

#### 4. Widget not found
**Solution**: Ensure widget is registered
```python
widget = MyWidget()
qtbot.addWidget(widget)  # Don't forget this!
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Install Qt dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y xvfb libxcb-xinerama0
    
- name: Run UI tests
  run: |
    export DISPLAY=:99
    xvfb-run -a pytest -m ui
```

### Local Docker Testing
```dockerfile
FROM python:3.10
RUN apt-get update && apt-get install -y \
    xvfb \
    libxcb-xinerama0 \
    libgl1-mesa-glx
    
# Run tests
CMD ["xvfb-run", "-a", "pytest", "-m", "ui"]
```

## Best Practices

1. **Always use qtbot**: Register all widgets with `qtbot.addWidget()`
2. **Set timeouts**: Use timeouts for all wait operations
3. **Mock external dependencies**: Don't make real API calls in UI tests
4. **Test user workflows**: Focus on user interactions, not implementation
5. **Keep tests fast**: UI tests are slower, so optimize where possible
6. **Use markers**: Mark UI tests with `@pytest.mark.ui`
7. **Handle cleanup**: Ensure widgets are properly cleaned up

## Example: Testing Medical Assistant Workflow

```python
@pytest.mark.ui
def test_recording_workflow(self, qtbot, mock_audio):
    # 1. Start recording
    record_btn = window.findChild(QPushButton, "recordButton")
    qtbot.mouseClick(record_btn, Qt.LeftButton)
    
    # 2. Verify recording started
    assert mock_audio.start_recording.called
    assert record_btn.text() == "Recording..."
    
    # 3. Wait a bit
    qtbot.wait(1000)
    
    # 4. Stop recording
    stop_btn = window.findChild(QPushButton, "stopButton")
    qtbot.mouseClick(stop_btn, Qt.LeftButton)
    
    # 5. Verify transcript appears
    transcript_area = window.findChild(QTextEdit, "transcriptEdit")
    qtbot.waitUntil(
        lambda: transcript_area.toPlainText() != "",
        timeout=5000
    )
    
    # 6. Generate SOAP note
    soap_btn = window.findChild(QPushButton, "generateSOAPButton")
    qtbot.mouseClick(soap_btn, Qt.LeftButton)
    
    # 7. Verify SOAP note appears
    soap_area = window.findChild(QTextEdit, "soapEdit")
    qtbot.waitUntil(
        lambda: "S:" in soap_area.toPlainText(),
        timeout=5000
    )
```

## Additional Resources

- [pytest-qt documentation](https://pytest-qt.readthedocs.io/)
- [PyQt5 documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [Qt Test Tutorial](https://doc.qt.io/qt-5/qtest-tutorial.html)