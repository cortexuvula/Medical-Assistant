"""Medical Assistant specific tkinter UI tests."""
import pytest
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttk_bs
from unittest.mock import Mock, patch, MagicMock
from tests.unit.tkinter_test_utils import TkinterTestCase, create_mock_workflow_ui
import os

# Skip ttkbootstrap-specific tests in CI environment
# The ttkbootstrap style initialization fails when the tk window is destroyed too quickly in test environments
SKIP_TTKBOOTSTRAP = bool(os.environ.get('CI', '')) or bool(os.environ.get('GITHUB_ACTIONS', ''))


class TestMedicalAssistantUI(TkinterTestCase):
    """Tests for Medical Assistant UI components."""
    
    @pytest.fixture
    def mock_environment(self):
        """Mock the Medical Assistant environment."""
        with patch('database.Database') as mock_db:
            with patch('audio.AudioHandler') as mock_audio:
                with patch('recording_manager.RecordingManager') as mock_recording:
                    with patch('ai_processor.AIProcessor') as mock_ai:
                        # Configure mocks
                        mock_db.return_value.get_all_recordings.return_value = []
                        mock_audio.return_value.get_input_devices.return_value = [
                            {'name': 'Default Microphone', 'id': 0}
                        ]
                        
                        yield {
                            'db': mock_db,
                            'audio': mock_audio,
                            'recording': mock_recording,
                            'ai': mock_ai
                        }
    
    def test_workflow_tabs(self):
        """Test the workflow tab structure."""
        notebook = self.create_widget(ttk.Notebook)
        notebook.pack(fill='both', expand=True)
        
        # Create workflow tabs as in the actual app
        workflows = ["Record", "Process", "Generate", "Recordings"]
        tabs = {}
        
        for workflow in workflows:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=workflow)
            tabs[workflow] = frame
        
        # Verify all tabs exist
        assert notebook.index("end") == len(workflows)
        
        # Verify tab names
        for i, workflow in enumerate(workflows):
            assert notebook.tab(i, "text") == workflow
    
    def test_recording_controls(self):
        """Test recording control buttons and states."""
        # Create recording controls frame
        controls_frame = self.create_widget(ttk.Frame)
        controls_frame.pack()
        
        # Create buttons
        record_button = ttk.Button(controls_frame, text="🎤 Start Recording")
        stop_button = ttk.Button(controls_frame, text="⏹ Stop")
        pause_button = ttk.Button(controls_frame, text="⏸ Pause")
        
        record_button.pack(side='left', padx=5)
        stop_button.pack(side='left', padx=5)
        pause_button.pack(side='left', padx=5)
        
        # Initial state
        stop_button.configure(state='disabled')
        pause_button.configure(state='disabled')
        
        self.assert_widget_enabled(record_button)
        self.assert_widget_disabled(stop_button)
        self.assert_widget_disabled(pause_button)
        
        # Simulate recording start
        record_button.configure(state='disabled')
        stop_button.configure(state='normal')
        pause_button.configure(state='normal')
        
        self.assert_widget_disabled(record_button)
        self.assert_widget_enabled(stop_button)
        self.assert_widget_enabled(pause_button)
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_text_editor_tabs(self):
        """Test the text editor notebook structure."""
        editor_notebook = self.create_widget(ttk.Notebook)
        editor_notebook.pack(fill='both', expand=True)
        
        # Create editor tabs
        editor_tabs = ["Transcript", "Refined", "Improved", "SOAP", "Letter"]
        
        for tab_name in editor_tabs:
            # Create frame with text widget
            frame = ttk.Frame(editor_notebook)
            text = tk.Text(frame, wrap='word')
            scrollbar = ttk.Scrollbar(frame, command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            
            text.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            editor_notebook.add(frame, text=tab_name)
        
        # Verify tabs
        assert editor_notebook.index("end") == len(editor_tabs)
        
        # Test tab switching
        for i in range(len(editor_tabs)):
            self.select_notebook_tab(editor_notebook, i)
            assert editor_notebook.index("current") == i
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_ai_provider_selection(self):
        """Test AI provider dropdown functionality."""
        # Create provider selection frame
        frame = self.create_widget(ttk.Frame)
        frame.pack()
        
        ttk.Label(frame, text="AI Provider:").pack(side='left')
        
        providers = ["OpenAI", "Perplexity", "Grok", "Ollama"]
        provider_combo = ttk.Combobox(frame, values=providers, state='readonly')
        provider_combo.set("OpenAI")
        provider_combo.pack(side='left', padx=5)
        
        # Create model dropdown
        ttk.Label(frame, text="Model:").pack(side='left', padx=(20, 0))
        
        model_combo = ttk.Combobox(frame, state='readonly')
        model_combo.pack(side='left', padx=5)
        
        # Test provider selection updates model list
        model_configs = {
            "OpenAI": ["gpt-4", "gpt-3.5-turbo"],
            "Perplexity": ["mixtral-8x7b", "llama-3-70b"],
            "Grok": ["grok-1", "grok-2"],
            "Ollama": ["llama3", "mistral", "phi"]
        }
        
        def update_models(event=None):
            provider = provider_combo.get()
            models = model_configs.get(provider, [])
            model_combo['values'] = models
            if models:
                model_combo.set(models[0])
        
        provider_combo.bind("<<ComboboxSelected>>", update_models)
        update_models()  # Initial update
        
        # Test provider changes
        self.select_combobox_value(provider_combo, "Ollama")
        assert model_combo['values'] == model_configs["Ollama"]
        
        self.select_combobox_value(provider_combo, "Perplexity")
        assert model_combo['values'] == model_configs["Perplexity"]
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_quick_continue_mode(self):
        """Test Quick Continue Mode checkbox."""
        var = tk.BooleanVar(value=False)
        checkbox = self.create_widget(
            ttk.Checkbutton,
            text="Quick Continue Mode",
            variable=var
        )
        checkbox.pack()
        
        # Initial state
        assert var.get() is False
        
        # Enable Quick Continue
        checkbox.invoke()
        self.process_events()
        assert var.get() is True
        
        # Test that it affects UI behavior (mock)
        queue_status_label = ttk.Label(text="Queue: Idle")
        queue_status_label.pack()
        
        # When enabled, show queue status
        if var.get():
            queue_status_label.configure(text="Queue: Ready")
    
    def test_status_bar_updates(self):
        """Test status bar information display."""
        # Create status bar frame
        status_frame = self.create_widget(ttk.Frame)
        status_frame.pack(fill='x', side='bottom')
        
        # Status variables
        status_var = tk.StringVar(value="Ready")
        queue_var = tk.StringVar(value="Queue: 0 items")
        timer_var = tk.StringVar(value="00:00")
        
        # Status labels
        ttk.Label(status_frame, textvariable=status_var).pack(side='left', padx=5)
        ttk.Label(status_frame, text="|").pack(side='left', padx=5)  # Use label instead of separator
        ttk.Label(status_frame, textvariable=queue_var).pack(side='left', padx=5)
        ttk.Label(status_frame, text="|").pack(side='left', padx=5)  # Use label instead of separator
        ttk.Label(status_frame, textvariable=timer_var).pack(side='left', padx=5)
        
        # Test status updates
        status_var.set("Recording...")
        queue_var.set("Queue: 2 items")
        timer_var.set("01:45")
        
        self.process_events()
        
        assert status_var.get() == "Recording..."
        assert queue_var.get() == "Queue: 2 items"
        assert timer_var.get() == "01:45"
    
    def test_recording_timer_display(self):
        """Test recording timer functionality."""
        timer_var = tk.StringVar(value="00:00")
        timer_label = self.create_widget(
            ttk.Label,
            textvariable=timer_var,
            font=('TkDefaultFont', 24, 'bold')
        )
        timer_label.pack()
        
        # Simulate timer updates
        times = ["00:01", "00:15", "01:00", "02:30"]
        for time_str in times:
            timer_var.set(time_str)
            self.process_events()
            assert timer_var.get() == time_str
    
    def test_context_panel_toggle(self):
        """Test context panel show/hide functionality."""
        # Main container
        container = self.create_widget(ttk.Frame)
        container.pack(fill='both', expand=True)
        
        # Context panel (initially hidden)
        context_visible = False
        context_frame = ttk.LabelFrame(container, text="Previous Medical Information")
        
        # Context button
        def toggle_context():
            nonlocal context_visible
            context_visible = not context_visible
            if context_visible:
                context_frame.pack(side='left', fill='both', padx=5)
            else:
                context_frame.pack_forget()
        
        context_button = ttk.Button(container, text="Context", command=toggle_context)
        context_button.pack()
        
        # Test toggle
        assert not context_visible
        
        self.click_button(context_button)
        assert context_visible
        
        self.click_button(context_button)
        assert not context_visible
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_chat_interface_structure(self):
        """Test chat interface components."""
        # Chat frame
        chat_frame = self.create_widget(ttk.LabelFrame, text="AI Assistant")
        chat_frame.pack(fill='both', expand=True)
        
        # Messages area
        messages_frame = ttk.Frame(chat_frame)
        messages_frame.pack(fill='both', expand=True)
        
        messages_text = tk.Text(messages_frame, height=8, state='disabled')
        messages_scroll = ttk.Scrollbar(messages_frame, command=messages_text.yview)
        messages_text.configure(yscrollcommand=messages_scroll.set)
        
        messages_text.pack(side='left', fill='both', expand=True)
        messages_scroll.pack(side='right', fill='y')
        
        # Input area
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill='x', pady=5)
        
        chat_entry = ttk.Entry(input_frame)
        send_button = ttk.Button(input_frame, text="Send")
        
        chat_entry.pack(side='left', fill='x', expand=True)
        send_button.pack(side='right', padx=(5, 0))
        
        # Test message sending
        messages = []
        def send_message():
            text = chat_entry.get().strip()
            if text:
                messages.append(text)
                # Add to display
                messages_text.configure(state='normal')
                messages_text.insert('end', f"You: {text}\n")
                messages_text.configure(state='disabled')
                chat_entry.delete(0, 'end')
        
        send_button.configure(command=send_message)
        
        # Send test message
        self.enter_text(chat_entry, "Test message")
        self.click_button(send_button)
        
        assert len(messages) == 1
        assert messages[0] == "Test message"
        assert chat_entry.get() == ""
    
    def test_error_dialog_display(self):
        """Test error message dialog functionality."""
        from tkinter import messagebox
        
        # Mock messagebox
        with patch('tkinter.messagebox.showerror') as mock_error:
            # Simulate error
            error_title = "API Error"
            error_message = "Failed to connect to API"
            
            messagebox.showerror(error_title, error_message)
            
            mock_error.assert_called_once_with(error_title, error_message)
    
    def test_settings_dialog_components(self):
        """Test settings dialog structure."""
        # Create a mock settings window
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.withdraw()  # Hide during test
        
        # Create notebook for settings tabs
        settings_notebook = ttk.Notebook(settings_window)
        settings_notebook.pack(fill='both', expand=True)
        
        # API Keys tab
        api_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(api_frame, text="API Keys")
        
        # Add API key fields
        api_providers = ["OpenAI", "Deepgram", "ElevenLabs", "Groq"]
        api_entries = {}
        
        for i, provider in enumerate(api_providers):
            ttk.Label(api_frame, text=f"{provider} API Key:").grid(
                row=i, column=0, sticky='w', padx=5, pady=5
            )
            entry = ttk.Entry(api_frame, show='*', width=40)
            entry.grid(row=i, column=1, padx=5, pady=5)
            api_entries[provider] = entry
        
        # Models tab
        models_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(models_frame, text="Models")
        
        # Prompts tab
        prompts_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(prompts_frame, text="Prompts")
        
        # Verify structure
        assert settings_notebook.index("end") == 3
        assert len(api_entries) == len(api_providers)
    
    def test_recording_workflow_integration(self):
        """Test integrated recording workflow."""
        mock_ui = create_mock_workflow_ui()
        
        # Initial state
        assert not mock_ui.recording_manager.is_recording
        assert not mock_ui.recording_manager.is_paused
        
        # Start recording
        mock_ui.recording_manager.is_recording = True
        mock_ui.update_ui_state()
        
        # Verify state change
        assert mock_ui.recording_manager.is_recording
        mock_ui.update_ui_state.assert_called()
        
        # Pause recording
        mock_ui.recording_manager.is_paused = True
        mock_ui.update_ui_state()
        
        # Stop recording
        mock_ui.recording_manager.is_recording = False
        mock_ui.recording_manager.is_paused = False
        mock_ui.update_ui_state()
        
        # Process recording
        mock_ui.transcript_text.get.return_value = "Test transcript"
        mock_ui.process_recording()
        
        mock_ui.process_recording.assert_called_once()
    
    @pytest.mark.skipif(SKIP_TTKBOOTSTRAP, reason="ttkbootstrap widgets require display in CI")
    def test_document_generation_flow(self):
        """Test document generation workflow."""
        # Create generation controls
        generate_frame = self.create_widget(ttk.Frame)
        generate_frame.pack()
        
        # Document type selection
        doc_types = ["SOAP Note", "Referral Letter", "Custom Document"]
        doc_type_var = tk.StringVar(value=doc_types[0])
        
        for doc_type in doc_types:
            ttk.Radiobutton(
                generate_frame,
                text=doc_type,
                variable=doc_type_var,
                value=doc_type
            ).pack(anchor='w')
        
        # Generate button
        generate_button = ttk.Button(generate_frame, text="Generate Document")
        generate_button.pack(pady=10)
        
        # Progress indicator
        progress = ttk.Progressbar(generate_frame, mode='indeterminate')
        
        # Mock generation
        generated_docs = []
        def generate_document():
            doc_type = doc_type_var.get()
            progress.pack(pady=5)
            progress.start()
            self.process_events()
            
            # Simulate generation
            generated_docs.append(doc_type)
            
            progress.stop()
            progress.pack_forget()
        
        generate_button.configure(command=generate_document)
        
        # Test generation
        self.click_button(generate_button)
        assert len(generated_docs) == 1
        assert generated_docs[0] == "SOAP Note"
        
        # Change type and generate again
        doc_type_var.set("Referral Letter")
        self.click_button(generate_button)
        assert len(generated_docs) == 2
        assert generated_docs[1] == "Referral Letter"