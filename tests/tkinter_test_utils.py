"""
Tkinter Test Utilities for Medical Assistant

This module provides utilities and helper functions for testing tkinter/ttkbootstrap UI components.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import time
import queue
from typing import Callable, Optional, Any, List, Tuple
from contextlib import contextmanager
import sys
import os


class TkinterTestCase:
    """Base class for tkinter UI tests with proper setup and teardown."""
    
    def setup_method(self, method):
        """Set up test environment before each test method."""
        self.root = None
        self.app = None
        self.update_queue = queue.Queue()
        self.exception_info = None
        
    def teardown_method(self, method):
        """Clean up after each test method."""
        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass
        self.root = None
        self.app = None
        
    def create_test_window(self, title="Test Window", theme="darkly"):
        """Create a test window with ttkbootstrap theme."""
        self.root = ttk.Window(title=title, themename=theme)
        self.root.withdraw()  # Hide by default
        return self.root
        
    def pump_events(self, duration=0.1):
        """Process tkinter events for a given duration."""
        start_time = time.time()
        while time.time() - start_time < duration:
            self.root.update_idletasks()
            self.root.update()
            time.sleep(0.01)
            
    def wait_for_condition(self, condition: Callable[[], bool], timeout=5.0, interval=0.1):
        """Wait for a condition to become true."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition():
                return True
            self.pump_events(interval)
        return False
        
    def simulate_click(self, widget, button=1):
        """Simulate a mouse click on a widget."""
        widget.event_generate("<Button-%d>" % button)
        widget.event_generate("<ButtonRelease-%d>" % button)
        self.pump_events(0.05)
        
    def simulate_key(self, widget, key, modifiers=None):
        """Simulate a key press."""
        if modifiers:
            widget.event_generate(f"<{modifiers}-{key}>")
        else:
            widget.event_generate(f"<{key}>")
        self.pump_events(0.05)
        
    def simulate_text_input(self, widget, text):
        """Simulate typing text into a widget."""
        widget.focus_set()
        self.pump_events(0.05)
        
        if hasattr(widget, 'delete'):
            widget.delete(0, tk.END)
        elif hasattr(widget, 'delete'):
            widget.delete('1.0', tk.END)
            
        if hasattr(widget, 'insert'):
            widget.insert(0, text)
        elif hasattr(widget, 'insert'):
            widget.insert('1.0', text)
            
        self.pump_events(0.05)
        
    def get_widget_text(self, widget):
        """Get text from various widget types."""
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            return widget.get()
        elif isinstance(widget, (tk.Text, tk.ScrolledText)):
            return widget.get('1.0', 'end-1c')
        elif isinstance(widget, (tk.Label, ttk.Label)):
            return widget.cget('text')
        elif isinstance(widget, (tk.Button, ttk.Button)):
            return widget.cget('text')
        else:
            return str(widget.cget('text'))
            
    def find_widget_by_text(self, parent, text, widget_class=None):
        """Find a widget by its text content."""
        for child in parent.winfo_children():
            try:
                if widget_class and not isinstance(child, widget_class):
                    continue
                    
                widget_text = self.get_widget_text(child)
                if widget_text == text:
                    return child
                    
                # Recursively search children
                result = self.find_widget_by_text(child, text, widget_class)
                if result:
                    return result
            except:
                pass
        return None
        
    def find_widgets_by_class(self, parent, widget_class):
        """Find all widgets of a specific class."""
        widgets = []
        for child in parent.winfo_children():
            if isinstance(child, widget_class):
                widgets.append(child)
            # Recursively search children
            widgets.extend(self.find_widgets_by_class(child, widget_class))
        return widgets
        
    def assert_widget_enabled(self, widget):
        """Assert that a widget is enabled."""
        state = str(widget['state'])
        assert 'disabled' not in state, f"Widget {widget} is disabled"
        
    def assert_widget_disabled(self, widget):
        """Assert that a widget is disabled."""
        state = str(widget['state'])
        assert 'disabled' in state, f"Widget {widget} is not disabled"
        
    def assert_widget_visible(self, widget):
        """Assert that a widget is visible."""
        assert widget.winfo_viewable(), f"Widget {widget} is not visible"
        
    def assert_widget_hidden(self, widget):
        """Assert that a widget is hidden."""
        assert not widget.winfo_viewable(), f"Widget {widget} is visible"
        
    @contextmanager
    def assert_dialog_shown(self, dialog_class=None):
        """Context manager to assert a dialog is shown."""
        dialogs_before = set(self.root.winfo_children())
        yield
        self.pump_events(0.1)
        dialogs_after = set(self.root.winfo_children())
        new_dialogs = dialogs_after - dialogs_before
        
        assert len(new_dialogs) > 0, "No dialog was shown"
        
        if dialog_class:
            assert any(isinstance(d, dialog_class) for d in new_dialogs), \
                f"No dialog of type {dialog_class} was shown"
                

