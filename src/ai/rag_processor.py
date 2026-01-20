"""
RAG Processor for Medical Assistant

Supports two modes:
1. N8N webhook mode (legacy) - sends queries to external N8N workflow
2. Local RAG mode - uses local document embeddings with Neon pgvector

The mode is determined by configuration:
- If NEON_DATABASE_URL is set, local RAG mode is preferred
- Falls back to N8N webhook mode if configured
"""

import threading
import requests
import json
import os
import uuid
import re
from typing import Optional, Callable, Tuple, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

from managers.data_folder_manager import data_folder_manager
from utils.timeout_config import get_timeout, get_timeout_tuple
from utils.http_client_manager import get_http_client_manager
from utils.structured_logging import get_logger
from utils.resilience import smart_retry
from utils.exceptions import APIError

logger = get_logger(__name__)

# Load environment variables
# Try loading from root .env first, then fall back to AppData .env
import pathlib
root_env = pathlib.Path(__file__).parent.parent.parent / '.env'
if root_env.exists():
    load_dotenv(dotenv_path=str(root_env))
else:
    load_dotenv(dotenv_path=str(data_folder_manager.env_file_path))


class RagProcessor:
    """Processes RAG queries via N8N webhook with security validation"""

    # Allowed URL schemes for webhook
    ALLOWED_SCHEMES = {'https', 'http'}

    # Maximum allowed response length (prevent memory exhaustion)
    MAX_RESPONSE_LENGTH = 100000  # 100KB

    # Maximum line length to prevent UI freeze
    MAX_LINE_LENGTH = 5000

    # Dangerous patterns to remove from responses
    DANGEROUS_PATTERNS = [
        # Script tags and event handlers (in case content is ever rendered in HTML context)
        (re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL), ''),
        (re.compile(r'<[^>]+on\w+\s*=', re.IGNORECASE), '<'),
        # HTML tags that could be problematic
        (re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL), ''),
        (re.compile(r'<object[^>]*>.*?</object>', re.IGNORECASE | re.DOTALL), ''),
        (re.compile(r'<embed[^>]*>', re.IGNORECASE), ''),
        # Control characters (except newline, tab, carriage return)
        (re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]'), ''),
        # ANSI escape sequences
        (re.compile(r'\x1b\[[0-9;]*[a-zA-Z]'), ''),
        # Null bytes
        (re.compile(r'\x00'), ''),
    ]

    # Blocked private IP ranges (SSRF protection)
    BLOCKED_IP_PATTERNS = [
        r'^127\.',                    # Localhost
        r'^10\.',                     # Private class A
        r'^172\.(1[6-9]|2[0-9]|3[01])\.', # Private class B
        r'^192\.168\.',               # Private class C
        r'^169\.254\.',               # Link-local
        r'^0\.',                      # Invalid
        r'^localhost$',               # Localhost hostname
        r'^::1$',                     # IPv6 localhost
        r'^fd[0-9a-f]{2}:',           # IPv6 private
    ]

    def __init__(self, app):
        """
        Initialize the RAG processor.

        Args:
            app: Reference to the main application
        """
        self.app = app
        self.is_processing = False

        # Check for local RAG mode (Neon database)
        self.neon_database_url = os.getenv("NEON_DATABASE_URL")
        self.use_local_rag = bool(self.neon_database_url)
        self._hybrid_retriever = None

        if self.use_local_rag:
            logger.info("Local RAG mode enabled (Neon database configured)")
        else:
            logger.info("N8N webhook mode (local RAG not configured)")

        # Typing indicator state for progress feedback
        self._typing_indicator_mark = None
        self._typing_animation_id = None
        self._typing_frame_index = 0
        self._current_indicator_type = None  # 'search' or 'generate'

        # Animation frames for different RAG stages
        self._search_frames = [
            "🔍 Searching documents",
            "🔍 Searching documents.",
            "🔍 Searching documents..",
            "🔍 Searching documents..."
        ]
        self._generate_frames = [
            "⏳ Generating response",
            "⏳ Generating response.",
            "⏳ Generating response..",
            "⏳ Generating response..."
        ]

        # Get N8N webhook configuration from environment
        raw_url = os.getenv("N8N_URL")
        self.n8n_auth_header = os.getenv("N8N_AUTHORIZATION_SECRET")

        # Validate and sanitize the webhook URL
        self.n8n_webhook_url = None
        if raw_url:
            is_valid, validated_url, error = self._validate_webhook_url(raw_url)
            if is_valid:
                self.n8n_webhook_url = validated_url
            else:
                logger.error(f"Invalid N8N_URL: {error}")
        else:
            if not self.use_local_rag:
                logger.warning("N8N_URL not found in environment variables")

        if not self.n8n_auth_header and not self.use_local_rag:
            logger.warning("N8N_AUTHORIZATION_SECRET not found in environment variables")

    def _get_hybrid_retriever(self):
        """Get or create hybrid retriever for local RAG mode."""
        if self._hybrid_retriever is None:
            try:
                from src.rag.hybrid_retriever import get_hybrid_retriever
                self._hybrid_retriever = get_hybrid_retriever()
            except Exception as e:
                logger.error(f"Failed to initialize hybrid retriever: {e}")
                return None
        return self._hybrid_retriever

    def _show_typing_indicator(self, indicator_type: str = 'search'):
        """Show animated typing indicator in RAG text widget.

        Args:
            indicator_type: 'search' for document search phase,
                          'generate' for AI response generation phase
        """
        def show():
            try:
                if not hasattr(self.app, 'rag_text'):
                    return

                rag_widget = self.app.rag_text
                self._current_indicator_type = indicator_type

                # Select appropriate frames based on type
                frames = self._search_frames if indicator_type == 'search' else self._generate_frames

                # If indicator already showing, just update text
                if self._typing_indicator_mark:
                    try:
                        rag_widget.delete(self._typing_indicator_mark, "end-1c")
                        self._typing_frame_index = 0
                        rag_widget.insert(self._typing_indicator_mark, frames[0], "typing_indicator")
                        return
                    except Exception:
                        pass

                # Mark the position where we insert the indicator
                self._typing_indicator_mark = rag_widget.index("end-1c")

                # Insert initial typing indicator
                self._typing_frame_index = 0
                rag_widget.insert("end", frames[0], "typing_indicator")
                rag_widget.tag_config("typing_indicator", foreground="#888888", font=("Arial", 10, "italic"))

                # Scroll to bottom
                rag_widget.see("end")

                # Start animation
                self._animate_typing_indicator()

            except Exception as e:
                logger.debug(f"Error showing typing indicator: {e}")

        # Execute on main thread
        self.app.after(0, show)

    def _animate_typing_indicator(self):
        """Animate the typing indicator with cycling dots."""
        def animate():
            try:
                if not self._typing_indicator_mark:
                    return

                if not hasattr(self.app, 'rag_text'):
                    return

                rag_widget = self.app.rag_text

                # Select appropriate frames based on current type
                frames = self._search_frames if self._current_indicator_type == 'search' else self._generate_frames

                # Delete old indicator text
                rag_widget.delete(self._typing_indicator_mark, "end-1c")

                # Cycle through frames
                self._typing_frame_index = (self._typing_frame_index + 1) % len(frames)

                # Insert new frame
                rag_widget.insert(self._typing_indicator_mark, frames[self._typing_frame_index], "typing_indicator")

                # Scroll to keep indicator visible
                rag_widget.see("end")

                # Schedule next animation (500ms interval)
                self._typing_animation_id = self.app.after(500, animate)

            except Exception as e:
                logger.debug(f"Error animating typing indicator: {e}")

        animate()

    def _hide_typing_indicator(self):
        """Remove typing indicator from RAG text widget."""
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
                if self._typing_indicator_mark and hasattr(self.app, 'rag_text'):
                    rag_widget = self.app.rag_text
                    try:
                        # Delete from mark to end
                        rag_widget.delete(self._typing_indicator_mark, "end")
                    except Exception:
                        pass
                    self._typing_indicator_mark = None

                self._typing_frame_index = 0
                self._current_indicator_type = None

            except Exception as e:
                logger.debug(f"Error hiding typing indicator: {e}")

        # Execute on main thread
        self.app.after(0, hide)

    def is_local_rag_available(self) -> bool:
        """Check if local RAG mode is available and configured.

        Returns:
            True if local RAG can be used
        """
        if not self.use_local_rag:
            return False

        try:
            retriever = self._get_hybrid_retriever()
            if retriever:
                stats = retriever.get_retrieval_stats()
                return stats.get("vector_store_available", False)
        except Exception:
            pass

        return False

    def get_rag_mode(self) -> str:
        """Get current RAG mode.

        Returns:
            'local' for local RAG, 'n8n' for webhook, 'none' if unconfigured
        """
        if self.use_local_rag and self.is_local_rag_available():
            return "local"
        elif self.n8n_webhook_url:
            return "n8n"
        return "none"

    @smart_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def _make_webhook_request(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any]
    ) -> requests.Response:
        """Make retryable HTTP POST request to webhook.

        Uses @smart_retry decorator to handle transient network errors
        with exponential backoff.

        Args:
            url: Webhook URL to call
            headers: HTTP headers
            payload: JSON payload to send

        Returns:
            Response object from the request

        Raises:
            APIError: On non-retryable errors
            requests.exceptions.RequestException: On network errors (may be retried)
        """
        session = get_http_client_manager().get_requests_session("rag")
        timeout = get_timeout_tuple("rag")

        response = session.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout
        )

        # Raise for server errors (5xx) to trigger retry
        # Client errors (4xx) should not be retried
        if response.status_code >= 500:
            response.raise_for_status()

        return response

    def _validate_webhook_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Validate webhook URL for security.

        Performs SSRF protection by blocking private IP ranges and
        validating URL format.

        Args:
            url: The URL to validate

        Returns:
            Tuple of (is_valid, sanitized_url, error_message)
        """
        if not url:
            return False, None, "URL is empty"

        url = url.strip()

        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
                return False, None, f"Invalid scheme: {parsed.scheme}. Must be http or https"

            # Check if hostname exists
            if not parsed.hostname:
                return False, None, "URL has no hostname"

            hostname = parsed.hostname.lower()

            # Check against blocked patterns (SSRF protection)
            for pattern in self.BLOCKED_IP_PATTERNS:
                if re.match(pattern, hostname, re.IGNORECASE):
                    return False, None, f"Blocked hostname: {hostname} (private/local address)"

            # Validate port if specified
            if parsed.port:
                if parsed.port < 1 or parsed.port > 65535:
                    return False, None, f"Invalid port: {parsed.port}"

            # Reconstruct URL to ensure it's properly formatted
            # This also removes any extraneous components
            sanitized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                sanitized += f"?{parsed.query}"

            logger.debug(f"Validated webhook URL: {sanitized}")
            return True, sanitized, None

        except Exception as e:
            return False, None, f"URL parsing error: {str(e)}"
            
    def process_message(self, user_message: str, callback: Optional[Callable] = None):
        """
        Process a RAG query from the user.

        Automatically selects between local RAG mode and N8N webhook mode
        based on configuration.

        Args:
            user_message: The user's query
            callback: Optional callback to call when processing is complete
        """
        if self.is_processing:
            logger.warning("RAG processor is already processing a message")
            return

        # Check available RAG mode
        rag_mode = self.get_rag_mode()

        if rag_mode == "none":
            self._display_error(
                "No RAG system configured. Please either:\n"
                "• Set NEON_DATABASE_URL for local RAG mode\n"
                "• Set N8N_URL for webhook mode"
            )
            if callback:
                callback()
            return

        # Run processing in a separate thread to avoid blocking UI
        if rag_mode == "local":
            thread = threading.Thread(
                target=self._process_message_local,
                args=(user_message, callback),
                daemon=True
            )
        else:
            thread = threading.Thread(
                target=self._process_message_async,
                args=(user_message, callback),
                daemon=True
            )
        thread.start()

    def _process_message_local(self, user_message: str, callback: Optional[Callable]):
        """Process RAG query using local vector database.

        Args:
            user_message: The user's query
            callback: Optional callback when processing is complete
        """
        try:
            self.is_processing = True

            # Add user message to RAG tab
            self._add_message_to_rag_tab("User", user_message)

            # Show search progress indicator
            self._show_typing_indicator('search')

            # Get hybrid retriever
            retriever = self._get_hybrid_retriever()
            if not retriever:
                self._hide_typing_indicator()
                self._display_error("Failed to initialize RAG retriever.")
                return

            logger.info(f"Processing local RAG query: {user_message[:100]}...")

            # Perform hybrid search
            from src.rag.models import RAGQueryRequest
            request = RAGQueryRequest(
                query=user_message,
                top_k=5,
                use_graph_search=True,
                similarity_threshold=0.3,  # Lower threshold - scores typically 0.3-0.6
            )

            response = retriever.search(request)

            if not response.results:
                # Hide indicator before showing message
                self._hide_typing_indicator()
                output = (
                    "I couldn't find any relevant information in the document database "
                    "for your query. Try uploading more documents or rephrasing your question."
                )
            else:
                # Update indicator to show we're generating the response
                self._show_typing_indicator('generate')
                # Generate AI response using retrieved context
                output = self._generate_rag_response(user_message, response)

            # Hide indicator before adding response
            self._hide_typing_indicator()

            # Add response to RAG tab
            self._add_message_to_rag_tab("RAG Assistant", output)

            logger.info(f"Local RAG query completed: {response.total_results} results in {response.processing_time_ms:.0f}ms")

        except Exception as e:
            error_msg = f"Error processing local RAG query: {str(e)}"
            logger.error(error_msg)
            self._hide_typing_indicator()  # Cleanup on error
            self._display_error(error_msg)

        finally:
            self._hide_typing_indicator()  # Ensure cleanup
            self.is_processing = False
            if callback:
                self.app.after(0, callback)

    def _generate_rag_response(self, query: str, response) -> str:
        """Generate AI response using retrieved document context.

        Args:
            query: Original user query
            response: RAGQueryResponse from hybrid retriever

        Returns:
            AI-generated response based on document context
        """
        from ai.ai import call_openai
        from settings.settings_manager import settings_manager

        # Build context from retrieved documents
        context_parts = []
        sources = []
        for i, result in enumerate(response.results, 1):
            sources.append(f"Source {i}: {result.document_filename}")
            context_parts.append(f"[Document {i}: {result.document_filename}]\n{result.chunk_text}")
            if result.related_entities:
                entities = ", ".join(result.related_entities[:5])
                context_parts.append(f"Related concepts: {entities}")
            context_parts.append("")

        context_text = "\n".join(context_parts)

        # Build the prompt for the LLM
        system_message = """You are a helpful medical AI assistant. Answer the user's question based ONLY on the provided document context.

