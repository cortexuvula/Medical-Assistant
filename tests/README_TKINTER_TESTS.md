# Tkinter UI Testing Guide for Medical Assistant

This document describes the tkinter/ttkbootstrap UI testing framework for the Medical Assistant application.

## Overview

The Medical Assistant application uses tkinter with ttkbootstrap for its UI. This testing framework provides comprehensive coverage of UI components, workflows, and user interactions using tkinter-specific testing utilities.

## Test Structure

### Test Files

- `tkinter_test_utils.py` - Core testing utilities and base classes
- `test_tkinter_ui_basic.py` - Basic tkinter widget and interaction tests
- `test_tkinter_ui_medical_assistant.py` - Medical Assistant specific UI tests
- `test_tkinter_workflow_tabs.py` - Tests for workflow tabs (Record, Process, Generate, Recordings)
- `test_tkinter_chat_and_editors.py` - Tests for chat interface and text editor tabs

### Test Categories

1. **Basic UI Tests** - Test fundamental tkinter/ttkbootstrap functionality
2. **Component Tests** - Test individual UI components (buttons, text widgets, etc.)
3. **Workflow Tests** - Test complete user workflows (recording, processing, generation)
4. **Integration Tests** - Test interaction between different UI components

## Running Tests

### Command Line

```bash
# Run all tkinter UI tests
python tests/run_tkinter_ui_tests.py

# Run with verbose output
python tests/run_tkinter_ui_tests.py --verbose

# Run in headless mode (Linux)
python tests/run_tkinter_ui_tests.py --headless

# Run with coverage
python tests/run_tkinter_ui_tests.py --coverage

# Run specific test file
pytest tests/unit/test_tkinter_ui_basic.py -v

# Run tests matching pattern
pytest tests/unit/ -k "tkinter" -v
```

### Using pytest directly

```bash
# Run all UI tests
pytest -m ui -v

# Run tkinter tests only
pytest tests/unit/test_tkinter*.py -v

# Run with specific markers
pytest -m "ui and not slow" -v
```

## Key Testing Utilities

### TkinterTestCase Base Class

The `TkinterTestCase` class provides essential testing functionality:

```python
class TestMyUI(TkinterTestCase):
    def test_button_click(self):
        self.create_test_window()
        
        button = ttk.Button(self.root, text="Click Me")
        button.pack()
        
        # Simulate click
        self.simulate_click(button)
        
        # Pump events to process
        self.pump_events()
```

### Available Methods

- `create_test_window(title, theme)` - Create a test window
- `pump_events(duration)` - Process tkinter events
- `simulate_click(widget, button)` - Simulate mouse clicks
- `simulate_key(widget, key, modifiers)` - Simulate keyboard input
- `simulate_text_input(widget, text)` - Type text into widgets
- `get_widget_text(widget)` - Get text from various widget types
- `find_widget_by_text(parent, text, widget_class)` - Find widgets by text content
- `find_widgets_by_class(parent, widget_class)` - Find all widgets of a type
- `assert_widget_enabled/disabled(widget)` - Check widget states
- `assert_widget_visible/hidden(widget)` - Check widget visibility
- `wait_for_condition(condition, timeout)` - Wait for conditions

## Writing New Tests

### Basic Test Structure

```python
import pytest
from tkinter_test_utils import TkinterTestCase

@pytest.mark.ui
class TestNewFeature(TkinterTestCase):
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up any mocks needed."""
        with patch('some_module') as mock:
            yield mock
    
    def test_feature(self):
        """Test description."""
        self.create_test_window()
        
        # Create UI components
        # Perform actions
        # Assert results
```

### Testing Workflows

```python
def test_complete_workflow(self):
    """Test a complete user workflow."""
    self.create_test_window()
    
    # Step 1: Create UI
    workflow_ui = create_mock_workflow_ui(self.root)
    notebook = workflow_ui.create_workflow_tabs({})
    
    # Step 2: Simulate user actions
    self.simulate_click(workflow_ui.record_button)
    self.pump_events(0.5)
    
    # Step 3: Verify state changes
    self.assert_widget_disabled(workflow_ui.record_button)
    self.assert_widget_enabled(workflow_ui.stop_button)
```

### Testing Async Operations

