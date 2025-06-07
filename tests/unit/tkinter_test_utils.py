"""Utilities for testing tkinter/ttkbootstrap applications."""
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttk_bs
from unittest.mock import Mock, MagicMock
import time
from typing import Optional, Callable, Any, List, Union


class TkinterTestCase:
    """Base class for tkinter UI tests."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        self.root = ttk_bs.Window(themename="darkly")
        self.root.withdraw()  # Hide window during tests
        self.widgets_to_destroy = []
        
    def teardown_method(self):
        """Clean up after each test."""
        # Destroy tracked widgets
        for widget in self.widgets_to_destroy:
            try:
                if widget.winfo_exists():
                    widget.destroy()
            except:
                pass
        
        # Process remaining events
        try:
            self.root.update_idletasks()
        except:
            pass
        
        # Destroy root
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
    
    def create_widget(self, widget_class, parent=None, **kwargs):
        """Create a widget and track it for cleanup."""
        if parent is None:
            parent = self.root
        widget = widget_class(parent, **kwargs)
        self.widgets_to_destroy.append(widget)
        return widget
    
    def process_events(self, delay=0.01):
        """Process pending tkinter events."""
        self.root.update()
        if delay > 0:
            time.sleep(delay)
        self.root.update_idletasks()
    
    def click_button(self, button: tk.Button):
        """Simulate button click."""
        button.invoke()
        self.process_events()
    
    def enter_text(self, widget: Union[tk.Entry, tk.Text], text: str):
        """Enter text into an Entry or Text widget."""
        if isinstance(widget, tk.Entry):
            widget.delete(0, tk.END)
            widget.insert(0, text)
        elif isinstance(widget, tk.Text):
            widget.delete("1.0", tk.END)
            widget.insert("1.0", text)
        self.process_events()
    
    def get_text(self, widget: Union[tk.Entry, tk.Text]) -> str:
        """Get text from Entry or Text widget."""
        if isinstance(widget, tk.Entry):
            return widget.get()
        elif isinstance(widget, tk.Text):
            return widget.get("1.0", tk.END).strip()
        return ""
    
    def select_combobox_value(self, combobox: ttk.Combobox, value: str):
        """Select a value in a combobox."""
        combobox.set(value)
        combobox.event_generate("<<ComboboxSelected>>")
        self.process_events()
    
    def select_notebook_tab(self, notebook: ttk.Notebook, index: int):
        """Select a tab in a notebook."""
        notebook.select(index)
        notebook.event_generate("<<NotebookTabChanged>>")
        self.process_events()
    
    def simulate_keypress(self, widget: tk.Widget, key: str, modifiers: List[str] = None):
        """Simulate a key press event."""
        if modifiers is None:
            modifiers = []
        
        # Build event string
        event_str = "<"
        if modifiers:
            event_str += "-".join(modifiers) + "-"
        event_str += key + ">"
        
        widget.focus_set()
        widget.event_generate(event_str)
        self.process_events()
    
    def wait_for_condition(self, condition: Callable[[], bool], timeout: float = 2.0, interval: float = 0.1):
        """Wait for a condition to become true."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition():
                return True
            self.process_events(interval)
        return False
    
    def assert_widget_enabled(self, widget: tk.Widget):
        """Assert that a widget is enabled."""
        assert str(widget['state']) != 'disabled', f"Widget {widget} is disabled"
    
    def assert_widget_disabled(self, widget: tk.Widget):
        """Assert that a widget is disabled."""
        assert str(widget['state']) == 'disabled', f"Widget {widget} is not disabled"
    
    def assert_widget_visible(self, widget: tk.Widget):
        """Assert that a widget is visible."""
        assert widget.winfo_viewable(), f"Widget {widget} is not visible"
    
    def find_widget_by_text(self, parent: tk.Widget, text: str, widget_class=None) -> Optional[tk.Widget]:
        """Find a widget by its text content."""
        for child in parent.winfo_children():
            try:
                if widget_class and not isinstance(child, widget_class):
                    continue
                    
                # Check button/label text
                if hasattr(child, 'cget'):
                    if 'text' in child.keys():
                        if child.cget('text') == text:
                            return child
                
                # Recursively search children
                found = self.find_widget_by_text(child, text, widget_class)
                if found:
                    return found
            except:
                continue
        return None
    
    def find_widgets_by_class(self, parent: tk.Widget, widget_class) -> List[tk.Widget]:
        """Find all widgets of a specific class."""
        widgets = []
        for child in parent.winfo_children():
            if isinstance(child, widget_class):
                widgets.append(child)
            # Recursively search children
            widgets.extend(self.find_widgets_by_class(child, widget_class))
        return widgets


def create_mock_workflow_ui():
    """Create a mock WorkflowUI object for testing."""
    mock_ui = MagicMock()
    
    # Mock the main components
    mock_ui.root = Mock()
    mock_ui.workflow_notebook = Mock()
    mock_ui.editor_notebook = Mock()
    mock_ui.status_var = tk.StringVar()
    mock_ui.recording_timer_var = tk.StringVar()
    mock_ui.queue_status_var = tk.StringVar()
    
    # Mock recording state
    mock_ui.recording_manager = Mock()
    mock_ui.recording_manager.is_recording = False
    mock_ui.recording_manager.is_paused = False
    
    # Mock methods
    mock_ui.update_ui_state = Mock()
    mock_ui.show_error = Mock()
    mock_ui.show_info = Mock()
    mock_ui.process_recording = Mock()
    mock_ui.generate_soap_note = Mock()
    mock_ui.send_message = Mock()
    
    # Mock workflow components
    mock_ui.record_button = Mock()
    mock_ui.stop_button = Mock()
    mock_ui.pause_button = Mock()
    mock_ui.transcript_text = Mock()
    mock_ui.refined_text = Mock()
    mock_ui.improved_text = Mock()
    mock_ui.soap_text = Mock()
    mock_ui.letter_text = Mock()
    
    return mock_ui


def simulate_recording_workflow(test_case: TkinterTestCase, ui_mock: MagicMock):
    """Simulate a complete recording workflow for testing."""
    # Start recording
    ui_mock.recording_manager.is_recording = True
    ui_mock.recording_manager.is_paused = False
    ui_mock.update_ui_state()
    test_case.process_events(0.1)
    
    # Simulate some recording time
    ui_mock.recording_timer_var.set("00:05")
    test_case.process_events(0.1)
    
    # Stop recording
    ui_mock.recording_manager.is_recording = False
    ui_mock.update_ui_state()
    test_case.process_events(0.1)
    
    # Simulate transcript
    ui_mock.transcript_text.get.return_value = "Patient presents with headache."
    
    # Process recording
    ui_mock.process_recording()
    test_case.process_events(0.1)