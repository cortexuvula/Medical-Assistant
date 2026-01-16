# Contributing to Medical Assistant

This document outlines coding standards and architectural patterns for the Medical Assistant project.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Import Conventions](#import-conventions)
3. [Error Handling](#error-handling)
4. [UI Patterns](#ui-patterns)
5. [Settings Management](#settings-management)
6. [Provider Pattern](#provider-pattern)
7. [Agent System](#agent-system)
8. [Testing](#testing)
9. [Security](#security)

---

## Project Structure

```
src/
├── ai/                    # AI providers and processing
│   ├── agents/            # Specialized AI agents
│   └── providers/         # LLM provider implementations
├── audio/                 # Audio recording and processing
├── core/                  # Core application logic and mixins
├── database/              # Database management and migrations
├── managers/              # Singleton managers (agent, translation, etc.)
├── processing/            # Document generation and processing
│   └── generators/        # Specific document generators
├── settings/              # Settings types and management
├── stt_providers/         # Speech-to-text providers
├── translation/           # Translation providers
├── tts_providers/         # Text-to-speech providers
├── ui/                    # User interface
│   ├── components/        # Reusable UI components
│   └── dialogs/           # Dialog windows
└── utils/                 # Utility functions and helpers
```

### File Naming

- Use `snake_case` for all Python files
- Suffix pattern:
  - `*_dialog.py` - Dialog windows
  - `*_provider.py` - Service providers
  - `*_manager.py` - Singleton managers
  - `*_controller.py` - UI controllers
  - `*_mixin.py` - Class mixins

---

## Import Conventions

### Tkinter Constants

**Always import constants explicitly from `ttkbootstrap.constants`:**

```python
# CORRECT
from ttkbootstrap.constants import BOTH, X, Y, LEFT, RIGHT, END, NORMAL, DISABLED, WORD, VERTICAL

# WRONG - will cause NameError
text_widget.delete("1.0", END)  # END not imported!

# WRONG - inconsistent with codebase
text_widget.delete("1.0", tk.END)  # Works but inconsistent
```

**Standard tkinter constant imports for dialogs:**

```python
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import (
    BOTH, X, Y,                    # Pack/grid fill options
    LEFT, RIGHT, TOP, BOTTOM,      # Side options
    VERTICAL, HORIZONTAL,          # Orient options
    NORMAL, DISABLED,              # State options
    END, WORD,                     # Text widget options
    W, E, N, S, NW, NE, SW, SE    # Anchor options
)
from tkinter import messagebox, filedialog
```

### Module Imports

```python
# Standard library first
import os
import sys
import logging
from typing import Dict, List, Optional, Any, Callable

# Third-party libraries
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, END, NORMAL, DISABLED

# Local imports - use relative for same package, absolute for cross-package
from settings.settings import SETTINGS, save_settings
from utils.error_handling import OperationResult, handle_errors
from ui.dialogs.base_dialog import BaseDialog
```

---

## Error Handling

### Use OperationResult for Operations

```python
from utils.error_handling import OperationResult, handle_errors, ErrorSeverity

class MyProcessor:
    @handle_errors(ErrorSeverity.ERROR, error_message="Failed to process", return_type="result")
    def process_data(self, data: str) -> OperationResult[Dict[str, Any]]:
        if not data.strip():
            return OperationResult.failure("No data provided", error_code="EMPTY_INPUT")

        result = self._do_processing(data)
        return OperationResult.success({"text": result})
```

### Exception Handling in UI

```python
# Wrap UI operations that may fail after widget destruction
def _on_close(self) -> None:
    """Handle dialog close."""
    try:
        self._cleanup()
    except tk.TclError:
        pass  # Widget may already be destroyed

    try:
        self.dialog.destroy()
    except tk.TclError:
        pass
```

### Attribute Checks for Optional UI Elements

```python
def pause(self) -> None:
    """Pause playback."""
    self.is_playing = False

    # Check if attribute exists before accessing
    if hasattr(self, 'play_btn') and self.play_btn:
        try:
            self.play_btn.configure(text="Play")
        except tk.TclError:
            pass  # Widget may have been destroyed
```

---

## UI Patterns

### Dialog Base Class

Inherit from appropriate base class when available:

```python
from ui.dialogs.base_results_dialog import BaseResultsDialog

class MyResultsDialog(BaseResultsDialog):
    def _get_dialog_title(self) -> str:
        return "My Results"

    def _format_results(self, results: Any) -> str:
        return str(results)

    def _get_pdf_filename(self) -> str:
        return "my_results.pdf"
```

### Dialog Structure

```python
class MyDialog:
    def __init__(self, parent):
        self.parent = parent
        self.result = None
        self._create_dialog()
        self._create_widgets()
        self._bind_events()

    def _create_dialog(self) -> None:
        """Create the dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("My Dialog")
        self.dialog.transient(self.parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self) -> None:
        """Create dialog widgets."""
        pass

    def _bind_events(self) -> None:
        """Bind keyboard and other events."""
        self.dialog.bind('<Escape>', lambda e: self._on_close())

    def _on_close(self) -> None:
        """Handle dialog close."""
        try:
            self.dialog.destroy()
        except tk.TclError:
            pass

    def show(self) -> Optional[Dict[str, Any]]:
        """Show dialog and return result."""
        self.dialog.grab_set()
        self.dialog.wait_window()
        return self.result
```

### Widget State Management

```python
# Use constants, not strings
button.configure(state=DISABLED)  # CORRECT
button.configure(state="disabled")  # WRONG - use constant

# Check widget exists before configuring
if hasattr(self, 'my_button') and self.my_button:
    self.my_button.configure(state=NORMAL)
```

---

## Settings Management

### Accessing Settings

```python
from settings.settings import SETTINGS, save_settings, load_settings

# Read settings with defaults
wpm = SETTINGS.get("rsvp", {}).get("wpm", 300)

# Write settings
if "rsvp" not in SETTINGS:
    SETTINGS["rsvp"] = {}
SETTINGS["rsvp"]["wpm"] = new_wpm
save_settings(SETTINGS)

# Reload from disk if needed
current_settings = load_settings()
```

### Settings Keys Convention

```python
# Use nested dictionaries for related settings
SETTINGS = {
    "rsvp": {
        "wpm": 300,
        "font_size": 48,
        "dark_theme": True
    },
    "rsvp_reader": {
        "last_directory": "",
        "auto_start_after_load": False
    }
}
```

---

## Provider Pattern

### Base Provider Class

```python
from abc import ABC, abstractmethod

class BaseSTTProvider(ABC):
    """Base class for speech-to-text providers."""

    @abstractmethod
    def transcribe(self, audio_segment) -> str:
        """Transcribe audio to text."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test API connectivity."""
        pass
```

### Provider Implementation

```python
class MySTTProvider(BaseSTTProvider):
    def __init__(self):
        self.api_key = self._get_api_key()

    def _get_api_key(self) -> Optional[str]:
        from utils.security import get_security_manager
        return get_security_manager().get_api_key("my_provider")

    def transcribe(self, audio_segment) -> str:
        if not self.api_key:
            raise ValueError("API key not configured")
        # Implementation here
        return transcribed_text

    def test_connection(self) -> bool:
        try:
            # Test API
            return True
        except Exception:
            return False
```

### Deprecated Model Handling

```python
# Map deprecated models to current equivalents
DEPRECATED_MODEL_MAPPING = {
    "old-model-name": "new-model-name",
}

def _normalize_model_name(model: str) -> str:
    """Normalize deprecated model names."""
    if model in DEPRECATED_MODEL_MAPPING:
        new_model = DEPRECATED_MODEL_MAPPING[model]
        logging.warning(f"Model '{model}' is deprecated, using '{new_model}'")
        return new_model
    return model
```

---

## Agent System

### Creating a New Agent

1. Create agent file in `src/ai/agents/`:

```python
from ai.agents.base import BaseAgent
from ai.agents.models import AgentTask, AgentResponse, AgentType

class MyAgent(BaseAgent):
    """Description of what this agent does."""

    def __init__(self, config=None):
        super().__init__(config)
        self.agent_type = AgentType.MY_AGENT

    def execute(self, task: AgentTask) -> AgentResponse:
        """Execute the agent task."""
        # Validate input
        if not task.input_data.get("content"):
            return AgentResponse(
                success=False,
                error="No content provided"
            )

        # Process
        result = self._process(task.input_data["content"])

        return AgentResponse(
            success=True,
            result=result,
            metadata={"source": task.input_data.get("source", "unknown")}
        )
```

2. Register in `src/ai/agents/models.py`:

```python
class AgentType(str, Enum):
    # ... existing types
    MY_AGENT = "my_agent"
```

3. Register in `src/managers/agent_manager.py`

---

## Testing

### Test File Location

```
tests/
├── unit/                  # Unit tests
│   ├── test_services.py
│   └── test_stt_providers/
├── integration/           # Integration tests
└── regression/            # Regression tests
```

### Test Structure

```python
import pytest
from unittest.mock import Mock, patch

class TestMyFeature:
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_settings = {"key": "value"}

    def test_success_case(self):
        """Test description."""
        result = my_function(valid_input)
        assert result.success

    def test_failure_case(self):
        """Test error handling."""
        result = my_function(invalid_input)
        assert not result.success
        assert "error" in result.error.lower()

    @patch('module.external_api')
    def test_with_mock(self, mock_api):
        """Test with mocked dependency."""
        mock_api.return_value = {"data": "test"}
        result = my_function()
        mock_api.assert_called_once()
```

---

## Security

### API Key Handling

```python
from utils.security import get_security_manager

# Get API key securely
security_manager = get_security_manager()
api_key = security_manager.get_api_key("provider_name")

# Validate before use
from utils.validation import validate_api_key
is_valid, error = validate_api_key("provider_name", api_key)
if not is_valid:
    raise ValueError(f"Invalid API key: {error}")
```

### Input Sanitization

```python
from utils.validation import sanitize_prompt

# Sanitize user input before sending to LLM
sanitized_text = sanitize_prompt(user_input)
```

### Secure API Calls

```python
from utils.security_decorators import secure_api_call
from utils.resilience import resilient_api_call

@secure_api_call("provider_name")
@resilient_api_call(max_retries=3, initial_delay=1.0)
def _api_call(client, model, messages, temperature):
    """Make API call with security and resilience."""
    return client.messages.create(
        model=model,
        messages=messages,
        temperature=temperature
    )
```

---

## Commit Messages

Follow conventional commits format:

```
feat: add new medication analysis feature
fix: handle missing END import in dialog
refactor: extract PDF processing into separate module
docs: update CONTRIBUTING.md with new patterns
test: add unit tests for RSVP dialog
chore: update dependencies
```

---

## Pull Request Checklist

- [ ] Code follows the patterns in this document
- [ ] All imports are explicit (no missing constants)
- [ ] Error handling uses `OperationResult` or try/except appropriately
- [ ] UI code handles widget destruction gracefully
- [ ] Settings are accessed through `SETTINGS` dict
- [ ] Sensitive data uses security manager
- [ ] Tests pass locally
- [ ] No hardcoded API keys or secrets
