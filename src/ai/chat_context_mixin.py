"""
Chat Context Mixin

Provides context extraction, prompt construction, and conversation
history management for ChatProcessor. Extracted to keep the main
processor focused on AI orchestration.
"""

import threading
import tkinter as tk
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from ai.chat_processor import ChatContextData

logger = get_logger(__name__)


class ChatContextMixin:
    """Context and history management methods for ChatProcessor."""

    def _extract_context(self) -> 'ChatContextData':
        """Fallback context extraction.

        WARNING: This method accesses Tkinter widgets, so it must only be
        called from the main thread. The preferred path is pre-extraction
        via AppChatMixin._extract_chat_context() which is passed as
        context_data to process_message().  This fallback returns empty
        context with a warning if called from a non-main thread.
        """
        context = {
            "tab_name": "",
            "tab_index": 0,
            "content": "",
            "content_length": 0,
            "has_content": False
        }

        # Guard: Tkinter widgets must only be accessed from the main thread
        if threading.current_thread() is not threading.main_thread():
            logger.warning(
                "_extract_context called from worker thread — returning empty context. "
                "Pass context_data to process_message() instead."
            )
            return context

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
                    # Truncate if too long
                    if len(content) > self.max_context_length:
                        content = content[:self.max_context_length] + "...[truncated]"
                    context["content"] = content
                    context["content_length"] = len(content)
                    context["has_content"] = bool(content)

        except (tk.TclError, AttributeError) as e:
            logger.error(f"Error extracting context: {e}")

        return context

    def _construct_prompt(self, user_message: str, context_data: 'ChatContextData') -> tuple[str, str]:
        """Construct the system message and prompt to send to the AI.

        Returns:
            Tuple of (system_message, prompt). The system_message is
            context-specific (e.g. SOAP-focused) and should be passed as the
            API system parameter. The prompt contains document content,
            conversation history, and the user request.
        """

        # Context-specific system message
        tab_name = context_data.get("tab_name", "unknown")

        system_messages = {
            "transcript": "You are an AI assistant helping with medical transcription analysis. You can help summarize, extract information, remove speaker labels, clean up formatting, and answer questions about the transcript content. When asked to modify text, provide the complete cleaned version.",
            "soap": "You are an AI assistant helping with SOAP note creation and improvement. You can help improve clarity, add medical detail, ensure proper medical documentation format, and fix any formatting issues. When modifying content, provide the complete updated version.",
            "referral": "You are an AI assistant helping with medical referral letters. You can help make them more professional, add urgency indicators, ensure proper referral format, and improve overall presentation. When editing, provide the complete improved version.",
            "letter": "You are an AI assistant helping with patient communication letters. You can help improve tone, clarity, empathy, and formatting while maintaining medical accuracy. When modifying content, provide the complete updated version.",
            "chat": "You are a helpful medical AI assistant. Engage in conversation, answer questions, provide medical information, and help with various healthcare-related queries. Do not modify any document content - just have a natural conversation."
        }

        system_msg = system_messages.get(tab_name, "You are an AI assistant helping with medical documentation.")

        # Build prompt (no embedded system message — it's returned separately)
        prompt_parts = [
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

        return system_msg, "\n".join(prompt_parts)

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
        logger.info("Chat conversation history cleared")

    def get_history(self) -> list:
        """Get conversation history."""
        return self.conversation_history.copy()

    def get_context_from_history(self, max_entries: int = 5) -> str:
        """Get context from recent conversation history."""
        if not self.conversation_history:
            return ""

        recent_history = self.conversation_history[-max_entries:]
        context_parts = []

        for entry in recent_history:
            role = entry["role"].title()
            message = entry["message"]
            context_parts.append(f"{role}: {message}")

        return "\n\n".join(context_parts)
