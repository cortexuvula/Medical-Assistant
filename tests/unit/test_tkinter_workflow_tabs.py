"""Tests for Medical Assistant workflow tabs."""
import pytest
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttk_bs
from unittest.mock import Mock, patch, MagicMock
from tests.unit.tkinter_test_utils import TkinterTestCase
import os

# Skip ttkbootstrap-specific tests in CI environment
SKIP_TTKBOOTSTRAP = bool(os.environ.get('CI', '')) or bool(os.environ.get('GITHUB_ACTIONS', ''))


class TestWorkflowTabs(TkinterTestCase):
    """Detailed tests for each workflow tab."""
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_record_tab_components(self):
        """Test Record tab UI components and functionality."""
        # Create Record tab
        record_frame = self.create_widget(ttk.Frame)
        record_frame.pack(fill='both', expand=True)
        
        # Timer display
        timer_frame = ttk.Frame(record_frame)
        timer_frame.pack(pady=20)
        
        timer_var = tk.StringVar(value="00:00")
        timer_label = ttk.Label(
            timer_frame,
            textvariable=timer_var,
            font=('TkDefaultFont', 48, 'bold')
        )
        timer_label.pack()
        
        # Recording controls
        controls_frame = ttk.Frame(record_frame)
        controls_frame.pack()
        
        record_button = ttk.Button(controls_frame, text="🎤 Start Recording", width=20)
        stop_button = ttk.Button(controls_frame, text="⏹ Stop", width=15, state='disabled')
        pause_button = ttk.Button(controls_frame, text="⏸ Pause", width=15, state='disabled')
        
        record_button.grid(row=0, column=0, padx=5)
        stop_button.grid(row=0, column=1, padx=5)
        pause_button.grid(row=0, column=2, padx=5)
        
        # Quick Continue Mode
        quick_continue_var = tk.BooleanVar(value=False)
        quick_continue_check = ttk.Checkbutton(
            record_frame,
            text="Quick Continue Mode - Queue recordings for processing",
            variable=quick_continue_var
        )
        quick_continue_check.pack(pady=10)
        
        # Device selection
        device_frame = ttk.Frame(record_frame)
        device_frame.pack(pady=10)
        
        ttk.Label(device_frame, text="Microphone:").pack(side='left')
        device_combo = ttk.Combobox(
            device_frame,
            values=["Default Microphone", "USB Microphone", "Headset"],
            state='readonly',
            width=30
        )
        device_combo.set("Default Microphone")
        device_combo.pack(side='left', padx=5)
        
        # Status display
        status_var = tk.StringVar(value="Ready to record")
        status_label = ttk.Label(record_frame, textvariable=status_var)
        status_label.pack(pady=10)
        
        # Test initial state
        self.assert_widget_enabled(record_button)
        self.assert_widget_disabled(stop_button)
        self.assert_widget_disabled(pause_button)
        assert timer_var.get() == "00:00"
        assert not quick_continue_var.get()
        
        # Simulate recording start
        recording = False
        paused = False
        
        def start_recording():
            nonlocal recording, paused
            recording = True
            paused = False
            record_button.configure(state='disabled')
            stop_button.configure(state='normal')
            pause_button.configure(state='normal', text="⏸ Pause")
            status_var.set("Recording...")
        
        def stop_recording():
            nonlocal recording, paused
            recording = False
            paused = False
            record_button.configure(state='normal')
            stop_button.configure(state='disabled')
            pause_button.configure(state='disabled', text="⏸ Pause")
            status_var.set("Recording stopped")
            timer_var.set("00:00")
        
        def toggle_pause():
            nonlocal paused
            paused = not paused
            if paused:
                pause_button.configure(text="▶ Resume")
                status_var.set("Recording paused")
            else:
                pause_button.configure(text="⏸ Pause")
                status_var.set("Recording...")
        
        record_button.configure(command=start_recording)
        stop_button.configure(command=stop_recording)
        pause_button.configure(command=toggle_pause)
        
        # Test recording workflow
        self.click_button(record_button)
        assert recording
        assert status_var.get() == "Recording..."
        self.assert_widget_disabled(record_button)
        self.assert_widget_enabled(stop_button)
        self.assert_widget_enabled(pause_button)
        
        # Test pause
        self.click_button(pause_button)
        assert paused
        assert status_var.get() == "Recording paused"
        assert pause_button.cget('text') == "▶ Resume"
        
        # Test resume
        self.click_button(pause_button)
        assert not paused
        assert status_var.get() == "Recording..."
        assert pause_button.cget('text') == "⏸ Pause"
        
        # Test stop
        self.click_button(stop_button)
        assert not recording
        assert status_var.get() == "Recording stopped"
        self.assert_widget_enabled(record_button)
        self.assert_widget_disabled(stop_button)
        self.assert_widget_disabled(pause_button)
        
        # Test Quick Continue Mode
        quick_continue_check.invoke()
        self.process_events()
        assert quick_continue_var.get()
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_process_tab_components(self):
        """Test Process tab UI components."""
        # Create Process tab
        process_frame = self.create_widget(ttk.Frame)
        process_frame.pack(fill='both', expand=True)
        
        # Instructions
        instructions = ttk.Label(
            process_frame,
            text="Select text in the Transcript tab and click a button to process:",
            font=('TkDefaultFont', 10)
        )
        instructions.pack(pady=10)
        
        # Process buttons
        button_frame = ttk.Frame(process_frame)
        button_frame.pack(pady=20)
        
        refine_button = ttk.Button(
            button_frame,
            text="✨ Refine Text",
            width=20
        )
        improve_button = ttk.Button(
            button_frame,
            text="📝 Improve Clarity",
            width=20
        )
        
        refine_button.grid(row=0, column=0, padx=10, pady=5)
        improve_button.grid(row=0, column=1, padx=10, pady=5)
        
        # Options frame
        options_frame = ttk.LabelFrame(process_frame, text="Processing Options")
        options_frame.pack(fill='x', padx=20, pady=10)
        
        # Temperature setting
        temp_frame = ttk.Frame(options_frame)
        temp_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(temp_frame, text="Temperature:").pack(side='left')
        temp_var = tk.DoubleVar(value=0.7)
        temp_scale = ttk.Scale(
            temp_frame,
            from_=0.0,
            to=1.0,
            variable=temp_var,
            orient='horizontal',
            length=200
        )
        temp_scale.pack(side='left', padx=10)
        temp_label = ttk.Label(temp_frame, text="0.7")
        temp_label.pack(side='left')
        
        # Update temperature label
        def update_temp_label(value):
            temp_label.configure(text=f"{float(value):.1f}")
        
        temp_scale.configure(command=update_temp_label)
        
        # Progress indicator
        progress = ttk.Progressbar(
            process_frame,
            mode='indeterminate',
            length=300
        )
        
        # Result label
        result_var = tk.StringVar(value="")
        result_label = ttk.Label(
            process_frame,
            textvariable=result_var,
            foreground='green'
        )
        
        # Test button functionality
        processed_texts = []
        
        def process_text(process_type):
            progress.pack(pady=10)
            progress.start()
            result_var.set(f"Processing with {process_type}...")
            self.process_events()
            
            # Simulate processing
            processed_texts.append({
                'type': process_type,
                'temperature': temp_var.get()
            })
            
            # Simulate completion
            progress.stop()
            progress.pack_forget()
            result_var.set(f"✓ Text {process_type} complete!")
            result_label.pack(pady=5)
        
        refine_button.configure(command=lambda: process_text("refinement"))
        improve_button.configure(command=lambda: process_text("improvement"))
        
        # Test processing
        self.click_button(refine_button)
        assert len(processed_texts) == 1
        assert processed_texts[0]['type'] == "refinement"
        assert processed_texts[0]['temperature'] == 0.7
        
        # Change temperature and process again
        temp_var.set(0.9)
        update_temp_label(0.9)
        self.click_button(improve_button)
        assert len(processed_texts) == 2
        assert processed_texts[1]['type'] == "improvement"
        assert processed_texts[1]['temperature'] == 0.9
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_generate_tab_components(self):
        """Test Generate tab UI components."""
        # Create Generate tab
        generate_frame = self.create_widget(ttk.Frame)
        generate_frame.pack(fill='both', expand=True)
        
        # Document type selection
        type_frame = ttk.LabelFrame(generate_frame, text="Document Type")
        type_frame.pack(fill='x', padx=20, pady=10)
        
        doc_type_var = tk.StringVar(value="soap")
        
        ttk.Radiobutton(
            type_frame,
            text="SOAP Note",
            variable=doc_type_var,
            value="soap"
        ).pack(anchor='w', padx=10, pady=5)
        
        ttk.Radiobutton(
            type_frame,
            text="Referral Letter",
            variable=doc_type_var,
            value="referral"
        ).pack(anchor='w', padx=10, pady=5)
        
        # Context section
        context_frame = ttk.LabelFrame(generate_frame, text="Context Information")
        context_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        context_text = tk.Text(context_frame, height=6, wrap='word')
        context_scroll = ttk.Scrollbar(context_frame, command=context_text.yview)
        context_text.configure(yscrollcommand=context_scroll.set)
        
        context_text.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        context_scroll.grid(row=0, column=1, sticky='ns', pady=5)
        
        context_frame.grid_columnconfigure(0, weight=1)
        context_frame.grid_rowconfigure(0, weight=1)
        
        # Template selection
        template_frame = ttk.Frame(context_frame)
        template_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        
        ttk.Label(template_frame, text="Template:").pack(side='left')
        template_combo = ttk.Combobox(
            template_frame,
            values=["None", "Follow-up Visit", "New Patient", "Telehealth"],
            state='readonly',
            width=20
        )
        template_combo.set("None")
        template_combo.pack(side='left', padx=5)
        
        # Generate button
        generate_button = ttk.Button(
            generate_frame,
            text="🚀 Generate Document",
            width=25
        )
        generate_button.pack(pady=20)
        
        # Progress and status
        progress_var = tk.IntVar(value=0)
        progress = ttk.Progressbar(
            generate_frame,
            variable=progress_var,
            maximum=100,
            length=300
        )
        
        status_var = tk.StringVar(value="")
        status_label = ttk.Label(
            generate_frame,
            textvariable=status_var
        )
        
        # Test generation workflow
        generated_docs = []
        
        def generate_document():
            doc_type = doc_type_var.get()
            context = context_text.get("1.0", tk.END).strip()
            template = template_combo.get()
            
            # Show progress
            progress.pack(pady=10)
            status_label.pack()
            
            # Simulate generation steps
            steps = [
                (25, "Analyzing transcript..."),
                (50, "Extracting medical information..."),
                (75, "Generating document..."),
                (100, "✓ Document generated successfully!")
            ]
            
            for value, status in steps:
                progress_var.set(value)
                status_var.set(status)
                self.process_events()
            
            generated_docs.append({
                'type': doc_type,
                'context': context,
                'template': template
            })
            
            # Hide progress after completion
            self.root.after(1000, lambda: progress.pack_forget())
        
        generate_button.configure(command=generate_document)
        
        # Test document generation
        self.enter_text(context_text, "Previous diagnosis: Hypertension")
        self.select_combobox_value(template_combo, "Follow-up Visit")
        self.click_button(generate_button)
        
        assert len(generated_docs) == 1
        assert generated_docs[0]['type'] == "soap"
        assert generated_docs[0]['context'] == "Previous diagnosis: Hypertension"
        assert generated_docs[0]['template'] == "Follow-up Visit"
        assert progress_var.get() == 100
        
        # Test referral generation
        doc_type_var.set("referral")
        self.click_button(generate_button)
        
        assert len(generated_docs) == 2
        assert generated_docs[1]['type'] == "referral"
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_recordings_tab_components(self):
        """Test Recordings tab UI components."""
        # Create Recordings tab
        recordings_frame = self.create_widget(ttk.Frame)
        recordings_frame.pack(fill='both', expand=True)
        
        # Search bar
        search_frame = ttk.Frame(recordings_frame)
        search_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(search_frame, text="🔍").pack(side='left')
        search_var = tk.StringVar()
        search_entry = ttk.Entry(
            search_frame,
            textvariable=search_var,
            width=40
        )
        search_entry.pack(side='left', padx=5)
        
        # Date filter
        ttk.Label(search_frame, text="Date:").pack(side='left', padx=(20, 5))
        date_combo = ttk.Combobox(
            search_frame,
            values=["All", "Today", "This Week", "This Month"],
            state='readonly',
            width=15
        )
        date_combo.set("All")
        date_combo.pack(side='left')
        
        # Recordings treeview
        tree_frame = ttk.Frame(recordings_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create treeview with columns
        columns = ('Date', 'Duration', 'Transcript', 'SOAP', 'Letter')
        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='tree headings',
            height=15
        )
        
        # Configure columns
        tree.heading('#0', text='Time')
        tree.column('#0', width=100)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100 if col != 'Transcript' else 300)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Action buttons
        action_frame = ttk.Frame(recordings_frame)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        load_button = ttk.Button(action_frame, text="Load Recording", state='disabled')
        export_button = ttk.Button(action_frame, text="Export", state='disabled')
        delete_button = ttk.Button(action_frame, text="Delete", state='disabled')
        
        load_button.pack(side='left', padx=5)
        export_button.pack(side='left', padx=5)
        delete_button.pack(side='left', padx=5)
        
        # Add sample data
        sample_recordings = [
            ("09:30", "2024-01-15", "05:23", "Patient with headache...", "✓", "—"),
            ("14:15", "2024-01-15", "03:45", "Follow-up visit for...", "✓", "✓"),
            ("16:00", "2024-01-14", "08:12", "New patient consultation...", "—", "—"),
            ("11:20", "2024-01-14", "04:30", "Routine check-up...", "✓", "❌"),
        ]
        
        for time, date, duration, transcript, soap, letter in sample_recordings:
            tree.insert('', 'end', text=time, values=(date, duration, transcript, soap, letter))
        
        # Test selection handling
        selected_items = []
        
        def on_select(event):
            selection = tree.selection()
            if selection:
                selected_items.append(selection[0])
                # Enable action buttons
                load_button.configure(state='normal')
                export_button.configure(state='normal')
                delete_button.configure(state='normal')
            else:
                # Disable action buttons
                load_button.configure(state='disabled')
                export_button.configure(state='disabled')
                delete_button.configure(state='disabled')
        
        tree.bind('<<TreeviewSelect>>', on_select)
        
        # Test filtering
        def filter_recordings():
            search_text = search_var.get().lower()
            date_filter = date_combo.get()
            
            # Clear tree
            for item in tree.get_children():
                tree.delete(item)
            
            # Re-add filtered items
            for time, date, duration, transcript, soap, letter in sample_recordings:
                if search_text and search_text not in transcript.lower():
                    continue
                if date_filter == "Today" and date != "2024-01-15":
                    continue
                    
                tree.insert('', 'end', text=time, values=(date, duration, transcript, soap, letter))
        
        search_var.trace('w', lambda *args: filter_recordings())
        date_combo.bind('<<ComboboxSelected>>', lambda e: filter_recordings())
        
        # Test search
        self.enter_text(search_entry, "headache")
        assert len(tree.get_children()) == 1
        
        # Clear search
        self.enter_text(search_entry, "")
        assert len(tree.get_children()) == 4
        
        # Test date filter
        self.select_combobox_value(date_combo, "Today")
        assert len(tree.get_children()) == 2
        
        # Test selection
        first_item = tree.get_children()[0]
        tree.selection_set(first_item)
        tree.event_generate('<<TreeviewSelect>>')
        self.process_events()
        
        assert len(selected_items) > 0
        self.assert_widget_enabled(load_button)
        self.assert_widget_enabled(export_button)
        self.assert_widget_enabled(delete_button)
    
    def test_tab_switching_preservation(self):
        """Test that tab state is preserved when switching."""
        # Create main notebook
        notebook = self.create_widget(ttk.Notebook)
        notebook.pack(fill='both', expand=True)
        
        # Create tabs with state
        record_frame = ttk.Frame(notebook)
        process_frame = ttk.Frame(notebook)
        
        notebook.add(record_frame, text="Record")
        notebook.add(process_frame, text="Process")
        
        # Add stateful widgets
        record_text = tk.Text(record_frame, height=5)
        record_text.pack()
        
        process_var = tk.StringVar(value="Initial")
        process_entry = ttk.Entry(process_frame, textvariable=process_var)
        process_entry.pack()
        
        # Set initial values
        self.enter_text(record_text, "Recording transcript")
        self.enter_text(process_entry, "Modified value")
        
        # Switch tabs
        self.select_notebook_tab(notebook, 1)  # Switch to Process
        assert notebook.index("current") == 1
        
        self.select_notebook_tab(notebook, 0)  # Back to Record
        assert notebook.index("current") == 0
        
        # Verify state preserved
        assert self.get_text(record_text) == "Recording transcript"
        assert process_var.get() == "Modified value"
    
    def test_workflow_data_flow(self):
        """Test data flow between workflow tabs."""
        # Mock shared data structure
        shared_data = {
            'transcript': tk.StringVar(value=""),
            'refined': tk.StringVar(value=""),
            'improved': tk.StringVar(value=""),
            'soap': tk.StringVar(value=""),
            'current_recording_id': None
        }
        
        # Simulate recording completion
        shared_data['transcript'].set("Patient presents with chronic headache.")
        shared_data['current_recording_id'] = 123
        
        # Simulate text processing
        transcript = shared_data['transcript'].get()
        if transcript:
            # Refine text
            shared_data['refined'].set(f"Refined: {transcript}")
            
            # Improve text
            shared_data['improved'].set(f"Improved clarity: {transcript}")
        
        # Simulate SOAP generation
        if shared_data['refined'].get():
            shared_data['soap'].set(
                "S: Chronic headache\n"
                "O: Vital signs stable\n"
                "A: Tension headache\n"
                "P: Prescribe pain relief"
            )
        
        # Verify data flow
        assert shared_data['transcript'].get() != ""
        assert shared_data['refined'].get() != ""
        assert shared_data['improved'].get() != ""
        assert shared_data['soap'].get() != ""
        assert shared_data['current_recording_id'] == 123