Guidelines:
- Provide clear, well-organized answers with proper formatting
- Use bullet points and headers to organize information when appropriate
- If the context doesn't contain enough information to fully answer, say so
- Cite which document source(s) your answer comes from
- Be concise but thorough
- Use medical terminology appropriately"""

        prompt = f"""Based on the following document excerpts, please answer this question:

**Question:** {query}

---
**Document Context:**

{context_text}
---

Please provide a comprehensive answer based on the above context. If you cite specific information, indicate which source document it came from."""

        try:
            # Call the AI to generate a response
            model = settings_manager.get_nested("openai.model", "gpt-4")
            temperature = settings_manager.get_nested("temperature_settings.chat_temperature", 0.3)

            logger.info(f"Generating RAG response with {model}")

            ai_response = call_openai(
                model=model,
                system_message=system_message,
                prompt=prompt,
                temperature=temperature
            )

            if ai_response and hasattr(ai_response, 'text'):
                response_text = ai_response.text
            elif ai_response:
                response_text = str(ai_response)
            else:
                # Fallback to formatted results if AI call fails
                return self._format_local_rag_response(query, response)

            # Add sources footer
            sources_list = "\n".join(f"- {s}" for s in sources)
            response_text += f"\n\n---\n**Sources:**\n{sources_list}\n\n*Search completed in {response.processing_time_ms:.0f}ms*"

            return response_text

        except Exception as e:
            logger.error(f"Failed to generate AI response: {e}")
            # Fallback to formatted results
            return self._format_local_rag_response(query, response)

    def _format_local_rag_response(self, query: str, response) -> str:
        """Format local RAG response for display (fallback when AI generation fails).

        Args:
            query: Original user query
            response: RAGQueryResponse from hybrid retriever

        Returns:
            Formatted response string
        """
        parts = []

        # Add summary line
        parts.append(f"Found **{response.total_results} relevant passages** in your documents.\n")

        # Add context from results
        for i, result in enumerate(response.results, 1):
            parts.append(f"### Source {i}: {result.document_filename}")
            parts.append(f"*Relevance: {result.combined_score:.0%}*\n")

            # Truncate long chunks for display
            chunk_preview = result.chunk_text
            if len(chunk_preview) > 500:
                chunk_preview = chunk_preview[:500] + "..."

            parts.append(chunk_preview)

            if result.related_entities:
                entities = ", ".join(result.related_entities[:5])
                parts.append(f"\n**Related concepts:** {entities}")

            parts.append("")  # Blank line between results

        # Add processing time
        parts.append(f"\n---\n*Search completed in {response.processing_time_ms:.0f}ms*")

        return "\n".join(parts)
        
    def _process_message_async(self, user_message: str, callback: Optional[Callable]):
        """Async processing of RAG query via N8N webhook."""
        try:
            self.is_processing = True

            # Add user message to RAG tab
            self._add_message_to_rag_tab("User", user_message)

            # Show search progress indicator
            self._show_typing_indicator('search')

            # Make request to N8N webhook
            try:
                headers = {
                    "Content-Type": "application/json"
                }

                # Add authorization header if provided
                if self.n8n_auth_header:
                    # Remove quotes if present
                    auth_value = self.n8n_auth_header.strip("'\"")
                    headers["Authorization"] = auth_value

                # Prepare request payload with sessionId
                # Generate a session ID - you can make this persistent per user session if needed
                session_id = getattr(self, 'session_id', None)
                if not session_id:
                    self.session_id = str(uuid.uuid4())
                    session_id = self.session_id

                payload = {
                    "chatInput": user_message,
                    "sessionId": session_id
                }

                logger.info(f"Sending RAG query to N8N webhook: {self.n8n_webhook_url}")
                logger.debug(f"Payload: {payload}")

                # Use retryable HTTP method with automatic retry on transient errors
                response = self._make_webhook_request(
                    self.n8n_webhook_url,
                    headers,
                    payload
                )

                # Check for client errors (4xx) - these weren't raised in _make_webhook_request
                response.raise_for_status()

                # Update indicator to show response generation phase
                self._show_typing_indicator('generate')

                # Log raw response for debugging
                logger.info(f"Response status code: {response.status_code}")
                logger.info(f"Response headers: {response.headers}")
                response_text = response.text
                logger.info(f"Raw response: {response_text[:500]}...")  # Log first 500 chars

                # Parse response
                if not response_text or response_text.strip() == "":
                    logger.warning("Empty response from N8N webhook - the webhook may need to be configured to return data")
                    output = "The RAG system processed your request but didn't return any data. Please check the N8N workflow configuration to ensure it returns a response."
                else:
                    try:
                        response_data = response.json()

                        # Handle the expected response format
                        # Example: [{"output": "response text"}]
                        if isinstance(response_data, list) and len(response_data) > 0:
                            output = response_data[0].get("output", "No response received from RAG system.")
                        elif isinstance(response_data, dict):
                            output = response_data.get("output", "No response received from RAG system.")
                        else:
                            output = "Unexpected response format from RAG system."
                    except json.JSONDecodeError:
                        # If it's not JSON, just use the text response
                        output = f"RAG Response: {response_text}"

                # Hide indicator before adding response
                self._hide_typing_indicator()

                # Add response to RAG tab
                self._add_message_to_rag_tab("RAG Assistant", output)

            except requests.exceptions.Timeout:
                self._hide_typing_indicator()  # Cleanup on error
                error_msg = "Request timed out. The RAG system took too long to respond."
                logger.error(error_msg)
                self._display_error(error_msg)

            except requests.exceptions.RequestException as e:
                self._hide_typing_indicator()  # Cleanup on error
                error_msg = f"Error connecting to RAG system: {str(e)}"
                logger.error(error_msg)
                self._display_error(error_msg)

            except json.JSONDecodeError as e:
                self._hide_typing_indicator()  # Cleanup on error
                error_msg = f"Error parsing RAG response: {str(e)}"
                logger.error(error_msg)
                self._display_error(error_msg)

        except Exception as e:
            self._hide_typing_indicator()  # Cleanup on error
            error_msg = f"Unexpected error in RAG processor: {str(e)}"
            logger.error(error_msg)
            self._display_error(error_msg)

        finally:
            self._hide_typing_indicator()  # Ensure cleanup
            self.is_processing = False
            if callback:
                self.app.after(0, callback)
                
    def _add_message_to_rag_tab(self, sender: str, message: str):
        """Add a message to the RAG tab."""
        if not hasattr(self.app, 'rag_text'):
            return
            
        def update_ui():
            # Add timestamp
            timestamp = datetime.now().strftime("%I:%M %p")
            
            # Get current position
            self.app.rag_text.mark_set("insert_start", "end")
            
            # Insert sender name with timestamp
            self.app.rag_text.insert("end", f"{sender} ({timestamp}):\n", "sender")
            
            # If this is from the RAG Assistant, render markdown and add copy button
            if sender == "RAG Assistant":
                # Store the response start position
                response_start = self.app.rag_text.index("end-1c")
                self._render_markdown(message)
                response_end = self.app.rag_text.index("end-1c")
                
                # Add copy button
                self._add_copy_button(message)
            else:
                # Insert plain message for user messages
                self.app.rag_text.insert("end", f"{message}\n\n", "message")
            
            # Add separator
            self.app.rag_text.insert("end", "-" * 50 + "\n\n")
            
            # Configure tags for styling
            self.app.rag_text.tag_config("sender", font=("Arial", 10, "bold"))
            self.app.rag_text.tag_config("message", font=("Arial", 10))
            
            # Scroll to bottom
            self.app.rag_text.see("end")
            
        # Update UI in main thread
        self.app.after(0, update_ui)
        
    def _sanitize_response(self, text: str) -> str:
        """Sanitize API response to prevent injection attacks.

        Args:
            text: Raw response text from API

        Returns:
            Sanitized text safe for display
        """
        if not text:
            return ""

        # Truncate excessively long responses
        if len(text) > self.MAX_RESPONSE_LENGTH:
            text = text[:self.MAX_RESPONSE_LENGTH] + "\n\n[Response truncated due to length]"
            logger.warning(f"Response truncated from {len(text)} to {self.MAX_RESPONSE_LENGTH} chars")

        # Apply dangerous pattern removal
        for pattern, replacement in self.DANGEROUS_PATTERNS:
            text = pattern.sub(replacement, text)

        # Truncate excessively long lines to prevent UI freeze
        lines = text.split('\n')
        sanitized_lines = []
        for line in lines:
            if len(line) > self.MAX_LINE_LENGTH:
                line = line[:self.MAX_LINE_LENGTH] + "... [line truncated]"
            sanitized_lines.append(line)

        return '\n'.join(sanitized_lines)

    # Pre-compiled regex patterns for markdown rendering (class-level for efficiency)
    _BOLD_PATTERN = re.compile(r'\*\*(.*?)\*\*')
    _NUMBERED_LIST_PATTERN = re.compile(r'^\s*\d+\.\s')

    def _render_markdown(self, markdown_text: str):
        """Render markdown text with basic formatting in the text widget.

        Optimizations:
        - Pre-compiled regex patterns at class level
        - Batch inserts where possible
        - Early detection of plain text lines
        """
        # Sanitize input before rendering
        markdown_text = self._sanitize_response(markdown_text)

        lines = markdown_text.split('\n')
        text_widget = self.app.rag_text  # Local reference for faster access

        # Batch plain text lines for fewer insert calls
        plain_buffer = []

        def flush_plain_buffer():
            """Flush accumulated plain text."""
            nonlocal plain_buffer
            if plain_buffer:
                text_widget.insert("end", '\n'.join(plain_buffer) + "\n", "message")
                plain_buffer = []

        for line in lines:
            # Headers - check in order of likelihood (h2/h3 more common than h1)
            if line.startswith('#'):
                flush_plain_buffer()
                if line.startswith('### '):
                    text_widget.insert("end", line[4:] + "\n", "h3")
                elif line.startswith('## '):
                    text_widget.insert("end", line[3:] + "\n", "h2")
                elif line.startswith('# '):
                    text_widget.insert("end", line[2:] + "\n", "h1")
                else:
                    plain_buffer.append(line)

            # Bold text - check for ** before doing regex
            elif '**' in line:
                flush_plain_buffer()
                parts = self._BOLD_PATTERN.split(line)
                for i, part in enumerate(parts):
                    if part:  # Skip empty strings
                        if i % 2 == 0:
                            text_widget.insert("end", part)
                        else:
                            text_widget.insert("end", part, "bold")
                text_widget.insert("end", "\n")

            # Bullet points
            elif line.lstrip().startswith(('- ', '* ')):
                flush_plain_buffer()
                stripped = line.lstrip()
                indent = len(line) - len(stripped)
                bullet_text = stripped[2:]
                text_widget.insert("end", " " * indent + "• " + bullet_text + "\n", "bullet")

            # Numbered lists
            elif self._NUMBERED_LIST_PATTERN.match(line):
                flush_plain_buffer()
                text_widget.insert("end", line + "\n", "numbered")

            # Code blocks (simple)
            elif line.lstrip().startswith('```'):
                flush_plain_buffer()
                text_widget.insert("end", line + "\n", "code")

            # Regular text - accumulate for batch insert
            else:
                plain_buffer.append(line)

        # Flush any remaining plain text
        flush_plain_buffer()

        # Add an extra newline at the end
        text_widget.insert("end", "\n")
        
        # Configure markdown tags
        self.app.rag_text.tag_config("h1", font=("Arial", 16, "bold"), spacing3=5)
        self.app.rag_text.tag_config("h2", font=("Arial", 14, "bold"), spacing3=4)
        self.app.rag_text.tag_config("h3", font=("Arial", 12, "bold"), spacing3=3)
        self.app.rag_text.tag_config("bold", font=("Arial", 10, "bold"))
        self.app.rag_text.tag_config("bullet", lmargin1=20, lmargin2=30)
        self.app.rag_text.tag_config("numbered", lmargin1=20, lmargin2=30)
        self.app.rag_text.tag_config("code", font=("Courier", 10), background="#f0f0f0", relief="solid", borderwidth=1)
        
    def _add_copy_button(self, response_text: str):
        """Add a copy button for the response."""
        import tkinter as tk
        import ttkbootstrap as ttk
        
        # Add some space before the button
        self.app.rag_text.insert("end", "  ")
        
        # Create frame for button
        button_frame = ttk.Frame(self.app.rag_text)
        button_frame.configure(cursor="arrow")
        
        # Create copy button
        copy_btn = ttk.Button(
            button_frame,
            text="Copy",
            bootstyle="secondary-link",
            command=lambda: self._copy_to_clipboard(response_text)
        )
        copy_btn.pack(padx=2)
        
        # Add tooltip
        from ui.tooltip import ToolTip
        ToolTip(copy_btn, "Copy this response to clipboard")
        
        # Create window for button frame in text widget
        self.app.rag_text.window_create("end-1c", window=button_frame)
        self.app.rag_text.insert("end", "\n\n")
        
    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        try:
            # Clear clipboard and append new text
            self.app.clipboard_clear()
            self.app.clipboard_append(text)
            self.app.update()  # Required to finalize clipboard operation
            
            # Show brief success message
            if hasattr(self.app, 'status_manager'):
                self.app.status_manager.success("Response copied to clipboard")
            logger.info("RAG response copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            if hasattr(self.app, 'status_manager'):
                self.app.status_manager.error("Failed to copy response")
        
    def _display_error(self, error_message: str):
        """Display an error message in the RAG tab."""
        self._add_message_to_rag_tab("System Error", error_message)
        
    def clear_history(self):
        """Clear the RAG conversation history."""
        if hasattr(self.app, 'rag_text'):
            def clear_ui():
                self.app.rag_text.delete("1.0", "end")
                # Re-add welcome message
                self.app.rag_text.insert("1.0", "Welcome to the RAG Document Search!\n\n")
                self.app.rag_text.insert("end", "This interface allows you to search your document database:\n")
                self.app.rag_text.insert("end", "• Query documents stored in your RAG database\n")
                self.app.rag_text.insert("end", "• Get relevant information from your knowledge base\n")
                self.app.rag_text.insert("end", "• Search through previously uploaded documents\n\n")
                self.app.rag_text.insert("end", "Type your question in the AI Assistant chat box below to search your documents!\n")
                self.app.rag_text.insert("end", "="*50 + "\n\n")
                
                # Configure initial styling
                self.app.rag_text.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                self.app.rag_text.tag_add("welcome", "1.0", "9.end")
                
            self.app.after(0, clear_ui)