class MockTkinterApp:
    """Mock tkinter application for testing."""
    
    def __init__(self, root):
        self.root = root
        self.components = {}
        self.callbacks = {}
        
    def register_callback(self, name: str, callback: Callable):
        """Register a callback function."""
        self.callbacks[name] = callback
        
    def trigger_callback(self, name: str, *args, **kwargs):
        """Trigger a registered callback."""
        if name in self.callbacks:
            return self.callbacks[name](*args, **kwargs)
            
    def add_component(self, name: str, widget):
        """Add a component to the mock app."""
        self.components[name] = widget
        
    def get_component(self, name: str):
        """Get a component by name."""
        return self.components.get(name)


def create_mock_workflow_ui(root):
    """Create a mock WorkflowUI for testing."""
    from workflow_ui import WorkflowUI
    
    class MockWorkflowUI(WorkflowUI):
        def __init__(self, parent):
            super().__init__(parent)
            self.mock_callbacks = {}
            
        def _create_record_tab(self, command_map):
            """Create mock record tab."""
            frame = ttk.Frame(self.parent)
            
            # Add basic controls
            self.record_button = ttk.Button(frame, text="Start Recording", 
                                          command=command_map.get('record_audio'))
            self.record_button.pack(pady=5)
            
            self.stop_button = ttk.Button(frame, text="Stop", 
                                        command=command_map.get('stop_recording'),
                                        state=DISABLED)
            self.stop_button.pack(pady=5)
            
            self.pause_button = ttk.Button(frame, text="Pause",
                                         command=command_map.get('pause_recording'),
                                         state=DISABLED)
            self.pause_button.pack(pady=5)
            
            self.timer_label = ttk.Label(frame, text="00:00")
            self.timer_label.pack(pady=5)
            
            self.status_label = ttk.Label(frame, text="Ready")
            self.status_label.pack(pady=5)
            
            return frame
            
        def _create_process_tab(self, command_map):
            """Create mock process tab."""
            frame = ttk.Frame(self.parent)
            
            self.refine_button = ttk.Button(frame, text="Refine Text",
                                          command=command_map.get('refine_text'))
            self.refine_button.pack(pady=5)
            
            self.improve_button = ttk.Button(frame, text="Improve Text",
                                           command=command_map.get('improve_text'))
            self.improve_button.pack(pady=5)
            
            return frame
            
        def _create_generate_tab(self, command_map):
            """Create mock generate tab."""
            frame = ttk.Frame(self.parent)
            
            self.soap_button = ttk.Button(frame, text="Generate SOAP Note",
                                        command=command_map.get('create_soap_note'))
            self.soap_button.pack(pady=5)
            
            self.letter_button = ttk.Button(frame, text="Generate Letter",
                                          command=command_map.get('create_letter'))
            self.letter_button.pack(pady=5)
            
            return frame
            
        def _create_recordings_tab(self, command_map):
            """Create mock recordings tab."""
            frame = ttk.Frame(self.parent)
            
            # Create treeview
            self.recordings_tree = ttk.Treeview(frame, columns=('date', 'duration', 'status'))
            self.recordings_tree.pack(fill=BOTH, expand=True)
            
            return frame
            
    return MockWorkflowUI(root)


def run_in_thread(func, *args, **kwargs):
    """Run a function in a separate thread and return the result."""
    result = [None]
    exception = [None]
    
    def wrapper():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e
            
    thread = threading.Thread(target=wrapper)
    thread.start()
    thread.join(timeout=5.0)
    
    if exception[0]:
        raise exception[0]
        
    return result[0]


def wait_for_widget_state(widget, state, timeout=2.0):
    """Wait for a widget to reach a specific state."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_state = str(widget['state'])
        if state in current_state:
            return True
        time.sleep(0.05)
    return False


def get_all_text_widgets(parent):
    """Get all text-based widgets in a window."""
    text_widgets = []
    widget_classes = (tk.Text, tk.Entry, ttk.Entry)
    
    def search_children(widget):
        for child in widget.winfo_children():
            if isinstance(child, widget_classes):
                text_widgets.append(child)
            search_children(child)
            
    search_children(parent)
    return text_widgets


def simulate_recording_workflow(test_case, duration=2.0):
    """Simulate a complete recording workflow."""
    # Find and click record button
    record_btn = test_case.find_widget_by_text(test_case.root, "Start Recording", ttk.Button)
    test_case.simulate_click(record_btn)
    
    # Wait for recording
    time.sleep(duration)
    
    # Find and click stop button
    stop_btn = test_case.find_widget_by_text(test_case.root, "Stop", ttk.Button)
    test_case.simulate_click(stop_btn)
    
    # Pump events to process stop
    test_case.pump_events(0.5)


def create_test_audio_data(duration=1.0, sample_rate=44100):
    """Create test audio data."""
    import numpy as np
    samples = int(duration * sample_rate)
    frequency = 440  # A4 note
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * frequency * t)
    return (audio * 32767).astype(np.int16)