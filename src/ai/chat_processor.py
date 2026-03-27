"""
Chat Processor for Medical Assistant

Handles LLM interactions for conversational AI features including
multi-turn conversations, tool execution, and streaming responses.

Error Handling:
    - Raises ServiceUnavailableError: When AI provider circuit breaker is open
    - Uses CircuitBreaker pattern for provider resilience (5 failures = open)
    - Graceful degradation when MCP servers are unavailable
    - Tool execution errors captured and reported to user
    - Streaming callbacks receive error events on failure

Logging:
    - Uses structured logging via get_logger(__name__)
    - Logs include provider, model, message counts, and timing
    - Tool calls and results logged for debugging
    - MCP server health status logged

Thread Safety:
    - Conversation history protected by threading.Lock
    - MCP tool registration is thread-safe via mcp_manager
    - Streaming responses run on separate threads
    - Circuit breaker state is thread-safe
"""

import sqlite3
import threading
import tkinter as tk

from utils.structured_logging import get_logger

logger = get_logger(__name__)
import time
from typing import Dict, Any, Optional, Callable, TypedDict
from datetime import datetime

from settings.settings_manager import settings_manager
from ai.agents.chat import ChatAgent
from ai.agents.models import AgentTask
from ai.tools.tool_executor import ToolExecutor
from ai.tools.tool_registry import tool_registry
# Import to register built-in tools
import ai.tools.builtin_tools
import ai.tools.medical_tools
# MCP support
from ai.mcp.mcp_manager import mcp_manager, health_monitor
from ai.mcp.mcp_tool_wrapper import register_mcp_tools
# Provider constants
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA
)
# Resilience patterns
from utils.resilience import CircuitBreaker, CircuitState
from utils.exceptions import ServiceUnavailableError


class ChatContextData(TypedDict):
    """Typed structure for chat context extracted from UI tabs."""
    tab_name: str
    tab_index: int
    content: str
    content_length: int
    has_content: bool


class ToolInfo(TypedDict, total=False):
    """Typed structure for tool execution metadata."""
    tool_calls: Any  # List of tool call objects
    metadata: Any


from ai.chat_context_mixin import ChatContextMixin
from ai.chat_tools_mixin import ChatToolsMixin
from ai.chat_ui_mixin import ChatUIMixin


