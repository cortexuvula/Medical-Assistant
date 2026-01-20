"""
Notebook Tabs Component for Medical Assistant
Handles the main text editor notebook with tabs
"""

import tkinter as tk
import ttkbootstrap as ttk
from utils.structured_logging import get_logger

from ui.tooltip import ToolTip

logger = get_logger(__name__)
from ui.ui_constants import Icons
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

        Note: Tab headers are hidden since sidebar navigation provides access to each section.
        The SOAP tab has a special split layout with medication and differential analysis panels.

        Returns:
            tuple: (notebook, transcript_text, soap_text, referral_text, letter_text, chat_text,
                    rag_text, context_text, medication_analysis_text, differential_analysis_text)
        """
        # Create a style that hides the notebook tabs
        style = ttk.Style()
        # Hide tabs by making them zero height and removing all visual elements
        style.configure("Hidden.TNotebook", tabmargins=[0, 0, 0, 0], padding=[0, 0])
        style.configure("Hidden.TNotebook.Tab",
                        padding=[0, 0, 0, 0],
                        width=0,
                        font=('', 1))
        style.map("Hidden.TNotebook.Tab",
                  width=[("selected", 0), ("!selected", 0)],
                  padding=[("selected", [0, 0, 0, 0]), ("!selected", [0, 0, 0, 0])])
        # Override the layout to remove tab content
        try:
            style.layout("Hidden.TNotebook.Tab", [])
        except Exception:
            pass  # Some themes may not support empty layout

        notebook = ttk.Notebook(self.parent, style="Hidden.TNotebook")
        
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

            # Add welcome message to chat tab
            if widget_key == "chat":
                # Add clear history button at the top
                button_frame = ttk.Frame(frame)
                button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
                
                clear_chat_btn = ttk.Button(
                    button_frame,
                    text="Clear Chat History",
                    command=lambda: self._clear_chat_history(),
                    bootstyle="secondary"
                )
                clear_chat_btn.pack(side=tk.RIGHT, padx=5)
                
                # Store reference to button
                self.components['clear_chat_button'] = clear_chat_btn
                
                text_widget.insert("1.0", "Welcome to the Medical Assistant Chat!\n\n")
                text_widget.insert("end", "This is your ChatGPT-style interface where you can:\n")
                text_widget.insert("end", "• Ask medical questions\n")
                text_widget.insert("end", "• Get explanations about medical terms\n")
                text_widget.insert("end", "• Have conversations about healthcare topics\n")
                text_widget.insert("end", "• Clear the chat with 'clear chat' command\n\n")
                text_widget.insert("end", "Type your message in the AI Assistant chat box below to start chatting with the AI!\n")
                text_widget.insert("end", "="*50 + "\n\n")
                
                # Configure initial styling
                text_widget.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                text_widget.tag_add("welcome", "1.0", "end")
                
                # Make text widget read-only but still selectable
                text_widget.bind("<Key>", lambda e: "break" if e.keysym not in ["Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End"] else None)
            
            # Add welcome message to RAG tab
            elif widget_key == "rag":
                # Add clear history button at the top
                button_frame = ttk.Frame(frame)
                button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
                
                clear_rag_btn = ttk.Button(
                    button_frame,
                    text="Clear RAG History",
                    command=lambda: self._clear_rag_history(),
                    bootstyle="secondary"
                )
                clear_rag_btn.pack(side=tk.RIGHT, padx=5)
                
                # Store reference to button
                self.components['clear_rag_button'] = clear_rag_btn
                
                text_widget.insert("1.0", "Welcome to the RAG Document Search!\n\n")
                text_widget.insert("end", "This interface allows you to search your document database:\n")
                text_widget.insert("end", "• Query documents stored in your RAG database\n")
                text_widget.insert("end", "• Get relevant information from your knowledge base\n")
                text_widget.insert("end", "• Search through previously uploaded documents\n\n")
                text_widget.insert("end", "Type your question in the AI Assistant chat box below to search your documents!\n")
                text_widget.insert("end", "="*50 + "\n\n")
                
                # Configure initial styling
                text_widget.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                text_widget.tag_add("welcome", "1.0", "end")
                
                # Make text widget read-only but still selectable
                text_widget.bind("<Key>", lambda e: "break" if e.keysym not in ["Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End"] else None)
        
        # Return in expected order
        return (
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
        header_frame = ttk.Frame(bottom_frame)
        header_frame.pack(fill=tk.X, padx=2, pady=2)

        # Collapse button first (on the left)
        # Icon shows the ACTION: when collapsed show expand icon (▼), when expanded show collapse icon (▲)
        initial_icon = Icons.EXPAND if is_collapsed else Icons.COLLAPSE
        collapse_btn = ttk.Button(
            header_frame,
            text=initial_icon,
            width=3,
            bootstyle="secondary-outline",
            command=self._toggle_analysis_panel
        )
        collapse_btn.pack(side=tk.LEFT, padx=2)
        self.components['analysis_collapse_btn'] = collapse_btn

        # Then the label
        header_label = ttk.Label(header_frame, text="Analysis", font=("", 10, "bold"))
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