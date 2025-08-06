"""
Notebook Tabs Component for Medical Assistant
Handles the main text editor notebook with tabs
"""

import tkinter as tk
import ttkbootstrap as ttk
import logging


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
        
        Returns:
            tuple: (notebook, transcript_text, soap_text, referral_text, letter_text, chat_text, rag_text, context_text)
        """
        notebook = ttk.Notebook(self.parent, style="Green.TNotebook")
        
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
            
            # Create text widget with scrollbar
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
            None  # No context text in notebook for workflow UI
        )
    
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
                
            logging.info("Chat history cleared successfully")
            
        except Exception as e:
            logging.error(f"Error clearing chat history: {e}")
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
                
            logging.info("RAG history cleared successfully")
            
        except Exception as e:
            logging.error(f"Error clearing RAG history: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to clear RAG history")