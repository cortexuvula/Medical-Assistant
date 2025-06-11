"""
Chat Processor for Medical Assistant
Handles LLM interactions for conversational AI features
"""

import logging
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from settings.settings import SETTINGS


class ChatProcessor:
    """Processes chat messages and handles AI interactions"""
    
    def __init__(self, app):
        """
        Initialize the chat processor.
        
        Args:
            app: Reference to the main application
        """
        self.app = app
        self.is_processing = False
        self.conversation_history = []
        
        # Configuration from settings
        chat_config = SETTINGS.get("chat_interface", {})
        self.max_context_length = chat_config.get("max_context_length", 8000)
        self.max_history_items = chat_config.get("max_history_items", 10)
        self.temperature = chat_config.get("temperature", 0.3)
        
    def process_message(self, user_message: str, callback: Optional[Callable] = None):
        """
        Process a chat message from the user.
        
        Args:
            user_message: The user's input message
            callback: Optional callback to call when processing is complete
        """
        if self.is_processing:
            logging.warning("Chat processor is already processing a message")
            return
            
        # Run processing in a separate thread to avoid blocking UI
        thread = threading.Thread(
            target=self._process_message_async,
            args=(user_message, callback),
            daemon=True
        )
        thread.start()
        
    def _process_message_async(self, user_message: str, callback: Optional[Callable]):
        """Async processing of chat message."""
        try:
            self.is_processing = True
            
            # Get current context from active tab
            context_data = self._extract_context()
            
            # Check for special chat commands when in chat tab
            if context_data.get("tab_name") == "chat" and self._handle_chat_command(user_message):
                return  # Command was handled, no need to call AI
            
            # Add user message to history
            self._add_to_history("user", user_message)
            
            # Construct prompt for AI
            prompt = self._construct_prompt(user_message, context_data)
            
            # Get AI response
            ai_response = self._get_ai_response(prompt)
            
            if ai_response:
                # Add AI response to history
                self._add_to_history("assistant", ai_response)
                
                # Process the response (apply changes if requested)
                self._process_ai_response(user_message, ai_response, context_data)
                
            else:
                self.app.status_manager.error("Failed to get AI response")
                
        except Exception as e:
            logging.error(f"Error processing chat message: {e}", exc_info=True)
            self.app.status_manager.error(f"Chat processing error: {str(e)}")
            
        finally:
            self.is_processing = False
            
            # Call callback on main thread
            if callback:
                self.app.after(0, callback)
                
    def _extract_context(self) -> Dict[str, Any]:
        """Extract context from the currently active tab."""
        context = {
            "tab_name": "",
            "tab_index": 0,
            "content": "",
            "content_length": 0,
            "has_content": False
        }
        
        try:
            # Get current tab info
            current_tab = self.app.notebook.index(self.app.notebook.select())
            tab_names = ["transcript", "soap", "referral", "letter", "chat"]
            
            if 0 <= current_tab < len(tab_names):
                context["tab_name"] = tab_names[current_tab]
                context["tab_index"] = current_tab
                
                # Get content from active text widget
                if hasattr(self.app, 'active_text_widget') and self.app.active_text_widget:
                    content = self.app.active_text_widget.get("1.0", "end-1c").strip()
                    context["content"] = content
                    context["content_length"] = len(content)
                    context["has_content"] = bool(content)
                    
                    # Truncate if too long
                    if len(content) > self.max_context_length:
                        context["content"] = content[:self.max_context_length] + "...[truncated]"
                        
        except Exception as e:
            logging.error(f"Error extracting context: {e}")
            
        return context
        
    def _construct_prompt(self, user_message: str, context_data: Dict[str, Any]) -> str:
        """Construct the prompt to send to the AI."""
        
        # System message based on context
        tab_name = context_data.get("tab_name", "unknown")
        
        system_messages = {
            "transcript": "You are an AI assistant helping with medical transcription analysis. You can help summarize, extract information, remove speaker labels, clean up formatting, and answer questions about the transcript content. When asked to modify text, provide the complete cleaned version.",
            "soap": "You are an AI assistant helping with SOAP note creation and improvement. You can help improve clarity, add medical detail, ensure proper medical documentation format, and fix any formatting issues. When modifying content, provide the complete updated version.",
            "referral": "You are an AI assistant helping with medical referral letters. You can help make them more professional, add urgency indicators, ensure proper referral format, and improve overall presentation. When editing, provide the complete improved version.",
            "letter": "You are an AI assistant helping with patient communication letters. You can help improve tone, clarity, empathy, and formatting while maintaining medical accuracy. When modifying content, provide the complete updated version.",
            "chat": "You are a helpful medical AI assistant. Engage in conversation, answer questions, provide medical information, and help with various healthcare-related queries. Do not modify any document content - just have a natural conversation."
        }
        
        system_msg = system_messages.get(tab_name, "You are an AI assistant helping with medical documentation.")
        
        # Build prompt
        prompt_parts = [
            f"System: {system_msg}",
            "",
            "Current Context:",
            f"- Document Type: {tab_name.title()}",
            f"- Has Content: {'Yes' if context_data.get('has_content') else 'No'}",
        ]
        
        # Add content if available
        if context_data.get("has_content"):
            prompt_parts.extend([
                "",
                "Current Document Content:",
                "---",
                context_data.get("content", ""),
                "---",
                ""
            ])
        
        # Add conversation history (last few exchanges)
        if self.conversation_history:
            prompt_parts.append("Recent Conversation:")
            for item in self.conversation_history[-6:]:  # Last 3 exchanges
                role = item["role"].title()
                message = item["message"][:200] + "..." if len(item["message"]) > 200 else item["message"]
                prompt_parts.append(f"{role}: {message}")
            prompt_parts.append("")
        
        # Add current user message
        prompt_parts.extend([
            f"User Request: {user_message}",
            "",
            "Please provide a helpful response. If the user is asking you to modify the document content, provide the improved version and explain what changes you made."
        ])
        
        return "\n".join(prompt_parts)
        
    def _get_ai_response(self, prompt: str) -> Optional[str]:
        """Get response from AI provider."""
        try:
            # Import AI functions
            from ai.ai import call_openai, call_perplexity, call_grok, call_ai
            
            # Get current AI provider setting
            provider = SETTINGS.get("ai_provider", "openai").lower()
            system_message = "You are a helpful medical AI assistant specialized in medical documentation and analysis."
            
            if provider == "openai":
                model = SETTINGS.get("openai", {}).get("model", "gpt-4")
                response = call_openai(
                    model=model,
                    system_message=system_message,
                    prompt=prompt,
                    temperature=self.temperature
                )
            elif provider == "grok":
                model = SETTINGS.get("grok", {}).get("model", "grok-beta")
                response = call_grok(
                    model=model,
                    system_message=system_message,
                    prompt=prompt,
                    temperature=self.temperature
                )
            elif provider == "perplexity":
                response = call_perplexity(
                    system_message=system_message,
                    prompt=prompt,
                    temperature=self.temperature
                )
            else:
                # Fallback to generic call_ai function
                logging.warning(f"Unknown provider '{provider}', using fallback")
                response = call_ai(
                    model="gpt-4",
                    system_message=system_message,
                    prompt=prompt,
                    temperature=self.temperature
                )
                    
            return response
                
        except Exception as e:
            logging.error(f"Error getting AI response: {e}", exc_info=True)
            
        return None
        
    def _process_ai_response(self, user_message: str, ai_response: str, context_data: Dict[str, Any]):
        """Process the AI response and apply changes if needed."""
        
        # Show the response to the user first
        self._show_ai_response(ai_response)
        
        # Special handling for chat tab - append conversation instead of replacing
        if context_data.get("tab_name") == "chat":
            self._append_to_chat_tab(user_message, ai_response)
        else:
            # Check if user wants to apply changes to the document
            if self._should_apply_to_document(user_message, ai_response):
                # Check if auto-apply is enabled (default: True)
                chat_config = SETTINGS.get("chat_interface", {})
                auto_apply = chat_config.get("auto_apply_changes", True)
                
                if auto_apply:
                    self._apply_response_to_document(ai_response, context_data)
                else:
                    # Legacy behavior with confirmation dialog
                    self._apply_response_with_confirmation(ai_response, context_data)
            
    def _show_ai_response(self, response: str):
        """Show a brief notification about the AI response."""
        # Since we're auto-applying changes, just show a brief status update
        # Full response details are logged for debugging
        
        def show_notification():
            try:
                # Log the full response for debugging
                logging.info(f"AI Response received: {response[:200]}{'...' if len(response) > 200 else ''}")
                
                # Show brief notification in status bar
                self.app.status_manager.info("AI response processed and applied")
                
            except Exception as e:
                logging.error(f"Error showing AI response notification: {e}")
                
        # Show on main thread
        self.app.after(0, show_notification)
        
    def _should_apply_to_document(self, user_message: str, ai_response: str) -> bool:
        """Determine if the AI response should be applied to the document."""
        
        # Keywords that suggest the user wants to modify the document
        modification_keywords = [
            "improve", "rewrite", "edit", "modify", "change", "update",
            "make it", "make more", "make less", "add to", "remove from",
            "fix", "correct", "enhance", "revise", "rephrase", "delete",
            "remove", "replace", "substitute", "clean up", "format"
        ]
        
        user_lower = user_message.lower()
        
        # Check if user message contains modification keywords
        for keyword in modification_keywords:
            if keyword in user_lower:
                return True
                
        # Specific patterns that indicate document modification
        modification_patterns = [
            "remove speaker_", "delete speaker_", "clean up the text",
            "format this", "fix the formatting", "make this better"
        ]
        
        for pattern in modification_patterns:
            if pattern in user_lower:
                return True
                
        # Check if AI response contains markers suggesting it's a document modification
        response_lower = ai_response.lower()
        if any(marker in response_lower for marker in [
            "here's the improved", "here's the revised", "updated version:",
            "improved version:", "revised text:", "corrected text:",
            "here's the cleaned", "cleaned up version:", "formatted version:"
        ]):
            return True
            
        return False
        
    def _apply_response_to_document(self, ai_response: str, context_data: Dict[str, Any]):
        """Apply the AI response to the current document automatically."""
        
        def apply_changes():
            try:
                # Extract the actual content from the AI response
                content_to_apply = self._extract_content_from_response(ai_response)
                
                if content_to_apply and hasattr(self.app, 'active_text_widget') and self.app.active_text_widget:
                    # Automatically replace content without asking
                    self.app.active_text_widget.delete("1.0", "end")
                    self.app.active_text_widget.insert("1.0", content_to_apply)
                    
                    # Show success message
                    tab_name = context_data.get("tab_name", "document").title()
                    self.app.status_manager.success(f"{tab_name} updated with AI response")
                    
                    logging.info(f"Auto-applied AI response to {tab_name} tab")
                else:
                    logging.warning("No content to apply or no active text widget")
                    self.app.status_manager.warning("No content to apply to document")
                        
            except Exception as e:
                logging.error(f"Error applying AI response to document: {e}")
                self.app.status_manager.error("Failed to apply changes")
                
        # Apply on main thread
        self.app.after(0, apply_changes)
        
    def _apply_response_with_confirmation(self, ai_response: str, context_data: Dict[str, Any]):
        """Apply the AI response to the current document with user confirmation."""
        
        def apply_changes():
            try:
                # Extract the actual content from the AI response
                content_to_apply = self._extract_content_from_response(ai_response)
                
                if content_to_apply and hasattr(self.app, 'active_text_widget') and self.app.active_text_widget:
                    # Ask user for confirmation
                    from tkinter import messagebox
                    
                    tab_name = context_data.get("tab_name", "document").title()
                    
                    if messagebox.askyesno(
                        "Apply Changes",
                        f"Do you want to apply the AI's suggestions to your {tab_name}?\n\n"
                        "This will replace the current content.",
                        parent=self.app
                    ):
                        # Replace content
                        self.app.active_text_widget.delete("1.0", "end")
                        self.app.active_text_widget.insert("1.0", content_to_apply)
                        
                        self.app.status_manager.success(f"{tab_name} updated with AI response")
                    else:
                        self.app.status_manager.info("Changes not applied")
                else:
                    self.app.status_manager.warning("No content to apply to document")
                        
            except Exception as e:
                logging.error(f"Error applying AI response to document: {e}")
                self.app.status_manager.error("Failed to apply changes")
                
        # Apply on main thread
        self.app.after(0, apply_changes)
        
    def _extract_content_from_response(self, ai_response: str) -> str:
        """Extract the actual content to apply from the AI response."""
        # Look for common patterns that indicate the start of the cleaned content
        patterns_to_try = [
            "here's the improved version:\n",
            "here's the cleaned version:\n",
            "here's the corrected text:\n",
            "revised text:\n",
            "updated version:\n",
            "improved version:\n",
            "corrected text:\n",
            "cleaned up version:\n",
            "formatted version:\n",
            "here's the text with speaker labels removed:\n",
            "cleaned text:\n"
        ]
        
        response_lower = ai_response.lower()
        
        for pattern in patterns_to_try:
            if pattern in response_lower:
                start_index = response_lower.find(pattern) + len(pattern)
                content = ai_response[start_index:].strip()
                
                # Remove any trailing explanations or notes
                lines = content.split('\n')
                # Look for lines that seem like AI explanations rather than content
                content_lines = []
                for line in lines:
                    line_lower = line.lower().strip()
                    if (line_lower.startswith(("note:", "explanation:", "i've", "this version", 
                                             "the changes", "summary:")) or
                        "changes made" in line_lower):
                        break  # Stop at explanation lines
                    content_lines.append(line)
                
                return '\n'.join(content_lines).strip()
        
        # Look for content between quotation marks or code blocks
        import re
        
        # Check for content in triple quotes or code blocks
        code_block_pattern = r'```(?:text|markdown)?\s*\n(.*?)\n```'
        match = re.search(code_block_pattern, ai_response, re.DOTALL)
        if match:
            return match.group(1).strip()
            
        # Check for content in double quotes
        # Use a simpler pattern to avoid ReDoS vulnerability
        quote_pattern = r'"([^"]+)"'
        matches = re.findall(quote_pattern, ai_response, re.DOTALL)
        if matches:
            # Return the longest quoted content
            return max(matches, key=len).strip()
                
        # If no specific pattern found, try to extract the main content
        lines = ai_response.split('\n')
        
        # Skip introductory lines and find the main content
        content_start = 0
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if (line_lower.startswith(("here", "i've", "the text", "below")) or
                "speaker_" in line_lower):
                content_start = i + 1
                break
                
        if content_start < len(lines):
            return '\n'.join(lines[content_start:]).strip()
            
        return ai_response.strip()
        
    def _add_to_history(self, role: str, message: str):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only recent history
        if len(self.conversation_history) > self.max_history_items:
            self.conversation_history = self.conversation_history[-self.max_history_items:]
            
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        logging.info("Chat conversation history cleared")
        
    def get_history(self) -> list:
        """Get conversation history."""
        return self.conversation_history.copy()
    
    def _append_to_chat_tab(self, user_message: str, ai_response: str):
        """Append conversation to chat tab in ChatGPT style."""
        def append_chat():
            try:
                chat_widget = self.app.chat_text
                
                # Get current content to check if we need separator
                current_content = chat_widget.get("1.0", "end-1c")
                
                # Add separator if there's existing content
                if current_content.strip():
                    chat_widget.insert("end", "\n" + "="*50 + "\n\n")
                
                # Add timestamp
                timestamp = datetime.now().strftime("%H:%M:%S")
                chat_widget.insert("end", f"[{timestamp}]\n", "timestamp")
                
                # Add user message
                chat_widget.insert("end", f"User: {user_message}\n\n", "user")
                
                # Add AI response with copy button
                chat_widget.insert("end", "Assistant: ", "assistant_label")
                
                # Store the response position for copy functionality
                response_start = chat_widget.index("end-1c")
                chat_widget.insert("end", ai_response, ("assistant_response", f"response_{timestamp}"))
                response_end = chat_widget.index("end-1c")
                
                # Add copy button after the response
                chat_widget.insert("end", "  ")
                
                # Create copy button
                import tkinter as tk
                import ttkbootstrap as ttk
                
                # Create a small frame to hold the button
                button_frame = tk.Frame(chat_widget, bg=chat_widget.cget('bg'))
                
                copy_btn = ttk.Button(
                    button_frame,
                    text="Copy",
                    bootstyle="secondary-link",
                    command=lambda r=ai_response: self._copy_to_clipboard(r)
                )
                copy_btn.pack(padx=2)
                
                # Add tooltip
                from ui.tooltip import ToolTip
                ToolTip(copy_btn, "Copy this response to clipboard")
                
                # Create window for button frame in text widget
                chat_widget.window_create("end-1c", window=button_frame)
                chat_widget.insert("end", "\n")
                
                # Bind right-click to the response text
                chat_widget.tag_bind(f"response_{timestamp}", "<Button-3>", 
                                   lambda e, r=ai_response: self._show_copy_menu(e, r))
                
                # Bind double-click to select the entire response
                chat_widget.tag_bind(f"response_{timestamp}", "<Double-Button-1>", 
                                   lambda e: self._select_response(e, response_start, response_end))
                
                # Configure tags for styling
                chat_widget.tag_config("timestamp", foreground="gray", font=("Arial", 9))
                chat_widget.tag_config("user", foreground="#0066cc", font=("Arial", 11, "bold"))
                chat_widget.tag_config("assistant_label", foreground="#008800", font=("Arial", 11, "bold"))
                chat_widget.tag_config("assistant_response", foreground="#008800", font=("Arial", 11))
                
                # Add hover effect for responses
                chat_widget.tag_bind(f"response_{timestamp}", "<Enter>", 
                                   lambda e: chat_widget.config(cursor="hand2"))
                chat_widget.tag_bind(f"response_{timestamp}", "<Leave>", 
                                   lambda e: chat_widget.config(cursor=""))
                
                # Scroll to bottom
                chat_widget.see("end")
                
                # Save to database if we have a current recording
                if hasattr(self.app, 'current_recording_id') and self.app.current_recording_id:
                    try:
                        # Get full chat content
                        full_chat = chat_widget.get("1.0", "end-1c")
                        # Update database
                        if self.app.db.update_recording(self.app.current_recording_id, chat=full_chat):
                            logging.info(f"Updated recording {self.app.current_recording_id} with chat content")
                    except Exception as e:
                        logging.error(f"Failed to save chat to database: {e}")
                
                # Update status
                self.app.status_manager.success("Chat response added")
                
            except Exception as e:
                logging.error(f"Error appending to chat tab: {e}")
                self.app.status_manager.error("Failed to add chat response")
        
        # Execute on main thread
        self.app.after(0, append_chat)
    
    def _handle_chat_command(self, message: str) -> bool:
        """Handle special chat commands. Returns True if command was handled."""
        message_lower = message.lower().strip()
        
        if message_lower in ["clear chat history", "clear chat", "clear", "/clear"]:
            def clear_chat():
                try:
                    # Clear the chat text widget
                    self.app.chat_text.delete("1.0", "end")
                    # Clear conversation history
                    self.clear_history()
                    # Update status
                    self.app.status_manager.success("Chat history cleared")
                except Exception as e:
                    logging.error(f"Error clearing chat: {e}")
                    self.app.status_manager.error("Failed to clear chat")
            
            self.app.after(0, clear_chat)
            return True
        
        return False
    
    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        try:
            # Clear clipboard and append new text
            self.app.clipboard_clear()
            self.app.clipboard_append(text)
            self.app.update()  # Required to finalize clipboard operation
            
            # Show brief success message
            self.app.status_manager.success("Response copied to clipboard")
            logging.info("Assistant response copied to clipboard")
        except Exception as e:
            logging.error(f"Failed to copy to clipboard: {e}")
            self.app.status_manager.error("Failed to copy response")
    
    def _show_copy_menu(self, event, response_text: str):
        """Show context menu for copying response."""
        try:
            import tkinter as tk
            
            # Create context menu
            context_menu = tk.Menu(self.app, tearoff=0)
            context_menu.add_command(
                label="Copy Response", 
                command=lambda: self._copy_to_clipboard(response_text)
            )
            context_menu.add_separator()
            context_menu.add_command(
                label="Select All",
                command=lambda: event.widget.tag_add(tk.SEL, "1.0", tk.END)
            )
            
            # Show menu at cursor position
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
                
        except Exception as e:
            logging.error(f"Error showing context menu: {e}")
    
    def _select_response(self, event, start_idx, end_idx):
        """Select an entire response when double-clicked."""
        try:
            import tkinter as tk
            
            # Clear any existing selection
            event.widget.tag_remove(tk.SEL, "1.0", tk.END)
            
            # Select the response text
            event.widget.tag_add(tk.SEL, start_idx, end_idx)
            
            # Set focus to enable keyboard shortcuts
            event.widget.focus_set()
            
        except Exception as e:
            logging.error(f"Error selecting response: {e}")