```python
def test_async_operation(self):
    """Test async operations."""
    self.create_test_window()
    
    result_ready = False
    
    def async_operation():
        nonlocal result_ready
        # Simulate async work
        self.root.after(100, lambda: setattr(locals(), 'result_ready', True))
    
    async_operation()
    
    # Wait for completion
    self.wait_for_condition(lambda: result_ready, timeout=2.0)
    assert result_ready
```

## Platform Considerations

### Windows
- Display always available
- No special setup required
- All tests should run normally

### macOS
- Display always available
- May require accessibility permissions for some operations
- Use `self.pump_events()` liberally to ensure UI updates

### Linux
- May require Xvfb for headless testing
- Use `--headless` flag when running without display
- Install Xvfb: `sudo apt-get install xvfb`

## Mock Strategies

### Mocking External Dependencies

```python
@pytest.fixture(autouse=True)
def mock_environment(self):
    """Mock external dependencies."""
    patches = {
        'database': patch('database.Database'),
        'audio': patch('audio.AudioHandler'),
        'ai_processor': patch('ai_processor.AIProcessor'),
    }
    
    mocks = {}
    for name, patcher in patches.items():
        mocks[name] = patcher.start()
    
    yield mocks
    
    for patcher in patches.values():
        patcher.stop()
```

### Creating Mock UI Components

```python
def create_mock_workflow_ui(root):
    """Create a mock WorkflowUI for testing."""
    class MockWorkflowUI(WorkflowUI):
        def __init__(self, parent):
            super().__init__(parent)
            # Add test-specific attributes
            self.test_callbacks = {}
```

## Best Practices

1. **Always clean up**: Use proper setup/teardown to avoid test pollution
2. **Pump events**: Call `self.pump_events()` after UI actions
3. **Mock external dependencies**: Don't let tests touch real files/APIs
4. **Test user workflows**: Focus on how users interact with the UI
5. **Use fixtures**: Share common setup code via fixtures
6. **Mark tests appropriately**: Use `@pytest.mark.ui` for UI tests
7. **Handle platform differences**: Account for platform-specific behavior
8. **Keep tests focused**: One test should test one thing
9. **Use descriptive names**: Test names should explain what they test
10. **Avoid timing dependencies**: Use `wait_for_condition` instead of `sleep`

## Troubleshooting

### Common Issues

1. **"No display available"**
   - Linux: Use `--headless` flag or export DISPLAY=:0
   - Check if X server is running

2. **Widget not found**
   - Ensure `pump_events()` is called after creating widgets
   - Check widget hierarchy with `find_widgets_by_class()`

3. **Events not processed**
   - Add more `pump_events()` calls
   - Increase pump duration: `pump_events(0.5)`

4. **Tests hang**
   - Check for infinite loops in event handlers
   - Add timeout to `wait_for_condition()`

5. **Intermittent failures**
   - Add more synchronization with `wait_for_condition()`
   - Avoid hard-coded delays

### Debug Helpers

```python
# Print widget hierarchy
def print_widget_tree(widget, indent=0):
    print("  " * indent + str(widget))
    for child in widget.winfo_children():
        print_widget_tree(child, indent + 1)

# Check widget state
print(f"Widget state: {widget['state']}")
print(f"Widget visible: {widget.winfo_viewable()}")
print(f"Widget geometry: {widget.winfo_geometry()}")
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Run Tkinter UI Tests
  run: |
    # Install dependencies
    pip install -r requirements.txt
    
    # Run tests with virtual display
    xvfb-run -a python tests/run_tkinter_ui_tests.py --headless
```

### Local Development

For rapid development, you can run specific tests:

```bash
# Run and watch a specific test
pytest tests/unit/test_tkinter_ui_basic.py::TestBasicTkinterUI::test_button_click -v

# Run with debugging
pytest tests/unit/test_tkinter_workflow_tabs.py -v -s --pdb
```

## Contributing

When adding new UI tests:

1. Follow the existing test structure
2. Add appropriate markers (`@pytest.mark.ui`)
3. Mock all external dependencies
4. Test both happy path and error cases
5. Document any platform-specific considerations
6. Update this documentation if adding new utilities

## Resources

- [Tkinter documentation](https://docs.python.org/3/library/tkinter.html)
- [ttkbootstrap documentation](https://ttkbootstrap.readthedocs.io/)
- [pytest documentation](https://docs.pytest.org/)
- [Medical Assistant Wiki](../docs/)