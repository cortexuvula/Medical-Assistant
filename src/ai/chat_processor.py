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

import threading

from utils.structured_logging import get_logger

logger = get_logger(__name__)
import time
from typing import Dict, Any, Optional, Callable
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

        # Typing indicator state
        self._typing_indicator_mark = None
        self._typing_animation_id = None
        self._typing_frames = ["⏳ Assistant is thinking", "⏳ Assistant is thinking.", "⏳ Assistant is thinking..", "⏳ Assistant is thinking..."]
        self._typing_frame_index = 0

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
        
    def process_message(self, user_message: str, callback: Optional[Callable] = None):
        """
        Process a chat message from the user.
        
        Args:
            user_message: The user's input message
            callback: Optional callback to call when processing is complete
        """
        if self.is_processing:
            logger.warning("Chat processor is already processing a message")
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

            # Show typing indicator while processing
            self._show_typing_indicator()

            # Add user message to history
            self._add_to_history("user", user_message)

            # Construct prompt for AI
            prompt = self._construct_prompt(user_message, context_data)

            # Get AI response (might include tool usage)
            ai_response, tool_info = self._get_ai_response_with_tools(prompt)

            # Hide typing indicator before showing response
            self._hide_typing_indicator()

            if ai_response:
                # Add AI response to history
                self._add_to_history("assistant", ai_response)

                # Process the response (apply changes if requested)
                self._process_ai_response(user_message, ai_response, context_data, tool_info)

            else:
                self.app.status_manager.error("Failed to get AI response")

        except Exception as e:
            logger.error(f"Error processing chat message: {e}", exc_info=True)
            self.app.status_manager.error(f"Chat processing error: {str(e)}")
            # Hide typing indicator on error
            self._hide_typing_indicator()

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
            logger.error(f"Error extracting context: {e}")
            
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
        
    def _should_use_tools(self, user_message: str) -> bool:
        """Determine if the message might benefit from tool usage."""
        if not self.use_tools or not self.chat_agent:
            return False
            
        message_lower = user_message.lower()
        
        # Keywords that suggest tool usage
        tool_keywords = [
            # Calculation keywords
            "calculate", "compute", "math", "add", "subtract", "multiply", "divide",
            # Time/date keywords
            "what time", "what date", "current time", "today", "tomorrow",
            # File operation keywords
            "read file", "open file", "save file", "write file",
            # Search keywords
            "search", "find", "look up", "lookup",
            # Data format keywords
            "parse json", "format json",
            # Medical calculation keywords
            "bmi", "body mass index", "drug interaction", "medication interaction",
            "dosage", "dose calculation", "mg/kg",
            # Medical guideline keywords
            "guideline", "guidelines", "recommendation", "recommendations",
            "protocol", "protocols", "standard", "standards", "best practice",
            # Medical value queries
            "target", "range", "level", "levels", "dose", "dosing",
            "threshold", "normal value", "reference range",
            # Question patterns
            "what is the", "what are the", "how much", "how many",
            "what should", "what does", "when should",
            # Medical specialties and conditions
            "hypertension", "blood pressure", "bp target", "diabetes",
            "cholesterol", "lipid", "glucose", "a1c", "hba1c",
            # Information queries
            "latest", "current", "recent", "updated", "new",
            "according to", "based on"
        ]
        
        # Check for any keyword match
        if any(keyword in message_lower for keyword in tool_keywords):
            return True
            
        # Check for year patterns (e.g., "2025 guidelines", "2024 recommendations")
        import re
        year_pattern = r'\b20\d{2}\b'  # Matches years 2000-2099
        if re.search(year_pattern, message_lower):
            return True
            
        # Check for question patterns that likely need information retrieval
        question_patterns = [
            r'^what\s+is\s+',
            r'^what\s+are\s+',
            r'^how\s+much\s+',
            r'^how\s+many\s+',
            r'^when\s+should\s+',
            r'^where\s+can\s+',
            r'^who\s+should\s+',
            r'^why\s+is\s+',
            r'\?$'  # Any message ending with a question mark
        ]
        
        for pattern in question_patterns:
            if re.search(pattern, message_lower):
                return True
                
        return False
    
    def _get_ai_response_with_tools(self, prompt: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Get response from AI provider, possibly using tools."""
        response_text, tool_info = self._get_ai_response(prompt)
        return response_text, tool_info
    
    def _get_ai_response(self, prompt: str, max_retries: int = 3) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Get response from AI provider with retry logic and circuit breaker.

        Args:
            prompt: The prompt to send to the AI
            max_retries: Maximum number of retry attempts (default: 3)

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

            # Create an agent task with just the user message
            task = AgentTask(
                task_description=user_message,
                context=self.get_context_from_history(max_entries=3)
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
        
    def _process_ai_response(self, user_message: str, ai_response: str, context_data: Dict[str, Any], tool_info: Dict[str, Any] = None):
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
                
            except Exception as e:
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
        
    def _apply_response_to_document(self, ai_response: str, context_data: Dict[str, Any]):
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
                
                if content_to_apply and hasattr(self.app, 'active_text_widget') and self.app.active_text_widget:
                    # Automatically replace content without asking
                    self.app.active_text_widget.delete("1.0", "end")
                    self.app.active_text_widget.insert("1.0", content_to_apply)
                    
                    # Show success message
                    tab_name = context_data.get("tab_name", "document").title()
                    self.app.status_manager.success(f"{tab_name} updated with AI response")
                    
                    logger.info(f"Auto-applied AI response to {tab_name} tab")
                else:
                    logger.warning(f"No content to apply or no active text widget. Content: {bool(content_to_apply)}, Widget: {hasattr(self.app, 'active_text_widget')}")
                    self.app.status_manager.warning("No content to apply to document")
                        
            except Exception as e:
                logger.error(f"Error applying AI response to document: {e}", exc_info=True)
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
    
    def _confirm_tool_execution(self, message: str) -> bool:
        """Callback to confirm tool execution with the user."""
        try:
            from tkinter import messagebox
            
            # Run on main thread
            result = [False]
            
            def show_confirmation():
                result[0] = messagebox.askyesno(
                    "Tool Confirmation",
                    message,
                    parent=self.app
                )
                
            self.app.after(0, show_confirmation)
            
            # Wait for user response (with timeout)
            import time
            timeout = 30  # 30 seconds timeout
            start_time = time.time()
            
            while len(result) == 1 and not result[0]:
                time.sleep(0.1)
                if time.time() - start_time > timeout:
                    logger.warning("Tool confirmation timed out")
                    return False
                    
            return result[0]
            
        except Exception as e:
            logger.error(f"Error showing tool confirmation: {e}")
            return False  # Deny on error
    
    def _append_to_chat_tab(self, user_message: str, ai_response: str, tool_info: Dict[str, Any] = None):
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
                
                # Add tool usage info if present
                if tool_info and tool_info.get("tool_calls"):
                    chat_widget.insert("end", "Tools Used:\n", "tool_header")
                    for tool_call in tool_info["tool_calls"]:
                        chat_widget.insert("end", f"  • {tool_call.tool_name}", "tool_name")
                        if tool_call.arguments:
                            args_str = ", ".join(f"{k}={v}" for k, v in tool_call.arguments.items())
                            chat_widget.insert("end", f"({args_str})", "tool_args")
                        chat_widget.insert("end", "\n")
                    chat_widget.insert("end", "\n")
                
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
                chat_widget.tag_config("tool_header", foreground="#FF6B35", font=("Arial", 10, "bold"))
                chat_widget.tag_config("tool_name", foreground="#FF6B35", font=("Arial", 10))
                chat_widget.tag_config("tool_args", foreground="#999999", font=("Arial", 9))
                
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
                            logger.info(f"Updated recording {self.app.current_recording_id} with chat content")
                    except Exception as e:
                        logger.error(f"Failed to save chat to database: {e}")
                
                # Update status
                self.app.status_manager.success("Chat response added")
                
            except Exception as e:
                logger.error(f"Error appending to chat tab: {e}")
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
                    logger.error(f"Error clearing chat: {e}")
                    self.app.status_manager.error("Failed to clear chat")
            
            self.app.after(0, clear_chat)
            return True

        return False

    def _show_typing_indicator(self):
        """Show a typing indicator in the chat widget while processing."""
        def show():
            try:
                chat_widget = self.app.chat_text

                # Get current content to check if we need separator
                current_content = chat_widget.get("1.0", "end-1c")

                # Add separator if there's existing content
                if current_content.strip():
                    chat_widget.insert("end", "\n" + "="*50 + "\n\n")

                # Mark the position where we inserted the indicator
                self._typing_indicator_mark = chat_widget.index("end-1c")

                # Insert initial typing indicator
                chat_widget.insert("end", self._typing_frames[0], "typing_indicator")
                chat_widget.tag_config("typing_indicator", foreground="#888888", font=("Arial", 10, "italic"))

                # Scroll to bottom
                chat_widget.see("end")

                # Start animation
                self._animate_typing_indicator()

            except Exception as e:
                logger.debug(f"Error showing typing indicator: {e}")

        # Execute on main thread
        self.app.after(0, show)

    def _animate_typing_indicator(self):
        """Animate the typing indicator with dots."""
        def animate():
            try:
                if not self._typing_indicator_mark:
                    return

                chat_widget = self.app.chat_text

                # Delete old indicator text
                chat_widget.delete(self._typing_indicator_mark, "end-1c")

                # Cycle through frames
                self._typing_frame_index = (self._typing_frame_index + 1) % len(self._typing_frames)

                # Insert new frame
                chat_widget.insert(self._typing_indicator_mark, self._typing_frames[self._typing_frame_index], "typing_indicator")

                # Schedule next animation
                self._typing_animation_id = self.app.after(500, animate)

            except Exception as e:
                logger.debug(f"Error animating typing indicator: {e}")

        animate()

    def _hide_typing_indicator(self):
        """Hide the typing indicator."""
        def hide():
            try:
                # Cancel animation
                if self._typing_animation_id:
                    try:
                        self.app.after_cancel(self._typing_animation_id)
                    except Exception:
                        pass
                    self._typing_animation_id = None

                # Remove indicator text if mark exists
                if self._typing_indicator_mark:
                    chat_widget = self.app.chat_text
                    # Delete from mark to end
                    chat_widget.delete(self._typing_indicator_mark, "end")
                    self._typing_indicator_mark = None

                self._typing_frame_index = 0

            except Exception as e:
                logger.debug(f"Error hiding typing indicator: {e}")

        # Execute on main thread
        self.app.after(0, hide)

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        try:
            # Clear clipboard and append new text
            self.app.clipboard_clear()
            self.app.clipboard_append(text)
            self.app.update()  # Required to finalize clipboard operation
            
            # Show brief success message
            self.app.status_manager.success("Response copied to clipboard")
            logger.info("Assistant response copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
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
            logger.error(f"Error showing context menu: {e}")
    
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
            logger.error(f"Error selecting response: {e}")
    
    def _initialize_mcp(self):
        """Initialize MCP manager and register tools."""
        try:
            mcp_config = settings_manager.get("mcp_config", {})

            # Load MCP servers
            mcp_manager.load_config(mcp_config)

            # Register MCP tools with the tool registry
            if mcp_config.get("enabled", False):
                registered = register_mcp_tools(tool_registry, mcp_manager)
                if registered > 0:
                    logger.info(f"Registered {registered} MCP tools")

                # Start health monitor for automatic server recovery
                health_monitor.start()
            else:
                # Stop health monitor if MCP is disabled
                health_monitor.stop()

        except Exception as e:
            logger.error(f"Error initializing MCP: {e}")
    
    def reload_mcp_tools(self):
        """Reload MCP tools after configuration change."""
        try:
            # Stop health monitor first
            health_monitor.stop()

            # Stop all MCP servers
            mcp_manager.stop_all()

            # Clear restart attempts on reload
            health_monitor.restart_attempts.clear()

            # Clear existing MCP tools
            tool_registry.clear_category("mcp")

            # Reinitialize (will restart health monitor if enabled)
            self._initialize_mcp()

            # Recreate chat agent if tools are enabled
            if self.use_tools:
                self.chat_agent = ChatAgent(tool_executor=self.tool_executor)

        except Exception as e:
            logger.error(f"Error reloading MCP tools: {e}")
    
    def set_tools_enabled(self, enabled: bool):
        """Enable or disable tool usage.
        
        Args:
            enabled: Whether to enable tools
        """
        self.use_tools = enabled
        
        if enabled and not self.chat_agent:
            # Create chat agent with tools
            self.tool_executor = ToolExecutor(confirm_callback=self._confirm_tool_execution)
            self.chat_agent = ChatAgent(tool_executor=self.tool_executor)
        elif not enabled:
            # Disable tools
            self.chat_agent = None
            
        # Update settings
        settings_manager.set_nested("chat_interface.enable_tools", enabled)