class ChatProcessor(ChatContextMixin, ChatToolsMixin, ChatUIMixin):
    """Processes chat messages and handles AI interactions.

    Composed from mixins following the ProcessingQueue pattern:
    - ChatContextMixin: Context extraction, prompt construction, history
    - ChatToolsMixin: Tool detection, MCP management, tool confirmation
    - ChatUIMixin: Chat display, typing indicators, clipboard operations
    """

    def __init__(self, app):
        """
        Initialize the chat processor.

        Args:
            app: Reference to the main application
        """
        self.app = app
        self.is_processing = False
        self.conversation_history = []

        # Typing indicator state
        self._typing_indicator_mark = None
        self._typing_animation_id = None
        self._typing_frames = ["⏳ Assistant is thinking", "⏳ Assistant is thinking.", "⏳ Assistant is thinking..", "⏳ Assistant is thinking..."]
        self._typing_frame_index = 0

        # Track embedded widgets in chat so they can be destroyed on clear
        self._chat_embedded_widgets = []

        # Circuit breaker for AI provider resilience
        # Opens after 5 consecutive failures, recovers after 60 seconds
        self._ai_circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=Exception,
            name="chat_ai_provider"
        )

        # Configuration from settings
        chat_config = settings_manager.get_chat_settings()
        self.max_context_length = chat_config.get("max_context_length", 8000)
        self.max_history_items = chat_config.get("max_history_items", 10)
        self.temperature = chat_config.get("temperature", 0.3)
        self.use_tools = chat_config.get("enable_tools", True)
        
        # Initialize tool executor first
        if self.use_tools:
            self.tool_executor = ToolExecutor(confirm_callback=self._confirm_tool_execution)
        else:
            self.tool_executor = None
            
        # Initialize MCP manager and register tools
        self._initialize_mcp()
        
        # Initialize chat agent after MCP tools are registered
        if self.use_tools:
            self.chat_agent = ChatAgent(tool_executor=self.tool_executor)
        else:
            self.chat_agent = None
        
    def process_message(self, user_message: str, callback: Optional[Callable] = None,
                        context_data: Optional[ChatContextData] = None):
        """
        Process a chat message from the user.

        Args:
            user_message: The user's input message
            callback: Optional callback to call when processing is complete
            context_data: Pre-extracted context from main thread (avoids
                          cross-thread Tkinter access and tab-switch race)
        """
        if self.is_processing:
            logger.warning("Chat processor is already processing a message")
            return

        # Run processing in a separate thread to avoid blocking UI
        thread = threading.Thread(
            target=self._process_message_async,
            args=(user_message, callback, context_data),
            daemon=True
        )
        thread.start()
        
    def _process_message_async(self, user_message: str, callback: Optional[Callable],
                               context_data: Optional[ChatContextData] = None):
        """Async processing of chat message."""
        try:
            self.is_processing = True

            # Use pre-extracted context if provided (avoids cross-thread
            # Tkinter access), otherwise fall back to local extraction
            if context_data is None:
                context_data = self._extract_context()

            # Check for special chat commands when in chat tab
            if context_data.get("tab_name") == "chat" and self._handle_chat_command(user_message):
                return  # Command was handled, no need to call AI

            # Show typing indicator while processing
            self._show_typing_indicator()

            # Add user message to history
            self._add_to_history("user", user_message)

            # Construct prompt for AI
            system_message, prompt = self._construct_prompt(user_message, context_data)

            # Get AI response (might include tool usage)
            ai_response, tool_info = self._get_ai_response_with_tools(
                prompt, system_message=system_message, context_data=context_data
            )

            # Hide typing indicator before showing response
            self._hide_typing_indicator()

            if ai_response:
                # Add AI response to history
                self._add_to_history("assistant", ai_response)

                # Process the response (apply changes if requested)
                self._process_ai_response(user_message, ai_response, context_data, tool_info)

            else:
                self.app.status_manager.error("Failed to get AI response")

        except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
            logger.error(f"Error processing chat message: {e}", exc_info=True)
            self.app.status_manager.error(f"Chat processing error: {str(e)}")
            # Hide typing indicator on error
            self._hide_typing_indicator()

        finally:
            self.is_processing = False

            # Call callback on main thread
            if callback:
                self.app.after(0, callback)
                
    def _get_ai_response_with_tools(self, prompt: str,
                                     system_message: str = None,
                                     context_data: Optional[ChatContextData] = None,
                                     ) -> tuple[Optional[str], Optional[ToolInfo]]:
        """Get response from AI provider, possibly using tools."""
        response_text, tool_info = self._get_ai_response(
            prompt, system_message=system_message, context_data=context_data
        )
        return response_text, tool_info
    
    def _get_ai_response(self, prompt: str, max_retries: int = 3,
                         system_message: str = None,
                         context_data: Optional[ChatContextData] = None,
                         ) -> tuple[Optional[str], Optional[ToolInfo]]:
        """Get response from AI provider with retry logic and circuit breaker.

        Args:
            prompt: The prompt to send to the AI
            max_retries: Maximum number of retry attempts (default: 3)
            system_message: Context-specific system message (falls back to generic)
            context_data: Pre-extracted context from the originating tab

        Returns:
            Tuple of (response_text, tool_info) or (None, None) on failure
        """
        # Check circuit breaker state first
        if self._ai_circuit_breaker.state == CircuitState.OPEN:
            logger.warning("AI circuit breaker is OPEN - service unavailable")
            self.app.status_manager.warning(
                "AI service temporarily unavailable. Please try again in a minute."
            )
            return None, None

        # Extract the actual user message from the prompt
        # The prompt contains system messages and context, but we need just the user's request
        user_message = None
        if "User Request: " in prompt:
            # Extract the user message from the constructed prompt
            parts = prompt.split("User Request: ", 1)
            if len(parts) > 1:
                user_message = parts[1].split("\n\n")[0].strip()

        # Check if we should use the chat agent with tools
        if user_message and self._should_use_tools(user_message):
            logger.info("Using chat agent with tools for this request")

            # Build context including document content and conversation history
            context_parts = []
            if context_data and context_data.get("has_content"):
                tab_name = context_data.get("tab_name", "document")
                content = context_data.get("content", "")
                context_parts.append(f"Current {tab_name.title()} Document Content:\n{content}")

            history_context = self.get_context_from_history(max_entries=3)
            if history_context:
                context_parts.append(f"Recent Conversation:\n{history_context}")

            task = AgentTask(
                task_description=user_message,
                context="\n\n".join(context_parts) if context_parts else None
            )

            # Execute with chat agent (has its own retry logic)
            response = self.chat_agent.execute(task)

            if response.success:
                # Record success in circuit breaker
                self._ai_circuit_breaker._on_success()

                # Log tool usage
                if response.tool_calls:
                    logger.info(f"Used {len(response.tool_calls)} tools")
                    for tool_call in response.tool_calls:
                        logger.info(f"Tool: {tool_call.tool_name}")

                # Debug log the response
                logger.debug(f"Chat agent response length: {len(response.result) if response.result else 0}")
                logger.debug(f"Response preview: {response.result[:200] if response.result else 'None'}...")

                tool_info = {
                    "tool_calls": response.tool_calls,
                    "metadata": response.metadata
                }
                return response.result, tool_info
            else:
                logger.error(f"Chat agent failed: {response.error}")
                # Fall back to regular AI (will be handled by the retry loop below)

        # Import AI functions
        from ai.ai import call_openai, call_ai

        # Get current AI provider setting
        provider = settings_manager.get_ai_provider().lower()
        # Use the context-specific system message, fall back to generic
        if not system_message:
            system_message = "You are a helpful medical AI assistant specialized in medical documentation and analysis."

        # Retry loop with exponential backoff
        last_exception = None
        for attempt in range(max_retries):
            try:
                if provider == PROVIDER_OPENAI:
                    model = settings_manager.get_nested("openai.model", "gpt-4")
                    response = call_openai(
                        model=model,
                        system_message=system_message,
                        prompt=prompt,
                        temperature=self.temperature
                    )
                else:
                    # Fallback to generic call_ai function
                    logger.warning(f"Unknown provider '{provider}', using fallback")
                    response = call_ai(
                        model="gpt-4",
                        system_message=system_message,
                        prompt=prompt,
                        temperature=self.temperature
                    )

                # If we get here, the call succeeded
                if response:
                    # Record success in circuit breaker
                    self._ai_circuit_breaker._on_success()
                    # Extract text from AIResult for consistency with chat agent path
                    response_text = response.text if hasattr(response, 'text') else str(response)
                    return response_text, None  # No tool info for regular AI calls
                else:
                    # Empty response, might be a transient issue
                    raise ValueError("Empty response from AI provider")

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check for rate limit or transient errors
                is_retryable = any(term in error_str for term in [
                    'rate limit', '429', 'timeout', 'connection',
                    'temporarily', 'overloaded', '503', '502', '500'
                ])

                if is_retryable and attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"AI request failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
                elif attempt < max_retries - 1:
                    # Non-retryable error but still have attempts left
                    # Try once more with minimal delay
                    logger.warning(
                        f"AI request failed (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(0.5)
                else:
                    # Final attempt failed - record failure in circuit breaker
                    self._ai_circuit_breaker._on_failure()
                    logger.error(
                        f"AI request failed after {max_retries} attempts: {e}",
                        exc_info=True
                    )

        return None, None
        
    def _process_ai_response(self, user_message: str, ai_response: str, context_data: ChatContextData, tool_info: Optional[ToolInfo] = None):
        """Process the AI response and apply changes if needed."""
        
        # Show the response to the user first
        self._show_ai_response(ai_response)
        
        # Special handling for chat tab - append conversation instead of replacing
        if context_data.get("tab_name") == "chat":
            self._append_to_chat_tab(user_message, ai_response, tool_info)
        else:
            # Check if user wants to apply changes to the document
            if self._should_apply_to_document(user_message, ai_response):
                # Check if auto-apply is enabled (default: True)
                chat_config = settings_manager.get_chat_settings()
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
                logger.info(f"AI Response received: {response[:200]}{'...' if len(response) > 200 else ''}")
                
                # Show brief notification in status bar
                self.app.status_manager.info("AI response processed and applied")

            except (tk.TclError, AttributeError) as e:
                logger.error(f"Error showing AI response notification: {e}")
                
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
        
    def _get_widget_for_tab(self, tab_index: int):
        """Map a tab index to its corresponding text widget.

        Uses the tab_index captured *before* the tab switch so that
        auto-apply targets the originating document, not the chat widget.
        """
        widget_map = {
            0: getattr(self.app, 'transcript_text', None),
            1: getattr(self.app, 'soap_text', None),
            2: getattr(self.app, 'referral_text', None),
            3: getattr(self.app, 'letter_text', None),
        }
        return widget_map.get(tab_index)

    def _apply_response_to_document(self, ai_response: str, context_data: ChatContextData):
        """Apply the AI response to the current document automatically."""

        def apply_changes():
            try:
                # Log the AI response for debugging
                logger.info(f"AI Response received: {ai_response[:200]}...")

                # Extract the actual content from the AI response
                content_to_apply = self._extract_content_from_response(ai_response)

                # Log extracted content
                logger.info(f"Extracted content length: {len(content_to_apply) if content_to_apply else 0}")
                if content_to_apply:
                    logger.info(f"Extracted content preview: {content_to_apply[:100]}...")

                # Look up the correct widget using tab_index captured before tab switch
                target_widget = self._get_widget_for_tab(context_data.get("tab_index", 0))
                if content_to_apply and target_widget:
                    # Automatically replace content without asking
                    target_widget.delete("1.0", "end")
                    target_widget.insert("1.0", content_to_apply)

                    # Show success message
                    tab_name = context_data.get("tab_name", "document").title()
                    self.app.status_manager.success(f"{tab_name} updated with AI response")

                    logger.info(f"Auto-applied AI response to {tab_name} tab")
                else:
                    logger.warning(f"No content to apply or no target widget. Content: {bool(content_to_apply)}, Widget: {bool(target_widget)}")
                    self.app.status_manager.warning("No content to apply to document")

            except (tk.TclError, AttributeError) as e:
                logger.error(f"Error applying AI response to document: {e}", exc_info=True)
                self.app.status_manager.error("Failed to apply changes")

        # Apply on main thread
        self.app.after(0, apply_changes)
        
    def _apply_response_with_confirmation(self, ai_response: str, context_data: ChatContextData):
        """Apply the AI response to the current document with user confirmation."""

        def apply_changes():
            try:
                # Extract the actual content from the AI response
                content_to_apply = self._extract_content_from_response(ai_response)

                # Look up the correct widget using tab_index captured before tab switch
                target_widget = self._get_widget_for_tab(context_data.get("tab_index", 0))
                if content_to_apply and target_widget:
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
                        target_widget.delete("1.0", "end")
                        target_widget.insert("1.0", content_to_apply)

                        self.app.status_manager.success(f"{tab_name} updated with AI response")
                    else:
                        self.app.status_manager.info("Changes not applied")
                else:
                    self.app.status_manager.warning("No content to apply to document")

            except (tk.TclError, AttributeError) as e:
                logger.error(f"Error applying AI response to document: {e}")
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
            "cleaned text:\n",
            "removed is as follows:\n",
            "as follows:\n",
            "following:\n",
            "below:\n"
        ]
        
        response_lower = ai_response.lower()
        
        for pattern in patterns_to_try:
            if pattern in response_lower:
                start_index = response_lower.find(pattern) + len(pattern)
                content = ai_response[start_index:].strip()
                
                # Remove leading "---" separators if present
                if content.startswith("---"):
                    content = content[3:].strip()
                    if content.startswith("\n"):
                        content = content[1:].strip()
                
                # Remove any trailing explanations or notes
                lines = content.split('\n')
                # Look for lines that seem like AI explanations rather than content
                content_lines = []
                for line in lines:
                    line_lower = line.lower().strip()
                    # Skip separator lines
                    if line.strip() == "---":
                        continue
                    if (line_lower.startswith(("note:", "explanation:", "i've", "this version", 
                                             "the changes", "summary:")) or
                        "changes made" in line_lower):
                        break  # Stop at explanation lines
                    content_lines.append(line)
                
                result = '\n'.join(content_lines).strip()
                # Remove trailing "---" if present
                if result.endswith("---"):
                    result = result[:-3].strip()
                
                return result
        
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
        
    def get_circuit_breaker_status(self) -> str:
        """Get the current circuit breaker status.

        Returns:
            String describing the circuit breaker state.
        """
        state = self._ai_circuit_breaker.state
        return state.value

    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker to closed state.

        Use this to recover from an open circuit after the underlying
        issue has been resolved (e.g., API key fixed, service restored).
        """
        self._ai_circuit_breaker.reset()
        logger.info("Chat AI circuit breaker manually reset")
        self.app.status_manager.success("AI service circuit breaker reset")

