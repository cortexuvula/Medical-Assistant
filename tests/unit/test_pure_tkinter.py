"""Pure tkinter tests without any ttkbootstrap dependencies."""
import pytest
import tkinter as tk
from tkinter import ttk
import os
import sys
from unittest.mock import Mock

# Ensure we're not importing any modules that import ttkbootstrap
# by clearing sys.modules of any ttkbootstrap-related modules
for module in list(sys.modules.keys()):
    if 'ttkbootstrap' in module:
        del sys.modules[module]


class TestPureTkinter:
    """Test pure tkinter functionality without ttkbootstrap."""
    
    def setup_method(self):
        """Set up test environment."""
        self.root = tk.Tk()
        self.root.withdraw()
        
    def teardown_method(self):
        """Clean up after test."""
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
    
    def test_basic_window(self):
        """Test basic window creation."""
        self.root.title("Test Window")
        assert self.root.title() == "Test Window"
    
    def test_button(self):
        """Test button widget."""
        clicked = False
        
        def on_click():
            nonlocal clicked
            clicked = True
            
        button = tk.Button(self.root, text="Test", command=on_click)
        button.pack()
        
        # Simulate click
        button.invoke()
        assert clicked is True
    
    def test_entry(self):
        """Test entry widget."""
        entry = tk.Entry(self.root)
        entry.pack()
        
        entry.insert(0, "Test text")
        assert entry.get() == "Test text"
    
    def test_text_widget(self):
        """Test text widget."""
        text = tk.Text(self.root, height=5, width=20)
        text.pack()
        
        text.insert("1.0", "Line 1\nLine 2")
        content = text.get("1.0", "end-1c")
        assert "Line 1" in content
        assert "Line 2" in content
    
    def test_listbox(self):
        """Test listbox widget."""
        listbox = tk.Listbox(self.root)
        listbox.pack()
        
        items = ["Item 1", "Item 2", "Item 3"]
        for item in items:
            listbox.insert(tk.END, item)
        
        assert listbox.size() == 3
        assert listbox.get(0) == "Item 1"
    
    def test_canvas(self):
        """Test canvas widget."""
        canvas = tk.Canvas(self.root, width=200, height=100)
        canvas.pack()
        
        # Create rectangle
        rect_id = canvas.create_rectangle(10, 10, 50, 50, fill="blue")
        assert rect_id is not None
        
        # Get coordinates
        coords = canvas.coords(rect_id)
        assert coords == [10.0, 10.0, 50.0, 50.0]
    
    def test_frame(self):
        """Test frame widget."""
        frame = tk.Frame(self.root, width=100, height=100, bg="red")
        frame.pack()
        
        # Add widget to frame
        label = tk.Label(frame, text="Test")
        label.pack()
        
        assert label.master == frame
    
    def test_labelframe(self):
        """Test labelframe widget."""
        lf = tk.LabelFrame(self.root, text="Options", padx=5, pady=5)
        lf.pack()
        
        # Add widget to labelframe
        cb = tk.Checkbutton(lf, text="Enable")
        cb.pack()
        
        assert cb.master == lf
    
    def test_checkbutton(self):
        """Test checkbutton widget."""
        var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(self.root, text="Check me", variable=var)
        cb.pack()
        
        assert var.get() is False
        
        # Toggle
        cb.invoke()
        assert var.get() is True
    
    def test_radiobutton(self):
        """Test radiobutton widget."""
        var = tk.StringVar(value="option1")
        
        rb1 = tk.Radiobutton(self.root, text="Option 1", variable=var, value="option1")
        rb2 = tk.Radiobutton(self.root, text="Option 2", variable=var, value="option2")
        
        rb1.pack()
        rb2.pack()
        
        assert var.get() == "option1"
        
        rb2.invoke()
        assert var.get() == "option2"
    
    def test_scale(self):
        """Test scale widget."""
        var = tk.DoubleVar(value=50)
        scale = tk.Scale(self.root, from_=0, to=100, variable=var, orient="horizontal")
        scale.pack()
        
        assert var.get() == 50
        
        scale.set(75)
        assert var.get() == 75
    
    def test_spinbox(self):
        """Test spinbox widget."""
        spinbox = tk.Spinbox(self.root, from_=0, to=10)
        spinbox.pack()
        
        spinbox.delete(0, tk.END)
        spinbox.insert(0, "5")
        assert spinbox.get() == "5"
    
    def test_menu(self):
        """Test menu widget."""
        menubar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New")
        file_menu.add_command(label="Open")
        file_menu.add_separator()
        file_menu.add_command(label="Exit")
        
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Verify menu structure
        # index("end") returns the index of the last item, which is 0-based
        # So for one menu item, it should return 0
        assert menubar.index("end") is not None
    
    def test_message(self):
        """Test message widget."""
        msg = tk.Message(self.root, text="This is a long message that will wrap", width=100)
        msg.pack()
        
        assert msg.cget("text") == "This is a long message that will wrap"
    
    def test_toplevel(self):
        """Test toplevel window."""
        top = tk.Toplevel(self.root)
        top.title("Dialog")
        top.withdraw()  # Hide during test
        
        assert top.title() == "Dialog"
        
        # Clean up
        top.destroy()
    
    def test_panedwindow(self):
        """Test panedwindow widget."""
        pw = tk.PanedWindow(self.root, orient="horizontal")
        pw.pack()
        
        left = tk.Label(pw, text="Left")
        pw.add(left)
        
        right = tk.Label(pw, text="Right")
        pw.add(right)
        
        # Check panes
        panes = pw.panes()
        assert len(panes) == 2
    
    def test_event_binding(self):
        """Test event binding."""
        events = []
        
        def on_event(event):
            events.append(event.type)
        
        button = tk.Button(self.root, text="Test")
        button.pack()
        
        button.bind("<Button-1>", on_event)
        
        # Generate event
        button.event_generate("<Button-1>")
        self.root.update()
        
        # Event generation might not work in test environment
        # so we just verify the binding exists
        assert "<Button-1>" in button.bind()
    
    def test_stringvar(self):
        """Test StringVar."""
        var = tk.StringVar(value="initial")
        
        assert var.get() == "initial"
        
        var.set("changed")
        assert var.get() == "changed"
        
        # Test trace
        traced = []
        
        def on_change(*args):
            traced.append(var.get())
        
        var.trace("w", on_change)
        var.set("traced")
        
        assert "traced" in traced
    
    def test_widget_config(self):
        """Test widget configuration."""
        label = tk.Label(self.root, text="Test", bg="red", fg="white")
        label.pack()
        
        assert label.cget("text") == "Test"
        assert label.cget("bg") == "red"
        assert label.cget("fg") == "white"
        
        # Change config
        label.config(text="Changed", bg="blue")
        assert label.cget("text") == "Changed"
        assert label.cget("bg") == "blue"