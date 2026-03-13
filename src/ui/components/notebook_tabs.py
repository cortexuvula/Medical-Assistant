"""
Notebook Tabs Component for Medical Assistant
Handles the main text editor notebook with tabs
"""

import threading
import tkinter as tk
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import ttkbootstrap as ttk
from utils.structured_logging import get_logger

from ui.tooltip import ToolTip

if TYPE_CHECKING:
    from ui.workflow_ui import WorkflowUI

logger = get_logger(__name__)
from ui.ui_constants import Icons, SidebarConfig, Fonts
from settings.settings import SETTINGS, save_settings

from ui.components.notebook_rag_mixin import NotebookRagMixin
from ui.components.notebook_guidelines_mixin import NotebookGuidelinesMixin
from ui.components.notebook_analysis_mixin import NotebookAnalysisMixin


class NotebookTabs(NotebookRagMixin, NotebookGuidelinesMixin, NotebookAnalysisMixin):
    """Manages the notebook tabs UI components."""

    def __init__(self, parent_ui: "WorkflowUI") -> None:
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
                    medication_analysis_text, differential_analysis_text,
                    compliance_analysis_text)
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

                # RAG component health indicators
                health_frame = ttk.Frame(right_buttons)
                health_frame.pack(side=tk.LEFT, padx=(0, 10))
                self._rag_health_indicators = {}
                for comp_name, comp_label in [
                    ("vector", "Vec"),
                    ("bm25", "BM25"),
                    ("graph", "Graph"),
                ]:
                    indicator = tk.Label(
                        health_frame,
                        text=f"\u25CF {comp_label}",
                        foreground="gray",
                        font=("Arial", 9),
                    )
                    indicator.pack(side=tk.LEFT, padx=(0, 6))
                    self._rag_health_indicators[comp_name] = indicator
                self._refresh_rag_health_indicators()

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
                except (ImportError, AttributeError) as e:
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
            text_widgets.get("differential_analysis"),
            text_widgets.get("compliance_analysis")
        )

    def _create_soap_split_layout(self, frame: ttk.Frame, text_widgets: Dict[str, tk.Text]) -> tk.Text:
        """Create the SOAP tab layout with analysis tabs below.

        Layout:
        +-------------------------------------------------------------+
        |                     SOAP Note (~70%)                         |
        +-------------------------------------------------------------+
        | [Medication Analysis] [Differential Dx]              [-]     |
        |  Analysis content with copy button...                        |
        +-------------------------------------------------------------+

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

        # Collapse button first (on the left) -- use tk.Label for clean minimal look
        # Icon shows the ACTION: when collapsed show expand icon, when expanded show collapse icon
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
                except tk.TclError:
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

        # Guidelines Library button
        guidelines_library_btn = ttk.Button(
            compliance_header,
            text="Guidelines Library",
            bootstyle="info-outline",
            command=self._show_guidelines_library_dialog
        )
        guidelines_library_btn.pack(side=tk.LEFT, padx=2)
        self.components['guidelines_library_btn'] = guidelines_library_btn

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

        # ----- Tab 4: Emotional Assessment -----
        emotion_tab = ttk.Frame(analysis_notebook)
        analysis_notebook.add(emotion_tab, text="  Emotional Assessment  ")

        # Emotion header with copy button
        emotion_header = ttk.Frame(emotion_tab)
        emotion_header.pack(fill=tk.X, padx=5, pady=3)

        emotion_copy_btn = ttk.Button(
            emotion_header,
            text="Copy",
            bootstyle="info-outline",
            command=lambda: self._copy_to_clipboard(emotion_analysis_text)
        )
        emotion_copy_btn.pack(side=tk.RIGHT, padx=2)

        # View Details button for full emotion dialog
        emotion_view_btn = ttk.Button(
            emotion_header,
            text="View Details",
            bootstyle="success-outline",
            command=self._open_emotion_details,
            state='disabled'  # Initially disabled until analysis is available
        )
        emotion_view_btn.pack(side=tk.RIGHT, padx=2)
        self.components['emotion_view_details_btn'] = emotion_view_btn

        # Emotion analysis scrollbar and text widget
        emotion_content = ttk.Frame(emotion_tab)
        emotion_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        emotion_scroll = ttk.Scrollbar(emotion_content)
        emotion_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        emotion_analysis_text = tk.Text(
            emotion_content,
            wrap=tk.WORD,
            yscrollcommand=emotion_scroll.set,
            state='disabled',
            height=8
        )
        emotion_analysis_text.pack(fill=tk.BOTH, expand=True)
        emotion_scroll.config(command=emotion_analysis_text.yview)

        # Initial placeholder message
        emotion_analysis_text.config(state='normal')
        emotion_analysis_text.insert('1.0', "Emotional assessment will appear here when using Modulate STT provider.")
        emotion_analysis_text.config(state='disabled')

        # Store reference
        text_widgets['emotion_analysis'] = emotion_analysis_text
        self.components['emotion_analysis_text'] = emotion_analysis_text

        return soap_text

    def _copy_to_clipboard(self, text_widget: tk.Text) -> None:
        """Copy text widget content to clipboard.

        Args:
            text_widget: The text widget to copy from
        """
        try:
            content = text_widget.get('1.0', 'end-1c')
            try:
                import pyperclip
                pyperclip.copy(content)
            except ImportError:
                self.parent.clipboard_clear()
                self.parent.clipboard_append(content)
                self.parent.update()
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.success("Copied to clipboard")
        except tk.TclError as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to copy")

    def _clear_chat_history(self) -> None:
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
                chat_text.insert("end", "\u2022 Have free-form conversations about medical topics\n")
                chat_text.insert("end", "\u2022 Get help with medical documentation\n")
                chat_text.insert("end", "\u2022 Ask questions about your recordings and notes\n")
                chat_text.insert("end", "\u2022 Request analysis and suggestions\n\n")
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

        except tk.TclError as e:
            logger.error(f"Error clearing chat history: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to clear chat history")
