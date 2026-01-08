"""
App Chat Mixin Module

Contains chat-related methods for the MedicalDictationApp class.
These are extracted as a mixin to reduce the size of the main app.py file.
"""

import logging
import tkinter as tk
from typing import List


class AppChatMixin:
    """Mixin class providing chat-related methods for MedicalDictationApp."""

    def _handle_chat_message(self, message: str):
        """Handle chat message from the chat UI."""
        logging.info(f"Chat message received: {message}")

        # Check which tab is currently active
        current_tab = self.notebook.index(self.notebook.select())

        # Route to appropriate processor based on tab
        if current_tab == 5:  # RAG tab (0-indexed)
            # Check for clear command
            message_lower = message.lower().strip()
            if message_lower in ["clear rag history", "clear rag", "clear", "/clear"]:
                if hasattr(self, 'rag_processor') and self.rag_processor:
                    self.rag_processor.clear_history()
                    self.status_manager.success("RAG history cleared")
                if hasattr(self, 'chat_ui') and self.chat_ui:
                    self.chat_ui.set_processing(False)
                return

            if not hasattr(self, 'rag_processor') or not self.rag_processor:
                self.status_manager.error("RAG processor not available")
                if hasattr(self, 'chat_ui') and self.chat_ui:
                    self.chat_ui.set_processing(False)
                return

            # Switch to RAG tab so user can see the response
            self.notebook.select(5)  # RAG tab index

            # Update status
            self.status_manager.info("Searching documents...")

            # Process the RAG query
            def on_complete():
                """Called when RAG processing is complete."""
                if hasattr(self, 'chat_ui') and self.chat_ui:
                    self.chat_ui.set_processing(False)
                self.status_manager.success("Document search complete")

            self.rag_processor.process_message(message, on_complete)

        else:  # Chat tab or other tabs
            if not hasattr(self, 'chat_processor') or not self.chat_processor:
                self.status_manager.error("Chat processor not available")
                if hasattr(self, 'chat_ui') and self.chat_ui:
                    self.chat_ui.set_processing(False)
                return

            # Switch to Chat tab so user can see the response
            self.notebook.select(4)  # Chat tab index

            # Update status
            self.status_manager.info("Processing your request...")

            # Process the message
            def on_complete():
                """Called when chat processing is complete."""
                if hasattr(self, 'chat_ui') and self.chat_ui:
                    self.chat_ui.set_processing(False)
                self.status_manager.success("Chat response ready")

            self.chat_processor.process_message(message, on_complete)

    def _update_chat_suggestions(self):
        """Update chat suggestions based on current tab and content."""
        if not hasattr(self, 'chat_ui') or not self.chat_ui:
            return

        current_tab = self.notebook.index(self.notebook.select())
        custom_suggestions_list = []

        # Get current content
        content = self.active_text_widget.get("1.0", tk.END).strip()
        has_content = bool(content)

        # Get custom suggestions from settings
        from settings.settings import SETTINGS
        custom_suggestions = SETTINGS.get("custom_chat_suggestions", {})

        # Helper to normalize suggestion to object format
        def normalize_suggestion(s):
            if isinstance(s, dict) and "text" in s:
                return s
            elif isinstance(s, str):
                return {"text": s, "favorite": False}
            return None

        # Add global custom suggestions first
        global_custom = custom_suggestions.get("global", [])
        for s in global_custom:
            normalized = normalize_suggestion(s)
            if normalized:
                custom_suggestions_list.append(normalized)

        # Determine context and content state
        context_map = {0: "transcript", 1: "soap", 2: "referral", 3: "letter", 4: "chat", 5: "rag"}
        context = context_map.get(current_tab, "transcript")
        content_state = "with_content" if has_content else "without_content"

        # Add context-specific custom suggestions
        context_custom = custom_suggestions.get(context, {}).get(content_state, [])
        for s in context_custom:
            normalized = normalize_suggestion(s)
            if normalized:
                custom_suggestions_list.append(normalized)

        # Sort custom suggestions: favorites first (alphabetically), then non-favorites (alphabetically)
        favorites = sorted(
            [s for s in custom_suggestions_list if s.get("favorite")],
            key=lambda x: x["text"].lower()
        )
        non_favorites = sorted(
            [s for s in custom_suggestions_list if not s.get("favorite")],
            key=lambda x: x["text"].lower()
        )
        sorted_custom = favorites + non_favorites

        # Add built-in suggestions as fallback/additional options (always non-favorites)
        builtin_suggestions = self._get_builtin_suggestions(current_tab, has_content)
        builtin_objects = [{"text": s, "favorite": False} for s in builtin_suggestions]

        # Combine custom + builtin
        all_suggestions = sorted_custom + builtin_objects

        # Remove duplicates while preserving order (favorites first, then sorted non-favorites)
        seen = set()
        unique_suggestions = []
        for suggestion in all_suggestions:
            text = suggestion["text"]
            if text not in seen:
                seen.add(text)
                unique_suggestions.append(suggestion)

        # Limit to max 6 suggestions to avoid UI clutter
        self.chat_ui.set_suggestions(unique_suggestions[:6])

    def _get_builtin_suggestions(self, current_tab: int, has_content: bool) -> List[str]:
        """Get built-in suggestions for the given context."""
        from settings.settings import SETTINGS

        if current_tab == 0:  # Transcript
            if has_content:
                return [
                    "Summarize key points",
                    "Extract symptoms mentioned",
                    "Identify medications"
                ]
            else:
                return [
                    "Analyze uploaded audio",
                    "Extract medical terms",
                    "Create summary"
                ]
        elif current_tab == 1:  # SOAP
            if has_content:
                return [
                    "Improve grammar and clarity",
                    "Add more detail to assessment",
                    "Suggest differential diagnoses"
                ]
            else:
                return [
                    "Create SOAP from transcript",
                    "Generate assessment",
                    "Suggest treatment plan"
                ]
        elif current_tab == 2:  # Referral
            if has_content:
                return [
                    "Make more formal",
                    "Add urgency indicators",
                    "Include relevant history"
                ]
            else:
                return [
                    "Generate referral letter",
                    "Create specialist request",
                    "Draft consultation note"
                ]
        elif current_tab == 3:  # Letter
            if has_content:
                return [
                    "Improve tone and clarity",
                    "Make more empathetic",
                    "Simplify language"
                ]
            else:
                return [
                    "Draft patient letter",
                    "Create discharge summary",
                    "Write follow-up instructions"
                ]
        elif current_tab == 4:  # Chat
            if has_content:
                return [
                    "Clear chat history",
                    "Summarize our conversation",
                    "What else can you help with?"
                ]
            else:
                # Include tool examples if tools are enabled
                chat_config = SETTINGS.get("chat_interface", {})
                if chat_config.get("enable_tools", True):
                    return [
                        "Calculate BMI for 70kg, 175cm",
                        "Check drug interaction warfarin aspirin",
                        "What's 15 * 8 + 32?",
                        "What's the current time?",
                        "Calculate dosage: 25mg/kg for 30kg",
                        "Explain this medical term"
                    ]
                else:
                    return [
                        "What is this medication for?",
                        "Explain this medical term",
                        "Help me understand my diagnosis"
                    ]
        elif current_tab == 5:  # RAG
            if has_content:
                return [
                    "Clear RAG history",
                    "Find related documents",
                    "Search for similar cases"
                ]
            else:
                return [
                    "What is advance care planning?",
                    "Search for treatment protocols",
                    "Find patient education materials",
                    "Look up clinical guidelines",
                    "Search medication information",
                    "Find procedure documentation"
                ]
        return []

    def _focus_chat_input(self):
        """Focus the chat input field."""
        if hasattr(self, 'chat_ui') and self.chat_ui:
            self.chat_ui.focus_input()
