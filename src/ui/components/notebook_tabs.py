"""
Notebook Tabs Component for Medical Assistant
Handles the main text editor notebook with tabs
"""

import threading
import tkinter as tk
import ttkbootstrap as ttk
from utils.structured_logging import get_logger

from ui.tooltip import ToolTip

logger = get_logger(__name__)
from ui.ui_constants import Icons, SidebarConfig, Fonts
from settings.settings import SETTINGS, save_settings


class NotebookTabs:
    """Manages the notebook tabs UI components."""
    
    def __init__(self, parent_ui):
        """Initialize the NotebookTabs component.
        
        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components
        
    def create_notebook(self) -> tuple:
        """Create the notebook with tabs for transcript, soap note, referral, letter, chat, and RAG.

        Note: Tab headers are hidden by clipping the tab bar above the visible area,
        since sidebar navigation provides access to each section.
        The SOAP tab has a special split layout with medication and differential analysis panels.

        Returns:
            tuple: (notebook_container, notebook, transcript_text, soap_text, referral_text,
                    letter_text, chat_text, rag_text, context_text,
                    medication_analysis_text, differential_analysis_text)
        """
        # Create a container frame that will clip the notebook's tab bar.
        # The notebook is placed inside with a negative y-offset so the tab
        # bar is pushed above the container's visible area.
        notebook_container = ttk.Frame(self.parent)

        notebook = ttk.Notebook(notebook_container)
        self._notebook = notebook  # Store actual notebook reference
        
        # Create tabs
        tabs = [
            ("Transcript", "transcript"),
            ("SOAP Note", "soap"),
            ("Referral", "referral"),
            ("Letter", "letter"),
            ("Chat", "chat"),
            ("RAG", "rag")
        ]
        
        text_widgets = {}

        for tab_name, widget_key in tabs:
            # Create frame for each tab
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=tab_name)

            # Special handling for SOAP tab - split into paned layout
            if widget_key == "soap":
                text_widget = self._create_soap_split_layout(frame, text_widgets)
            elif widget_key == "chat":
                # Chat tab: buttons first, then text widget
                button_frame = ttk.Frame(frame)
                button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

                clear_chat_btn = ttk.Button(
                    button_frame,
                    text="Clear Chat History",
                    command=lambda: self._clear_chat_history(),
                    bootstyle="secondary"
                )
                clear_chat_btn.pack(side=tk.RIGHT, padx=5)
                self.components['clear_chat_button'] = clear_chat_btn

                # Now create text widget
                text_scroll = ttk.Scrollbar(frame)
                text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
                text_widget = tk.Text(
                    frame,
                    wrap=tk.WORD,
                    yscrollcommand=text_scroll.set,
                    undo=True,
                    autoseparators=True
                )
                text_widget.pack(fill=tk.BOTH, expand=True)
                text_scroll.config(command=text_widget.yview)

                text_widget.insert("1.0", "Welcome to the Medical Assistant Chat!\n\n")
                text_widget.insert("end", "This is your ChatGPT-style interface where you can:\n")
                text_widget.insert("end", "• Ask medical questions\n")
                text_widget.insert("end", "• Get explanations about medical terms\n")
                text_widget.insert("end", "• Have conversations about healthcare topics\n")
                text_widget.insert("end", "• Clear the chat with 'clear chat' command\n\n")
                text_widget.insert("end", "Type your message in the AI Assistant chat box below to start chatting with the AI!\n")
                text_widget.insert("end", "="*50 + "\n\n")

                text_widget.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                text_widget.tag_add("welcome", "1.0", "end")
                text_widget.bind("<Key>", lambda e: "break" if e.keysym not in ["Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End"] else None)

            elif widget_key == "rag":
                # RAG tab: buttons first, then text widget
                button_frame = ttk.Frame(frame)
                button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

                # Left side buttons: Upload and Document Library
                left_buttons = ttk.Frame(button_frame)
                left_buttons.pack(side=tk.LEFT)

                upload_btn = ttk.Button(
                    left_buttons,
                    text="Upload Documents",
                    command=lambda: self._show_rag_upload_dialog(),
                    bootstyle="success"
                )
                upload_btn.pack(side=tk.LEFT, padx=(0, 5))
                self.components['rag_upload_button'] = upload_btn

                library_btn = ttk.Button(
                    left_buttons,
                    text="Document Library",
                    command=lambda: self._show_rag_library_dialog(),
                    bootstyle="info"
                )
                library_btn.pack(side=tk.LEFT, padx=(0, 5))
                self.components['rag_library_button'] = library_btn

                # Knowledge Graph button
                graph_btn = ttk.Button(
                    left_buttons,
                    text="Knowledge Graph",
                    command=lambda: self._show_knowledge_graph_dialog(),
                    bootstyle="warning"
                )
                graph_btn.pack(side=tk.LEFT, padx=(0, 5))
                self.components['rag_graph_button'] = graph_btn

                # Export menubutton
                export_btn = ttk.Menubutton(
                    left_buttons,
                    text="Export",
                    bootstyle="info-outline"
                )
                export_menu = tk.Menu(export_btn, tearoff=0)
                export_menu.add_command(label="Export as PDF", command=lambda: self._export_rag_conversation("pdf"))
                export_menu.add_command(label="Export as Word", command=lambda: self._export_rag_conversation("docx"))
                export_menu.add_command(label="Export as Markdown", command=lambda: self._export_rag_conversation("md"))
                export_menu.add_command(label="Export as JSON", command=lambda: self._export_rag_conversation("json"))
                export_btn["menu"] = export_menu
                export_btn.pack(side=tk.LEFT, padx=(0, 5))
                self.components['rag_export_button'] = export_btn

                # Filters button
                filters_btn = ttk.Button(
                    left_buttons,
                    text="Filters",
                    command=lambda: self._toggle_rag_filters(),
                    bootstyle="secondary-outline"
                )
                filters_btn.pack(side=tk.LEFT, padx=(0, 5))
                self.components['rag_filters_button'] = filters_btn

                # Syntax Help button
                syntax_btn = ttk.Button(
                    left_buttons,
                    text="?",
                    width=3,
                    command=lambda: self._show_search_syntax_help(),
                    bootstyle="secondary-outline"
                )
                syntax_btn.pack(side=tk.LEFT, padx=(0, 5))
                self.components['rag_syntax_button'] = syntax_btn
                ToolTip(syntax_btn, "Advanced Search Syntax Help")

                # Document count label
                self.rag_doc_count_label = ttk.Label(
                    left_buttons,
                    text="",
                    foreground="gray"
                )
                self.rag_doc_count_label.pack(side=tk.LEFT, padx=(10, 0))
                self._update_rag_document_count()

                # Right side: Cancel button (hidden by default) and Clear history button
                right_buttons = ttk.Frame(button_frame)
                right_buttons.pack(side=tk.RIGHT)

                # Cancel button for in-progress queries
                cancel_rag_btn = ttk.Button(
                    right_buttons,
                    text="Cancel Search",
                    command=lambda: self._cancel_rag_query(),
                    bootstyle="danger"
                )
                # Hidden by default, shown during searches
                self.components['cancel_rag_button'] = cancel_rag_btn

                clear_rag_btn = ttk.Button(
                    right_buttons,
                    text="Clear RAG History",
                    command=lambda: self._clear_rag_history(),
                    bootstyle="secondary"
                )
                clear_rag_btn.pack(side=tk.RIGHT, padx=5)
                self.components['clear_rag_button'] = clear_rag_btn

                # Create filters panel frame (initially hidden)
                filters_frame = ttk.Frame(frame)
                self.components['rag_filters_frame'] = filters_frame
                self._rag_filters_visible = False

                # Initialize filters panel (lazy loaded)
                self._rag_filters_panel = None

                # Now create text widget
                text_scroll = ttk.Scrollbar(frame)
                text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
                text_widget = tk.Text(
                    frame,
                    wrap=tk.WORD,
                    yscrollcommand=text_scroll.set,
                    undo=True,
                    autoseparators=True
                )
                text_widget.pack(fill=tk.BOTH, expand=True)
                text_scroll.config(command=text_widget.yview)

                # Initialize source highlighter for this text widget
                try:
                    from ui.components.source_highlighter import SourceHighlighter, SourceLegend
                    self._rag_source_highlighter = SourceHighlighter(text_widget)
                    # Create source legend frame
                    legend_frame = ttk.Frame(frame)
                    self._rag_source_legend = SourceLegend(legend_frame)
                    self.components['rag_legend_frame'] = legend_frame
                except Exception as e:
                    logger.debug(f"Could not initialize source highlighter: {e}")
                    self._rag_source_highlighter = None
                    self._rag_source_legend = None

                text_widget.insert("1.0", "Welcome to the RAG Document Search!\n\n")
                text_widget.insert("end", "This interface allows you to search your document database:\n")
                text_widget.insert("end", "• Upload documents using the 'Upload Documents' button above\n")
                text_widget.insert("end", "• View and manage documents in the 'Document Library'\n")
                text_widget.insert("end", "• Query your documents by typing questions below\n")
                text_widget.insert("end", "• Get relevant information from your knowledge base\n")
                text_widget.insert("end", "• Use advanced syntax: type:pdf, date:last-week, -exclude\n\n")
                text_widget.insert("end", "Type your question in the AI Assistant chat box below to search your documents!\n")
                text_widget.insert("end", "="*50 + "\n\n")

                text_widget.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                text_widget.tag_add("welcome", "1.0", "end")
                text_widget.bind("<Key>", lambda e: "break" if e.keysym not in ["Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End"] else None)
            else:
                # Standard layout for other tabs
                text_scroll = ttk.Scrollbar(frame)
                text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

                text_widget = tk.Text(
                    frame,
                    wrap=tk.WORD,
                    yscrollcommand=text_scroll.set,
                    undo=True,
                    autoseparators=True
                )
                text_widget.pack(fill=tk.BOTH, expand=True)
                text_scroll.config(command=text_widget.yview)

            # Store reference
            text_widgets[widget_key] = text_widget
            self.components[f'{widget_key}_text'] = text_widget

        # Hide the tab bar by placing the notebook with a negative y-offset
        # inside the container frame. The container clips anything above y=0,
        # effectively hiding the tab bar while keeping all tab content visible.
        TAB_HEIGHT = 30
        notebook.place(x=0, y=-TAB_HEIGHT, relwidth=1.0, relheight=1.0, height=TAB_HEIGHT)

        # Return in expected order (container for layout, notebook for tab operations)
        return (
            notebook_container,
            notebook,
            text_widgets["transcript"],
            text_widgets["soap"],
            text_widgets["referral"],
            text_widgets["letter"],
            text_widgets["chat"],
            text_widgets["rag"],
            None,  # No context text in notebook for workflow UI
            text_widgets.get("medication_analysis"),
            text_widgets.get("differential_analysis")
        )
    
    def _create_soap_split_layout(self, frame: ttk.Frame, text_widgets: dict) -> tk.Text:
        """Create the SOAP tab layout with analysis tabs below.

        Layout:
        ┌─────────────────────────────────────────────────────────────────┐
        │                     SOAP Note (~70%)                            │
        ├─────────────────────────────────────────────────────────────────┤
        │ [Medication Analysis] [Differential Dx]              [−]       │
        │  Analysis content with copy button...                          │
        └─────────────────────────────────────────────────────────────────┘

        Args:
            frame: Parent frame for the SOAP tab
            text_widgets: Dictionary to store additional widget references

        Returns:
            tk.Text: The main SOAP note text widget
        """
        # Create vertical paned window for top/bottom split
        soap_paned = ttk.Panedwindow(frame, orient=tk.VERTICAL)
        soap_paned.pack(fill=tk.BOTH, expand=True)

        # ===== TOP PANE: SOAP Note (70% height) =====
        top_frame = ttk.Frame(soap_paned)
        soap_paned.add(top_frame, weight=7)

        # SOAP note scrollbar
        soap_scroll = ttk.Scrollbar(top_frame)
        soap_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # SOAP note text widget (editable)
        soap_text = tk.Text(
            top_frame,
            wrap=tk.WORD,
            yscrollcommand=soap_scroll.set,
            undo=True,
            autoseparators=True
        )
        soap_text.pack(fill=tk.BOTH, expand=True)
        soap_scroll.config(command=soap_text.yview)

        # ===== BOTTOM PANE: Analysis Tabs (30% height) =====
        bottom_frame = ttk.Frame(soap_paned)
        soap_paned.add(bottom_frame, weight=3)

        # Store references for collapse functionality
        self.components['soap_paned'] = soap_paned
        self.components['analysis_bottom_frame'] = bottom_frame

        # Get initial collapse state from settings
        is_collapsed = SETTINGS.get("analysis_panel_collapsed", False)
        self._analysis_collapsed = is_collapsed

        # Header with collapse button on the left
        is_dark = SETTINGS.get("theme", "darkly") in ("darkly", "superhero", "cyborg", "vapor", "solar")
        sidebar_colors = SidebarConfig.get_sidebar_colors(is_dark)

        header_frame = tk.Frame(bottom_frame, bg=sidebar_colors["bg"])
        header_frame.pack(fill=tk.X, padx=2, pady=2)

        # Collapse button first (on the left) — use tk.Label for clean minimal look
        # Icon shows the ACTION: when collapsed show expand icon (▼), when expanded show collapse icon (▲)
        initial_icon = Icons.EXPAND if is_collapsed else Icons.COLLAPSE
        collapse_btn = tk.Label(
            header_frame,
            text=initial_icon,
            font=(Fonts.FAMILY[0], 14),
            bg=sidebar_colors["bg"],
            fg=sidebar_colors["fg"],
            cursor="hand2",
        )
        collapse_btn.pack(side=tk.LEFT, padx=5)
        collapse_btn.bind("<Button-1>", lambda e: self._toggle_analysis_panel())
        self.components['analysis_collapse_btn'] = collapse_btn

        # Then the label
        header_label = tk.Label(
            header_frame,
            text="Analysis",
            font=(Fonts.FAMILY[0], 11, "bold"),
            bg=sidebar_colors["bg"],
            fg=sidebar_colors["fg"],
        )
        header_label.pack(side=tk.LEFT, padx=5)

        # Analysis content frame
        analysis_content = ttk.Frame(bottom_frame)
        self.components['analysis_content'] = analysis_content

        # Add tooltip
        self._analysis_collapse_tooltip = ToolTip(
            collapse_btn,
            "Expand Analysis Panel" if is_collapsed else "Collapse Analysis Panel"
        )

        # Analysis content frame - pack if not collapsed
        if not is_collapsed:
            analysis_content.pack(fill=tk.BOTH, expand=True)
        else:
            # Schedule sash adjustment after widget is visible
            def adjust_collapsed_sash():
                try:
                    soap_paned.update_idletasks()
                    total_height = soap_paned.winfo_height()
                    if total_height > 50:  # Only adjust if widget is properly sized
                        collapsed_height = max(30, total_height - 30)
                        soap_paned.sashpos(0, collapsed_height)
                except Exception:
                    pass  # Widget might not be ready yet
            # Use after to let widget realize its size first
            self.parent.after(100, adjust_collapsed_sash)

        # Create notebook for analysis tabs
        analysis_notebook = ttk.Notebook(analysis_content)
        analysis_notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ----- Tab 1: Medication Analysis -----
        med_tab = ttk.Frame(analysis_notebook)
        analysis_notebook.add(med_tab, text="  Medication Analysis  ")

        # Medication header with copy button
        med_header = ttk.Frame(med_tab)
        med_header.pack(fill=tk.X, padx=5, pady=3)

        med_copy_btn = ttk.Button(
            med_header,
            text="Copy",
            bootstyle="info-outline",
            command=lambda: self._copy_to_clipboard(medication_analysis_text)
        )
        med_copy_btn.pack(side=tk.RIGHT, padx=2)

        # View Details button for full medication dialog
        med_view_btn = ttk.Button(
            med_header,
            text="View Details",
            bootstyle="success-outline",
            command=self._open_medication_details,
            state='disabled'  # Initially disabled until analysis is available
        )
        med_view_btn.pack(side=tk.RIGHT, padx=2)
        self.components['medication_view_details_btn'] = med_view_btn

        # Medication analysis scrollbar and text widget
        med_content = ttk.Frame(med_tab)
        med_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        med_scroll = ttk.Scrollbar(med_content)
        med_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        medication_analysis_text = tk.Text(
            med_content,
            wrap=tk.WORD,
            yscrollcommand=med_scroll.set,
            state='disabled',
            height=8
        )
        medication_analysis_text.pack(fill=tk.BOTH, expand=True)
        med_scroll.config(command=medication_analysis_text.yview)

        # Initial placeholder message
        medication_analysis_text.config(state='normal')
        medication_analysis_text.insert('1.0', "Medication analysis will appear here after SOAP note generation.")
        medication_analysis_text.config(state='disabled')

        # Store reference
        text_widgets['medication_analysis'] = medication_analysis_text
        self.components['medication_analysis_text'] = medication_analysis_text

        # ----- Tab 2: Differential Diagnosis -----
        diff_tab = ttk.Frame(analysis_notebook)
        analysis_notebook.add(diff_tab, text="  Differential Diagnosis  ")

        # Differential header with copy button
        diff_header = ttk.Frame(diff_tab)
        diff_header.pack(fill=tk.X, padx=5, pady=3)

        diff_copy_btn = ttk.Button(
            diff_header,
            text="Copy",
            bootstyle="info-outline",
            command=lambda: self._copy_to_clipboard(differential_analysis_text)
        )
        diff_copy_btn.pack(side=tk.RIGHT, padx=2)

        # View Details button for full diagnostic dialog
        diff_view_btn = ttk.Button(
            diff_header,
            text="View Details",
            bootstyle="success-outline",
            command=self._open_diagnostic_details,
            state='disabled'  # Initially disabled until analysis is available
        )
        diff_view_btn.pack(side=tk.RIGHT, padx=2)
        self.components['differential_view_details_btn'] = diff_view_btn

        # Differential analysis scrollbar and text widget
        diff_content = ttk.Frame(diff_tab)
        diff_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        diff_scroll = ttk.Scrollbar(diff_content)
        diff_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        differential_analysis_text = tk.Text(
            diff_content,
            wrap=tk.WORD,
            yscrollcommand=diff_scroll.set,
            state='disabled',
            height=8
        )
        differential_analysis_text.pack(fill=tk.BOTH, expand=True)
        diff_scroll.config(command=differential_analysis_text.yview)

        # Initial placeholder message
        differential_analysis_text.config(state='normal')
        differential_analysis_text.insert('1.0', "Differential diagnosis will appear here after SOAP note generation.")
        differential_analysis_text.config(state='disabled')

        # Store reference
        text_widgets['differential_analysis'] = differential_analysis_text
        self.components['differential_analysis_text'] = differential_analysis_text

        # ----- Tab 3: Clinical Guidelines Compliance -----
        compliance_tab = ttk.Frame(analysis_notebook)
        analysis_notebook.add(compliance_tab, text="  Clinical Guidelines  ")

        # Compliance header with copy button
        compliance_header = ttk.Frame(compliance_tab)
        compliance_header.pack(fill=tk.X, padx=5, pady=3)

        compliance_copy_btn = ttk.Button(
            compliance_header,
            text="Copy",
            bootstyle="info-outline",
            command=lambda: self._copy_to_clipboard(compliance_analysis_text)
        )
        compliance_copy_btn.pack(side=tk.RIGHT, padx=2)

        # View Details button for full compliance dialog
        compliance_view_btn = ttk.Button(
            compliance_header,
            text="View Details",
            bootstyle="success-outline",
            command=self._open_compliance_details,
            state='disabled'  # Initially disabled until analysis is available
        )
        compliance_view_btn.pack(side=tk.RIGHT, padx=2)
        self.components['compliance_view_details_btn'] = compliance_view_btn

        # Upload Guidelines button
        upload_guidelines_btn = ttk.Button(
            compliance_header,
            text="Upload Guidelines",
            bootstyle="warning-outline",
            command=self._show_guidelines_upload_dialog
        )
        upload_guidelines_btn.pack(side=tk.LEFT, padx=2)
        self.components['upload_guidelines_btn'] = upload_guidelines_btn

        # Compliance analysis scrollbar and text widget
        compliance_content = ttk.Frame(compliance_tab)
        compliance_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        compliance_scroll = ttk.Scrollbar(compliance_content)
        compliance_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        compliance_analysis_text = tk.Text(
            compliance_content,
            wrap=tk.WORD,
            yscrollcommand=compliance_scroll.set,
            state='disabled',
            height=8
        )
        compliance_analysis_text.pack(fill=tk.BOTH, expand=True)
        compliance_scroll.config(command=compliance_analysis_text.yview)

        # Initial placeholder message
        compliance_analysis_text.config(state='normal')
        compliance_analysis_text.insert('1.0', "Clinical guidelines compliance will appear here after SOAP note generation.\n\n"
                                        "Use the 'Upload Guidelines' button to add clinical guidelines to the database.")
        compliance_analysis_text.config(state='disabled')

        # Store reference
        text_widgets['compliance_analysis'] = compliance_analysis_text
        self.components['compliance_analysis_text'] = compliance_analysis_text

        return soap_text

    def _copy_to_clipboard(self, text_widget: tk.Text) -> None:
        """Copy text widget content to clipboard.

        Args:
            text_widget: The text widget to copy from
        """
        try:
            content = text_widget.get('1.0', 'end-1c')
            self.parent.clipboard_clear()
            self.parent.clipboard_append(content)
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.success("Copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to copy")

    def _toggle_analysis_panel(self) -> None:
        """Toggle collapse/expand state of the Analysis panel.

        When collapsed, the analysis content is hidden and only the header remains visible.
        The SOAP note editor expands to fill the available space by adjusting the PanedWindow sash.
        """
        self._analysis_collapsed = not self._analysis_collapsed

        # Save state to settings
        SETTINGS["analysis_panel_collapsed"] = self._analysis_collapsed
        save_settings(SETTINGS)

        # Get references
        analysis_content = self.components.get('analysis_content')
        collapse_btn = self.components.get('analysis_collapse_btn')
        soap_paned = self.components.get('soap_paned')
        bottom_frame = self.components.get('analysis_bottom_frame')

        if not analysis_content or not collapse_btn or not soap_paned:
            return

        if self._analysis_collapsed:
            # Collapse: hide the analysis content and move sash to bottom
            analysis_content.pack_forget()
            # Show expand icon (▼) when collapsed - indicates "click to expand"
            collapse_btn.config(text=Icons.EXPAND)
            if hasattr(self, '_analysis_collapse_tooltip') and self._analysis_collapse_tooltip:
                self._analysis_collapse_tooltip.text = "Expand Analysis Panel"

            # Save current sash position before collapsing (for later restoration)
            soap_paned.update_idletasks()
            try:
                current_sash = soap_paned.sashpos(0)
                self._saved_sash_position = current_sash
            except Exception:
                self._saved_sash_position = None

            # Move sash to nearly the bottom (leave room for header only ~30px)
            soap_paned.update_idletasks()
            try:
                total_height = soap_paned.winfo_height()
                # Leave just enough room for the header (approximately 30 pixels)
                collapsed_height = max(30, total_height - 30)
                soap_paned.sashpos(0, collapsed_height)
            except Exception as e:
                logger.debug(f"Could not set sash position: {e}")
        else:
            # Expand: show the analysis content and restore sash position
            analysis_content.pack(fill=tk.BOTH, expand=True)
            # Show collapse icon (▲) when expanded - indicates "click to collapse"
            collapse_btn.config(text=Icons.COLLAPSE)
            if hasattr(self, '_analysis_collapse_tooltip') and self._analysis_collapse_tooltip:
                self._analysis_collapse_tooltip.text = "Collapse Analysis Panel"

            # Restore sash to previous position or default 70/30 split
            soap_paned.update_idletasks()
            try:
                total_height = soap_paned.winfo_height()
                if hasattr(self, '_saved_sash_position') and self._saved_sash_position:
                    # Restore saved position
                    soap_paned.sashpos(0, self._saved_sash_position)
                else:
                    # Default to 70% for SOAP note
                    default_sash = int(total_height * 0.7)
                    soap_paned.sashpos(0, default_sash)
            except Exception as e:
                logger.debug(f"Could not restore sash position: {e}")

    def _clear_chat_history(self):
        """Clear the chat conversation history."""
        try:
            # Clear the chat processor history
            if hasattr(self.parent, 'chat_processor') and self.parent.chat_processor:
                self.parent.chat_processor.clear_history()
            
            # Clear the chat text widget
            if 'chat_text' in self.components:
                chat_text = self.components['chat_text']
                chat_text.config(state=tk.NORMAL)
                chat_text.delete("1.0", tk.END)
                
                # Re-add welcome message
                chat_text.insert("1.0", "Welcome to the Medical Assistant Chat!\n\n")
                chat_text.insert("end", "This is your ChatGPT-style interface where you can:\n")
                chat_text.insert("end", "• Have free-form conversations about medical topics\n")
                chat_text.insert("end", "• Get help with medical documentation\n")
                chat_text.insert("end", "• Ask questions about your recordings and notes\n")
                chat_text.insert("end", "• Request analysis and suggestions\n\n")
                chat_text.insert("end", "Type your message in the AI Assistant chat box below!\n")
                chat_text.insert("end", "="*50 + "\n\n")
                
                # Configure initial styling
                chat_text.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                chat_text.tag_add("welcome", "1.0", "9.end")
                
                chat_text.config(state=tk.DISABLED)
                
            # Show success message
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.success("Chat history cleared")
                
            logger.info("Chat history cleared successfully")
            
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to clear chat history")
    
    def _clear_rag_history(self):
        """Clear the RAG conversation history."""
        try:
            # Clear the RAG processor history
            if hasattr(self.parent, 'rag_processor') and self.parent.rag_processor:
                self.parent.rag_processor.clear_history()
            
            # Clear the RAG text widget
            if 'rag_text' in self.components:
                rag_text = self.components['rag_text']
                rag_text.config(state=tk.NORMAL)
                rag_text.delete("1.0", tk.END)
                
                # Re-add welcome message
                rag_text.insert("1.0", "Welcome to the RAG Document Search!\n\n")
                rag_text.insert("end", "This interface allows you to search your document database:\n")
                rag_text.insert("end", "• Query documents stored in your RAG database\n")
                rag_text.insert("end", "• Get relevant information from your knowledge base\n")
                rag_text.insert("end", "• Search through previously uploaded documents\n\n")
                rag_text.insert("end", "Type your question in the AI Assistant chat box below to search your documents!\n")
                rag_text.insert("end", "="*50 + "\n\n")
                
                # Configure initial styling
                rag_text.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                rag_text.tag_add("welcome", "1.0", "9.end")
                
                rag_text.config(state=tk.DISABLED)
                
            # Show success message
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.success("RAG history cleared")
                
            logger.info("RAG history cleared successfully")
            
        except Exception as e:
            logger.error(f"Error clearing RAG history: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to clear RAG history")

    def _cancel_rag_query(self):
        """Cancel the current RAG query if one is in progress."""
        try:
            if hasattr(self.parent, 'rag_processor') and self.parent.rag_processor:
                if self.parent.rag_processor.cancel_current_query():
                    logger.info("RAG query cancellation requested")
                    if hasattr(self.parent, 'status_manager'):
                        self.parent.status_manager.info("Cancelling search...")
                    # Hide cancel button
                    self._hide_cancel_button()
                else:
                    logger.debug("No RAG query to cancel")
        except Exception as e:
            logger.error(f"Error cancelling RAG query: {e}")

    def show_cancel_button(self):
        """Show the cancel button when a RAG query starts."""
        try:
            if 'cancel_rag_button' in self.components:
                self.components['cancel_rag_button'].pack(side=tk.RIGHT, padx=(0, 5))
        except Exception as e:
            logger.debug(f"Error showing cancel button: {e}")

    def _hide_cancel_button(self):
        """Hide the cancel button when a RAG query completes."""
        try:
            if 'cancel_rag_button' in self.components:
                self.components['cancel_rag_button'].pack_forget()
        except Exception as e:
            logger.debug(f"Error hiding cancel button: {e}")

    def _show_rag_upload_dialog(self):
        """Show the RAG document upload dialog."""
        try:
            from src.ui.dialogs.rag_upload_dialog import RAGUploadDialog

            def on_upload(files: list, options: dict):
                """Handle upload start."""
                self._process_rag_uploads(files, options)

            dialog = RAGUploadDialog(self.parent, on_upload=on_upload)
            dialog.wait_window()
            self._update_rag_document_count()

        except Exception as e:
            logger.error(f"Error showing RAG upload dialog: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open upload dialog: {e}")

    def _process_rag_uploads(self, files: list, options: dict):
        """Process uploaded files in background thread.

        Args:
            files: List of file paths to upload
            options: Upload options (category, tags, enable_ocr, enable_graph)
        """
        import threading

        def upload_thread():
            try:
                from src.managers.rag_document_manager import get_rag_document_manager
                from src.ui.dialogs.rag_upload_dialog import RAGUploadProgressDialog

                manager = get_rag_document_manager()

                # Show progress dialog
                self.parent.after(0, lambda: self._show_upload_progress(files, options, manager))

            except Exception as e:
                logger.error(f"Error processing RAG uploads: {e}")
                error_msg = str(e)
                self.parent.after(0, lambda msg=error_msg: self._show_upload_error(msg))

        thread = threading.Thread(target=upload_thread, daemon=True)
        thread.start()

    def _show_upload_progress(self, files: list, options: dict, manager):
        """Show upload progress dialog and process files.

        Args:
            files: List of file paths
            options: Upload options
            manager: RAGDocumentManager instance
        """
        from src.ui.dialogs.rag_upload_dialog import RAGUploadProgressDialog

        progress_dialog = RAGUploadProgressDialog(self.parent, len(files))

        def process_files():
            success_count = 0
            fail_count = 0

            for i, file_path in enumerate(files):
                if progress_dialog.cancelled:
                    break

                import os
                filename = os.path.basename(file_path)
                self.parent.after(0, lambda f=filename, idx=i: progress_dialog.update_file_start(f, idx))

                try:
                    def progress_callback(progress):
                        self.parent.after(0, lambda p=progress: progress_dialog.update_file_progress(p))

                    manager.upload_document(
                        file_path=file_path,
                        category=options.get("category"),
                        tags=options.get("tags", []),
                        enable_ocr=options.get("enable_ocr", True),
                        enable_graph=options.get("enable_graph", True),
                        progress_callback=progress_callback,
                    )
                    success_count += 1
                    self.parent.after(0, lambda: progress_dialog.update_file_complete(True))

                except Exception as e:
                    logger.error(f"Failed to upload {filename}: {e}")
                    fail_count += 1
                    self.parent.after(0, lambda: progress_dialog.update_file_complete(False))

            self.parent.after(0, progress_dialog.complete)
            self.parent.after(0, self._update_rag_document_count)

            if success_count > 0 and hasattr(self.parent, 'status_manager'):
                self.parent.after(0, lambda: self.parent.status_manager.success(
                    f"Uploaded {success_count} document(s)"
                ))

        import threading
        thread = threading.Thread(target=process_files, daemon=True)
        thread.start()

    def _show_upload_error(self, error_msg: str):
        """Show upload error message."""
        from tkinter import messagebox
        messagebox.showerror("Upload Error", f"Failed to start upload:\n{error_msg}", parent=self.parent)

    def _show_rag_library_dialog(self):
        """Show the RAG document library dialog."""
        try:
            from src.ui.dialogs.rag_document_library_dialog import RAGDocumentLibraryDialog
            from src.managers.rag_document_manager import get_rag_document_manager

            manager = get_rag_document_manager()
            documents = manager.get_documents()

            def on_delete(doc_id: str) -> bool:
                return manager.delete_document(doc_id)

            def on_refresh():
                return manager.get_documents()

            def on_reprocess(doc_id: str):
                # Reprocess document - would need implementation
                logger.info(f"Reprocess requested for document {doc_id}")

            dialog = RAGDocumentLibraryDialog(
                self.parent,
                documents=documents,
                on_delete=on_delete,
                on_refresh=on_refresh,
                on_reprocess=on_reprocess,
            )
            dialog.wait_window()
            self._update_rag_document_count()

        except Exception as e:
            logger.error(f"Error showing RAG library dialog: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open document library: {e}")

    def _show_knowledge_graph_dialog(self):
        """Show the knowledge graph visualization dialog."""
        try:
            from src.ui.dialogs.knowledge_graph_dialog import KnowledgeGraphDialog
            from src.rag.graphiti_client import get_graphiti_client

            graphiti = get_graphiti_client()
            dialog = KnowledgeGraphDialog(self.parent, graphiti_client=graphiti)
            dialog.wait_window()

        except Exception as e:
            logger.error(f"Error showing knowledge graph dialog: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open knowledge graph: {e}")

    def _update_rag_document_count(self):
        """Update the RAG document count label."""
        try:
            if not hasattr(self, 'rag_doc_count_label'):
                return

            from src.managers.rag_document_manager import get_rag_document_manager
            manager = get_rag_document_manager()
            count = manager.get_document_count()

            if count == 0:
                text = "No documents"
            elif count == 1:
                text = "1 document"
            else:
                text = f"{count} documents"

            self.rag_doc_count_label.config(text=text)

        except Exception as e:
            logger.debug(f"Could not update RAG document count: {e}")
            if hasattr(self, 'rag_doc_count_label'):
                self.rag_doc_count_label.config(text="")

    def _open_medication_details(self) -> None:
        """Open full medication results dialog with current analysis."""
        try:
            logger.info("View Details button clicked - opening medication details")
            logger.info(f"self.parent type: {type(self.parent)}, id: {id(self.parent)}")

            # Check if analysis exists and has content
            analysis = getattr(self.parent, '_last_medication_analysis', None)
            logger.info(f"_last_medication_analysis found: {analysis is not None}")

            if not analysis:
                logger.warning("No medication analysis available on parent")
                logger.info(f"Parent attributes starting with '_last': {[a for a in dir(self.parent) if a.startswith('_last')]}")
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No medication analysis available. Generate a SOAP note first.")
                return

            result = analysis.get('result', '')
            logger.info(f"Analysis result type: {type(result)}, length: {len(result) if result else 0}")

            if not result:
                logger.warning("Medication analysis exists but result is empty")
                logger.info(f"Analysis keys: {list(analysis.keys())}")
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("Medication analysis is empty")
                return

            from ui.dialogs.medication_results_dialog import MedicationResultsDialog

            logger.info(f"Opening MedicationResultsDialog with result length: {len(result)}")
            dialog = MedicationResultsDialog(self.parent)
            dialog.show_results(
                result,
                analysis.get('analysis_type', 'comprehensive'),
                'SOAP Note',
                analysis.get('metadata', {})
            )
            logger.info("MedicationResultsDialog.show_results() completed")
        except Exception as e:
            logger.error(f"Error opening medication details: {e}", exc_info=True)
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open medication details: {str(e)}")

    def _open_diagnostic_details(self) -> None:
        """Open full diagnostic results dialog with current analysis."""
        try:
            logger.debug("View Details button clicked - opening diagnostic details")

            # Check if analysis exists and has content
            analysis = getattr(self.parent, '_last_diagnostic_analysis', None)
            if not analysis:
                logger.warning("No diagnostic analysis available on parent")
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No diagnostic analysis available. Generate a SOAP note first.")
                return

            # Simple inline dialog (DiagnosticResultsDialog available for full-featured display)
            from tkinter import messagebox

            analysis = self.parent._last_diagnostic_analysis
            result = analysis.get('result', 'No analysis available')

            # Create a simple dialog to display the result
            dialog = tk.Toplevel(self.parent)
            dialog.title("Differential Diagnosis Details")
            dialog.geometry("600x500")
            dialog.transient(self.parent)

            # Create text widget with scrollbar
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text_widget = tk.Text(
                frame,
                wrap=tk.WORD,
                yscrollcommand=scrollbar.set,
                font=("Segoe UI", 10)
            )
            text_widget.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)

            # Insert the analysis text
            text_widget.insert('1.0', result)
            text_widget.config(state='disabled')

            # Add close button
            close_btn = ttk.Button(
                dialog,
                text="Close",
                command=dialog.destroy,
                bootstyle="secondary"
            )
            close_btn.pack(pady=10)

            # Center the dialog
            dialog.update_idletasks()
            x = self.parent.winfo_x() + (self.parent.winfo_width() - dialog.winfo_width()) // 2
            y = self.parent.winfo_y() + (self.parent.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

        except Exception as e:
            logger.error(f"Error opening diagnostic details: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to open diagnostic details")

    def _export_rag_conversation(self, format: str):
        """Export RAG conversation history to specified format.

        Args:
            format: Export format ('pdf', 'docx', 'md', 'json')
        """
        try:
            from tkinter import filedialog
            from datetime import datetime
            from pathlib import Path

            # Get RAG processor and conversation history
            if not hasattr(self.parent, 'rag_processor') or not self.parent.rag_processor:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No RAG conversation to export")
                return

            # Get conversation data from processor
            conversation_data = self.parent.rag_processor.get_conversation_export_data()
            if not conversation_data or not conversation_data.get('exchanges'):
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No RAG conversation to export")
                return

            # File extension mapping
            ext_map = {'pdf': '.pdf', 'docx': '.docx', 'md': '.md', 'json': '.json'}
            ext = ext_map.get(format, '.json')

            # Default filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_name = f"rag_conversation_{timestamp}{ext}"

            # File type filter
            filetypes = {
                'pdf': [("PDF Files", "*.pdf")],
                'docx': [("Word Documents", "*.docx")],
                'md': [("Markdown Files", "*.md")],
                'json': [("JSON Files", "*.json")],
            }

            # Ask for save location
            filepath = filedialog.asksaveasfilename(
                parent=self.parent,
                defaultextension=ext,
                filetypes=filetypes.get(format, [("All Files", "*.*")]),
                initialfile=default_name,
                title=f"Export RAG Conversation as {format.upper()}"
            )

            if not filepath:
                return  # User cancelled

            # Export using RAG exporter
            from exporters.rag_exporter import get_rag_exporter
            exporter = get_rag_exporter()

            success = exporter.export(conversation_data, Path(filepath))

            if success:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.success(f"Exported to {Path(filepath).name}")
            else:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.error(f"Export failed: {exporter.last_error}")

        except Exception as e:
            logger.error(f"Error exporting RAG conversation: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Export failed: {str(e)}")

    def _toggle_rag_filters(self):
        """Toggle visibility of the RAG filters panel."""
        try:
            self._rag_filters_visible = not getattr(self, '_rag_filters_visible', False)

            filters_frame = self.components.get('rag_filters_frame')
            if not filters_frame:
                return

            if self._rag_filters_visible:
                # Lazy initialize filters panel
                if self._rag_filters_panel is None:
                    try:
                        from ui.components.search_filters import CompactFiltersBar
                        self._rag_filters_panel = CompactFiltersBar(
                            filters_frame,
                            on_filters_changed=self._on_rag_filters_changed
                        )
                    except Exception as e:
                        logger.error(f"Could not create filters panel: {e}")
                        return

                # Show filters
                filters_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2, before=self.components.get('rag_text'))
                if self._rag_filters_panel:
                    self._rag_filters_panel.show()

                # Update button style
                if 'rag_filters_button' in self.components:
                    self.components['rag_filters_button'].config(bootstyle="secondary")
            else:
                # Hide filters
                if self._rag_filters_panel:
                    self._rag_filters_panel.hide()
                filters_frame.pack_forget()

                # Reset button style
                if 'rag_filters_button' in self.components:
                    self.components['rag_filters_button'].config(bootstyle="secondary-outline")

        except Exception as e:
            logger.error(f"Error toggling RAG filters: {e}")

    def _on_rag_filters_changed(self, filters):
        """Handle RAG filter changes.

        Args:
            filters: SearchFilters object with current settings
        """
        try:
            # Store current filters for use in queries
            self._current_rag_filters = filters

            # Update status to show active filters
            if hasattr(self.parent, 'status_manager') and filters.has_filters():
                filter_summary = []
                if filters.document_types:
                    filter_summary.append(f"types:{','.join(filters.document_types)}")
                if filters.date_start:
                    filter_summary.append("date filter active")
                if filters.entity_types:
                    filter_summary.append(f"entities:{','.join(filters.entity_types)}")
                if filters.min_score > 0:
                    filter_summary.append(f"score>{filters.min_score:.0%}")

                self.parent.status_manager.info(f"Filters: {', '.join(filter_summary)}")

        except Exception as e:
            logger.debug(f"Error handling filter change: {e}")

    def _show_search_syntax_help(self):
        """Show help dialog for advanced search syntax."""
        try:
            from rag.search_syntax_parser import get_search_syntax_parser

            parser = get_search_syntax_parser()
            help_text = parser.format_help()

            # Create help dialog
            dialog = tk.Toplevel(self.parent)
            dialog.title("Advanced Search Syntax")
            dialog.geometry("550x500")
            dialog.transient(self.parent)

            # Create text widget with scrollbar
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text_widget = tk.Text(
                frame,
                wrap=tk.WORD,
                yscrollcommand=scrollbar.set,
                font=("Consolas", 10)
            )
            text_widget.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)

            # Insert help text
            text_widget.insert('1.0', help_text)
            text_widget.config(state='disabled')

            # Configure tags for styling
            text_widget.tag_configure("header", font=("Consolas", 11, "bold"))

            # Add close button
            close_btn = ttk.Button(
                dialog,
                text="Close",
                command=dialog.destroy,
                bootstyle="secondary"
            )
            close_btn.pack(pady=10)

            # Center the dialog
            dialog.update_idletasks()
            x = self.parent.winfo_x() + (self.parent.winfo_width() - dialog.winfo_width()) // 2
            y = self.parent.winfo_y() + (self.parent.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

        except Exception as e:
            logger.error(f"Error showing syntax help: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to show syntax help")

    def get_rag_source_highlighter(self):
        """Get the RAG source highlighter instance.

        Returns:
            SourceHighlighter instance or None
        """
        return getattr(self, '_rag_source_highlighter', None)

    def get_rag_source_legend(self):
        """Get the RAG source legend instance.

        Returns:
            SourceLegend instance or None
        """
        return getattr(self, '_rag_source_legend', None)

    def get_current_rag_filters(self):
        """Get the current RAG filter settings.

        Returns:
            SearchFilters object or None
        """
        return getattr(self, '_current_rag_filters', None)

    def show_medication_analysis_tab(self):
        """Switch to the Medication Analysis tab within the SOAP panel."""
        try:
            # Make sure analysis panel is expanded
            if hasattr(self, '_analysis_collapsed') and self._analysis_collapsed:
                self._toggle_analysis_panel()

            # Find the analysis notebook
            analysis_content = self.components.get('analysis_content')
            if analysis_content:
                for child in analysis_content.winfo_children():
                    if hasattr(child, 'select') and hasattr(child, 'tabs'):
                        tabs = child.tabs()
                        if tabs:
                            child.select(tabs[0])  # Medication is first tab
                        break
        except Exception as e:
            logger.debug(f"Could not switch to medication tab: {e}")

    def show_differential_analysis_tab(self):
        """Switch to the Differential Diagnosis tab within the SOAP panel."""
        try:
            # Make sure analysis panel is expanded
            if hasattr(self, '_analysis_collapsed') and self._analysis_collapsed:
                self._toggle_analysis_panel()

            # Find the analysis notebook
            analysis_content = self.components.get('analysis_content')
            if analysis_content:
                for child in analysis_content.winfo_children():
                    if hasattr(child, 'select') and hasattr(child, 'tabs'):
                        tabs = child.tabs()
                        if len(tabs) > 1:
                            child.select(tabs[1])  # Differential is second tab
                        break
        except Exception as e:
            logger.debug(f"Could not switch to differential tab: {e}")

    def show_compliance_analysis_tab(self):
        """Switch to the Clinical Guidelines tab within the SOAP panel."""
        try:
            # Make sure analysis panel is expanded
            if hasattr(self, '_analysis_collapsed') and self._analysis_collapsed:
                self._toggle_analysis_panel()

            # Find the analysis notebook
            analysis_content = self.components.get('analysis_content')
            if analysis_content:
                for child in analysis_content.winfo_children():
                    if hasattr(child, 'select') and hasattr(child, 'tabs'):
                        tabs = child.tabs()
                        if len(tabs) > 2:
                            child.select(tabs[2])  # Compliance is third tab
                        break
        except Exception as e:
            logger.debug(f"Could not switch to compliance tab: {e}")

    def _open_compliance_details(self) -> None:
        """Open full compliance results dialog with current analysis."""
        try:
            logger.debug("View Details button clicked - opening compliance details")

            # Check if analysis exists and has content
            analysis = getattr(self.parent, '_last_compliance_analysis', None)
            if not analysis:
                logger.warning("No compliance analysis available on parent")
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No compliance analysis available. Generate a SOAP note first.")
                return

            result = analysis.get('result', '')
            if not result:
                logger.warning("Compliance analysis exists but result is empty")
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("Compliance analysis is empty")
                return

            # Try to use ComplianceResultsDialog if available
            try:
                from ui.dialogs.compliance_results_dialog import ComplianceResultsDialog
                dialog = ComplianceResultsDialog(self.parent)
                dialog.show_results(
                    result,
                    analysis.get('metadata', {})
                )
                return
            except ImportError:
                pass

            # Fallback: simple dialog
            dialog = tk.Toplevel(self.parent)
            dialog.title("Clinical Guidelines Compliance Details")
            dialog.geometry("700x550")
            dialog.transient(self.parent)

            # Create text widget with scrollbar
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text_widget = tk.Text(
                frame,
                wrap=tk.WORD,
                yscrollcommand=scrollbar.set,
                font=("Segoe UI", 10)
            )
            text_widget.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)

            # Insert the analysis text
            text_widget.insert('1.0', result)
            text_widget.config(state='disabled')

            # Add close button
            close_btn = ttk.Button(
                dialog,
                text="Close",
                command=dialog.destroy,
                bootstyle="secondary"
            )
            close_btn.pack(pady=10)

            # Center the dialog
            dialog.update_idletasks()
            x = self.parent.winfo_x() + (self.parent.winfo_width() - dialog.winfo_width()) // 2
            y = self.parent.winfo_y() + (self.parent.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

        except Exception as e:
            logger.error(f"Error opening compliance details: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to open compliance details")

    def _show_guidelines_upload_dialog(self):
        """Show the clinical guidelines upload dialog."""
        try:
            # Check if the guidelines upload manager is available before opening dialog.
            # Catch all exceptions (not just ImportError) because importing the rag
            # package may trigger cascading imports that fail with other error types
            # in a frozen PyInstaller bundle.
            try:
                from rag.guidelines_upload_manager import get_guidelines_upload_manager
            except Exception:
                logger.info("Guidelines upload manager not available")
                # Use status bar instead of messagebox to avoid potential Tk
                # grab_set() conflicts that crash macOS .app bundles.
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.info(
                        "Guidelines not configured \u2013 "
                        "go to Settings \u2192 Preferences \u2192 RAG & Guidelines"
                    )
                else:
                    self._show_guidelines_not_implemented()
                return

            from ui.dialogs.guidelines_upload_dialog import GuidelinesUploadDialog

            self._guidelines_dialog = None

            def on_upload(files: list, options: dict):
                """Handle upload start."""
                self._process_guidelines_uploads(files, options)

            dialog = GuidelinesUploadDialog(self.parent, on_upload=on_upload)
            self._guidelines_dialog = dialog
            dialog.wait_window()
            self._guidelines_dialog = None

        except Exception as e:
            self._guidelines_dialog = None
            logger.error(f"Error showing guidelines upload dialog: {e}", exc_info=True)
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open guidelines upload: {e}")

    def _process_guidelines_uploads(self, files: list, options: dict):
        """Process uploaded guideline files in background thread.

        Args:
            files: List of file paths to upload
            options: Upload options (specialty, source, version, etc.)
        """
        import threading

        def upload_thread():
            try:
                from rag.guidelines_upload_manager import get_guidelines_upload_manager

                manager = get_guidelines_upload_manager()

                # Show progress dialog
                self.parent.after(0, lambda: self._show_guidelines_upload_progress(files, options, manager))

            except ImportError:
                # Manager not available - close the dialog first to release grab,
                # then show info message
                self.parent.after(0, self._dismiss_guidelines_dialog_and_notify)
            except Exception as e:
                logger.error(f"Error processing guidelines uploads: {e}")
                error_msg = str(e)
                self.parent.after(0, lambda msg=error_msg: self._show_upload_error(msg))

        thread = threading.Thread(target=upload_thread, daemon=True)
        thread.start()

    def _dismiss_guidelines_dialog_and_notify(self):
        """Safely dismiss the guidelines dialog before showing a notification.

        This prevents Tk grab conflicts on macOS where showing a messagebox
        while another dialog holds grab_set() causes the app to crash.
        """
        dialog = getattr(self, '_guidelines_dialog', None)
        if dialog:
            try:
                dialog.destroy()
            except Exception:
                pass
            self._guidelines_dialog = None
        self._show_guidelines_not_implemented()

    def _show_guidelines_upload_progress(self, files: list, options: dict, manager):
        """Show upload progress dialog and process guideline files.

        Args:
            files: List of file paths
            options: Upload options
            manager: Guidelines upload manager instance
        """
        from ui.dialogs.guidelines_upload_dialog import GuidelinesUploadProgressDialog
        from rag.guidelines_models import GuidelineUploadStatus

        progress_dialog = GuidelinesUploadProgressDialog(self.parent, len(files))

        def process_files():
            success_count = 0
            fail_count = 0

            for i, file_path in enumerate(files):
                if progress_dialog.cancelled:
                    break

                import os
                filename = os.path.basename(file_path)
                self.parent.after(0, lambda f=filename, idx=i: progress_dialog.update_file_start(f, idx))

                try:
                    def progress_callback(status, progress_pct, error=None):
                        self.parent.after(0, lambda s=status, p=progress_pct, e=error:
                            progress_dialog.update_file_progress(s, p, e))

                    manager.upload_guideline(
                        file_path=file_path,
                        specialty=options.get("specialty"),
                        source=options.get("source"),
                        version=options.get("version"),
                        effective_date=options.get("effective_date"),
                        document_type=options.get("document_type"),
                        title=options.get("title"),
                        extract_recommendations=options.get("extract_recommendations", True),
                        enable_graph=options.get("enable_graph", True),
                        enable_ocr=options.get("enable_ocr", True),
                        progress_callback=progress_callback,
                    )
                    success_count += 1
                    self.parent.after(0, lambda: progress_dialog.update_file_complete(True))

                except Exception as e:
                    logger.error(f"Failed to upload guideline {filename}: {e}")
                    fail_count += 1
                    self.parent.after(0, lambda: progress_dialog.update_file_complete(False))

            self.parent.after(0, progress_dialog.complete)

            if success_count > 0 and hasattr(self.parent, 'status_manager'):
                self.parent.after(0, lambda: self.parent.status_manager.success(
                    f"Uploaded {success_count} guideline(s)"
                ))

        thread = threading.Thread(target=process_files, daemon=True)
        thread.start()

    def _show_guidelines_not_implemented(self):
        """Show message that guidelines upload is not yet fully implemented."""
        from tkinter import messagebox
        messagebox.showinfo(
            "Guidelines Upload",
            "Guidelines upload manager is being set up.\n\n"
            "Please ensure the clinical guidelines database is configured:\n"
            "• Set CLINICAL_GUIDELINES_DATABASE_URL in .env\n"
            "• Run guidelines migrations",
            parent=self.parent
        )

    def load_saved_analyses(self, recording_id: int) -> dict:
        """Load saved medication, differential, and compliance analyses from database.

        Args:
            recording_id: The recording ID to load analyses for

        Returns:
            Dict with 'medication', 'differential', and 'compliance' keys,
            each containing the analysis result dict or None
        """
        try:
            from processing.analysis_storage import get_analysis_storage

            storage = get_analysis_storage()
            analyses = storage.get_analyses_for_recording(recording_id)

            # Update the analysis panels with saved data
            if analyses.get('medication'):
                self._update_medication_panel_from_saved(analyses['medication'])

            if analyses.get('differential'):
                self._update_differential_panel_from_saved(analyses['differential'])

            if analyses.get('compliance'):
                self._update_compliance_panel_from_saved(analyses['compliance'])

            return analyses

        except Exception as e:
            logger.error(f"Failed to load saved analyses for recording {recording_id}: {e}")
            return {"medication": None, "differential": None, "compliance": None}

    def _update_medication_panel_from_saved(self, analysis: dict) -> None:
        """Update medication analysis panel with saved analysis.

        Args:
            analysis: Saved analysis dict from database
        """
        try:
            medication_widget = self.components.get('medication_analysis_text')
            if not medication_widget:
                return

            result_text = analysis.get('result_text', '')
            metadata = analysis.get('metadata_json', {}) or {}

            # Store for View Details button
            self.parent._last_medication_analysis = {
                'result': result_text,
                'analysis_type': analysis.get('analysis_subtype', 'comprehensive'),
                'metadata': metadata
            }

            # Format and display
            try:
                from ui.components.analysis_panel_formatter import AnalysisPanelFormatter
                formatter = AnalysisPanelFormatter(medication_widget)
                formatter.format_medication_panel(result_text, metadata)
            except Exception:
                # Fallback to plain text
                medication_widget.config(state='normal')
                medication_widget.delete('1.0', 'end')
                medication_widget.insert('1.0', result_text)
                medication_widget.config(state='disabled')

            # Enable View Details button
            view_btn = self.components.get('medication_view_details_btn')
            if view_btn:
                view_btn.config(state='normal')

        except Exception as e:
            logger.error(f"Failed to update medication panel from saved: {e}")

    def _update_differential_panel_from_saved(self, analysis: dict) -> None:
        """Update differential analysis panel with saved analysis.

        Args:
            analysis: Saved analysis dict from database
        """
        try:
            differential_widget = self.components.get('differential_analysis_text')
            if not differential_widget:
                return

            result_text = analysis.get('result_text', '')
            metadata = analysis.get('metadata_json', {}) or {}

            # Store for View Details button
            self.parent._last_diagnostic_analysis = {
                'result': result_text,
                'metadata': metadata
            }

            # Format and display
            try:
                from ui.components.analysis_panel_formatter import AnalysisPanelFormatter
                formatter = AnalysisPanelFormatter(differential_widget)
                formatter.format_diagnostic_panel(result_text, metadata)
            except Exception:
                # Fallback to plain text
                differential_widget.config(state='normal')
                differential_widget.delete('1.0', 'end')
                differential_widget.insert('1.0', result_text)
                differential_widget.config(state='disabled')

            # Enable View Details button
            view_btn = self.components.get('differential_view_details_btn')
            if view_btn:
                view_btn.config(state='normal')

        except Exception as e:
            logger.error(f"Failed to update differential panel from saved: {e}")

    def _update_compliance_panel_from_saved(self, analysis: dict) -> None:
        """Update compliance analysis panel with saved analysis.

        Args:
            analysis: Saved analysis dict from database
        """
        try:
            compliance_widget = self.components.get('compliance_analysis_text')
            if not compliance_widget:
                return

            result_text = analysis.get('result_text', '')
            metadata = analysis.get('metadata_json', {}) or {}

            # Store for View Details button
            self.parent._last_compliance_analysis = {
                'result': result_text,
                'metadata': metadata
            }

            # Format and display
            try:
                from ui.components.analysis_panel_formatter import AnalysisPanelFormatter
                formatter = AnalysisPanelFormatter(compliance_widget)
                formatter.format_compliance_panel(result_text, metadata)
            except Exception:
                # Fallback to plain text
                compliance_widget.config(state='normal')
                compliance_widget.delete('1.0', 'end')
                compliance_widget.insert('1.0', result_text)
                compliance_widget.config(state='disabled')

            # Enable View Details button
            view_btn = self.components.get('compliance_view_details_btn')
            if view_btn:
                view_btn.config(state='normal')

        except Exception as e:
            logger.error(f"Failed to update compliance panel from saved: {e}")

    def clear_analysis_panels(self) -> None:
        """Clear the medication, differential, and compliance analysis panels."""
        try:
            # Clear medication panel
            medication_widget = self.components.get('medication_analysis_text')
            if medication_widget:
                medication_widget.config(state='normal')
                medication_widget.delete('1.0', 'end')
                medication_widget.insert('1.0', "Medication analysis will appear here after SOAP note generation.")
                medication_widget.config(state='disabled')

            # Disable medication view details button
            med_view_btn = self.components.get('medication_view_details_btn')
            if med_view_btn:
                med_view_btn.config(state='disabled')

            # Clear differential panel
            differential_widget = self.components.get('differential_analysis_text')
            if differential_widget:
                differential_widget.config(state='normal')
                differential_widget.delete('1.0', 'end')
                differential_widget.insert('1.0', "Differential diagnosis will appear here after SOAP note generation.")
                differential_widget.config(state='disabled')

            # Disable differential view details button
            diff_view_btn = self.components.get('differential_view_details_btn')
            if diff_view_btn:
                diff_view_btn.config(state='disabled')

            # Clear compliance panel
            compliance_widget = self.components.get('compliance_analysis_text')
            if compliance_widget:
                compliance_widget.config(state='normal')
                compliance_widget.delete('1.0', 'end')
                compliance_widget.insert('1.0', "Clinical guidelines compliance will appear here after SOAP note generation.\n\n"
                                        "Use the 'Upload Guidelines' button to add clinical guidelines to the database.")
                compliance_widget.config(state='disabled')

            # Disable compliance view details button
            compliance_view_btn = self.components.get('compliance_view_details_btn')
            if compliance_view_btn:
                compliance_view_btn.config(state='disabled')

            # Clear stored analyses
            if hasattr(self.parent, '_last_medication_analysis'):
                self.parent._last_medication_analysis = None
            if hasattr(self.parent, '_last_diagnostic_analysis'):
                self.parent._last_diagnostic_analysis = None
            if hasattr(self.parent, '_last_compliance_analysis'):
                self.parent._last_compliance_analysis = None

        except Exception as e:
            logger.debug(f"Error clearing analysis panels: {e}")