"""
RAG Processor for Medical Assistant

Provides local RAG (Retrieval-Augmented Generation) functionality using
Neon pgvector for vector storage and Neo4j for knowledge graph queries.

The RAG system is enabled when NEON_DATABASE_URL is configured in the environment.
"""

import threading
import json
import os
import uuid
import re
from typing import Optional, Callable, Tuple
from datetime import datetime
from dotenv import load_dotenv

from managers.data_folder_manager import data_folder_manager
from utils.timeout_config import get_timeout
from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Load environment variables from multiple possible locations
import pathlib

def _load_env_file():
    """Try to load .env from multiple locations."""
    # Possible .env locations in order of priority
    possible_paths = [
        # 1. AppData / Application Support folder (most reliable for packaged apps)
        data_folder_manager.env_file_path,
        # 2. Project root (relative to this file) — useful when running from source
        pathlib.Path(__file__).parent.parent.parent / '.env',
        # 3. Current working directory
        pathlib.Path.cwd() / '.env',
    ]

    for env_path in possible_paths:
        try:
            if env_path.exists():
                load_dotenv(dotenv_path=str(env_path))
                logger.debug(f"Loaded .env from: {env_path}")
                return True
        except Exception as e:
            logger.debug(f"Failed to load .env from {env_path}: {e}")

    # Also try without specifying path (uses python-dotenv's default search)
    load_dotenv()
    return False

_load_env_file()


class RagProcessor:
    """Processes RAG queries using local vector database and knowledge graph.

    Supports two modes:
    1. Local RAG with streaming - Progressive result display with cancellation
    2. Local RAG (legacy) - Blocking search
    """

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
        self._streaming_retriever = None

        # Streaming and cancellation support
        self._current_cancellation_token = None
        self._use_streaming = True  # Enable streaming by default for local RAG

        # Log RAG mode configuration for debugging
        if self.use_local_rag:
            # Mask the URL for security (show only first 30 chars)
            masked_url = self.neon_database_url[:30] + "..." if len(self.neon_database_url) > 30 else self.neon_database_url
            logger.info(f"Local RAG mode enabled (Neon URL: {masked_url})")
        else:
            # Log env var status to help debug
            logger.warning(
                "Local RAG not configured - NEON_DATABASE_URL not found in environment. "
                f"Place .env at: {data_folder_manager.env_file_path}"
            )

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

        # Conversation context for follow-up queries
        self._conversation_history = []  # List of (query, key_topics) tuples
        self._max_history_length = 5  # Keep last 5 exchanges
        self._last_query_topics = []  # Key topics from last successful query

        # New conversation management components
        self._conversation_manager = None
        self._feedback_manager = None
        self._use_semantic_followup = True  # Use new semantic detection

        # Store last search results for feedback association
        self._last_search_results = []  # List of HybridSearchResult objects
        self._last_query_text = ""  # Query that produced the results

        # Store conversation exchanges for export functionality
        self._conversation_exchanges = []  # List of exchange dicts with query, response, sources
        self._max_exchanges = 100  # Maximum exchanges to store

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

    def _get_streaming_retriever(self):
        """Get or create streaming retriever for local RAG mode."""
        if self._streaming_retriever is None:
            try:
                from src.rag.streaming_retriever import get_streaming_retriever
                self._streaming_retriever = get_streaming_retriever()
            except Exception as e:
                logger.error(f"Failed to initialize streaming retriever: {e}")
                return None
        return self._streaming_retriever

    def _get_conversation_manager(self):
        """Get or create conversation manager for semantic context handling."""
        if self._conversation_manager is None:
            try:
                from src.rag.conversation_manager import get_conversation_manager
                from src.rag.followup_detector import get_followup_detector
                from src.rag.conversation_summarizer import get_conversation_summarizer
                from src.rag.medical_ner import get_ner_extractor

                # Initialize components
                detector = get_followup_detector()
                summarizer = get_conversation_summarizer()
                ner = get_ner_extractor()

                self._conversation_manager = get_conversation_manager(
                    followup_detector=detector,
                    summarizer=summarizer,
                    entity_extractor=ner,
                )
                logger.info("Conversation manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize conversation manager: {e}")
                return None
        return self._conversation_manager

    def _get_feedback_manager(self):
        """Get or create feedback manager for user feedback handling."""
        if self._feedback_manager is None:
            try:
                from src.rag.feedback_manager import get_feedback_manager
                self._feedback_manager = get_feedback_manager()
                logger.info("Feedback manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize feedback manager: {e}")
                return None
        return self._feedback_manager

    def cancel_current_query(self) -> bool:
        """Cancel the currently running query if any.

        Returns:
            True if a query was cancelled, False if nothing to cancel
        """
        if self._current_cancellation_token:
            self._current_cancellation_token.cancel("User cancelled query")
            logger.info("Query cancellation requested")
            return True
        return False

    @property
    def can_cancel(self) -> bool:
        """Check if there's a cancellable query in progress.

        Returns:
            True if a query can be cancelled
        """
        return (
            self.is_processing and
            self._current_cancellation_token is not None and
            not self._current_cancellation_token.is_cancelled
        )

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

    # -------------------------------------------------------------------------
    # Conversation Context Methods
    # -------------------------------------------------------------------------

    # Patterns that indicate a follow-up question
    _FOLLOWUP_PATTERNS = [
        r'^what about\b',
        r'^how about\b',
        r'^and\b',
        r'^also\b',
        r'^what else\b',
        r'^tell me more\b',
        r'^more on\b',
        r'^explain\b',
        r'^why\b',
        r'^how\b',
        r'^can you\b',
        r'^what are the\b',
        r'^what is the\b',
    ]

    # Pronouns and references that suggest context dependency
    _CONTEXT_REFS = ['it', 'this', 'that', 'these', 'those', 'they', 'them', 'its', 'their']

    def _is_followup_question(self, query: str) -> bool:
        """Detect if a query is likely a follow-up question.

        Args:
            query: The user's query

        Returns:
            True if the query appears to be a follow-up
        """
        if not self._conversation_history:
            return False

        query_lower = query.lower().strip()
        words = query_lower.split()

        # Short queries are often follow-ups
        if len(words) <= 4:
            return True

        # Check for follow-up patterns
        for pattern in self._FOLLOWUP_PATTERNS:
            if re.match(pattern, query_lower):
                return True

        # Check for context-dependent pronouns/references
        for ref in self._CONTEXT_REFS:
            if ref in words:
                return True

        # Questions without clear subjects are often follow-ups
        # e.g., "What are the side effects?" without mentioning the medication
        if query_lower.startswith(('what', 'how', 'why', 'when', 'where')):
            # Check if any key topics from last query are mentioned
            if self._last_query_topics:
                topic_mentioned = any(
                    topic.lower() in query_lower
                    for topic in self._last_query_topics
                )
                if not topic_mentioned:
                    return True

        return False

    def _extract_key_topics(self, query: str, response_text: str = "") -> list[str]:
        """Extract key topics from a query and response.

        Args:
            query: The user's query
            response_text: Optional response text for additional context

        Returns:
            List of key topic strings
        """
        # Common medical/document-related stopwords to exclude
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
            'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'between', 'under', 'again', 'further', 'then', 'once',
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 'whom',
            'this', 'that', 'these', 'those', 'am', 'and', 'but', 'if', 'or',
            'because', 'until', 'while', 'about', 'against', 'each', 'few',
            'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same',
            'than', 'too', 'very', 'just', 'also', 'now', 'tell', 'me', 'please',
            'explain', 'describe', 'information', 'details', 'give', 'show',
        }

        # Extract words from query
        words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())

        # Filter out stopwords and keep meaningful terms
        topics = [w for w in words if w not in stopwords]

        # Also look for multi-word medical terms (simplified approach)
        # Keep capitalized words from original query as they might be proper nouns
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
        topics.extend([c.lower() for c in capitalized if c.lower() not in stopwords])

        # Deduplicate while preserving order
        seen = set()
        unique_topics = []
        for topic in topics:
            if topic not in seen:
                seen.add(topic)
                unique_topics.append(topic)

        return unique_topics[:10]  # Keep top 10 topics

    def _enhance_query_with_context(self, query: str) -> str:
        """Enhance a follow-up query with conversation context.

        Args:
            query: The user's follow-up query

        Returns:
            Enhanced query with context prepended
        """
        if not self._conversation_history:
            return query

        # Get the last query and its topics
        last_query, last_topics = self._conversation_history[-1]

        # Build context from recent topics
        if last_topics:
            # Create a context prefix
            topic_str = ", ".join(last_topics[:5])  # Use top 5 topics
            enhanced = f"Regarding {topic_str}: {query}"
            logger.info(f"Enhanced follow-up query: '{query}' -> '{enhanced}'")
            return enhanced

        # Fallback: just prepend the last query context
        enhanced = f"Following up on '{last_query[:100]}': {query}"
        logger.info(f"Enhanced follow-up with last query context")
        return enhanced

    def _update_conversation_history(self, query: str, response_text: str = ""):
        """Update conversation history with the latest exchange.

        Args:
            query: The user's query
            response_text: The response text (for topic extraction)
        """
        topics = self._extract_key_topics(query, response_text)
        self._last_query_topics = topics

        self._conversation_history.append((query, topics))

        # Trim history if too long
        if len(self._conversation_history) > self._max_history_length:
            self._conversation_history = self._conversation_history[-self._max_history_length:]

    def _update_conversation_after_search(
        self,
        query: str,
        response,
        is_followup: bool = False,
        confidence: float = 0.0,
        intent_type: str = "new_topic"
    ):
        """Update conversation context after a successful search.

        Uses the new conversation manager if available, otherwise falls back
        to legacy history management.

        Args:
            query: The original user query
            response: RAGQueryResponse from the search
            is_followup: Whether this was detected as a follow-up
            confidence: Confidence score of follow-up detection
            intent_type: Intent classification
        """
        # Get response summary for context
        response_summary = ""
        if response.results:
            # Create brief summary from top results
            summaries = []
            for r in response.results[:3]:
                preview = r.chunk_text[:100] if r.chunk_text else ""
                summaries.append(f"{r.document_filename}: {preview}...")
            response_summary = " ".join(summaries)

        # Try to use new conversation manager
        if self._use_semantic_followup:
            manager = self._get_conversation_manager()
            if manager:
                try:
                    session_id = getattr(self, 'session_id', 'default')
                    manager.update_after_response(
                        session_id=session_id,
                        query=query,
                        response=response_summary,
                        is_followup=is_followup,
                        followup_confidence=confidence,
                        intent_type=intent_type,
                    )
                    return
                except Exception as e:
                    logger.warning(f"Conversation manager update failed: {e}")

        # Fallback to legacy history
        self._update_conversation_history(query, response_summary)

    def _process_query_with_context(self, user_message: str, query_embedding: list[float] = None) -> tuple[str, bool, float, str]:
        """Process a query, enhancing with context if it's a follow-up.

        Uses semantic follow-up detection when available, falls back to
        pattern-based detection otherwise.

        Args:
            user_message: The user's original message
            query_embedding: Optional query embedding for semantic similarity

        Returns:
            Tuple of (enhanced_query, is_followup, confidence, intent_type)
        """
        # Try to use new semantic conversation manager
        if self._use_semantic_followup:
            manager = self._get_conversation_manager()
            if manager:
                try:
                    session_id = getattr(self, 'session_id', 'default')
                    enhanced_query, is_followup, confidence, intent_type = manager.process_query(
                        session_id=session_id,
                        query=user_message,
                        query_embedding=query_embedding,
                    )
                    return enhanced_query, is_followup, confidence, intent_type
                except Exception as e:
                    logger.warning(f"Semantic follow-up detection failed: {e}")

        # Fallback to legacy pattern-based detection
        is_followup = self._is_followup_question(user_message)
        if is_followup:
            enhanced_query = self._enhance_query_with_context(user_message)
            return enhanced_query, True, 0.7, "followup"
        return user_message, False, 0.0, "new_topic"

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
            'local' for local RAG, 'none' if unconfigured
        """
        # Trust the configuration - if NEON_DATABASE_URL is set, use local RAG
        # Actual connectivity issues will be reported when operations are attempted
        if self.use_local_rag:
            return "local"
        return "none"

    def process_message(self, user_message: str, callback: Optional[Callable] = None):
        """
        Process a RAG query from the user using local vector database.

        Args:
            user_message: The user's query
            callback: Optional callback to call when processing is complete
        """
        if self.is_processing:
            logger.warning("RAG processor is already processing a message")
            return

        # Check if RAG is configured
        rag_mode = self.get_rag_mode()

        if rag_mode == "none":
            self._display_error(
                "No RAG system configured.\n"
                "Please set NEON_DATABASE_URL in your environment."
            )
            if callback:
                callback()
            return

        # Run processing in a separate thread to avoid blocking UI
        # Use streaming for local RAG mode
        if self._use_streaming:
            thread = threading.Thread(
                target=self._process_message_streaming,
                args=(user_message, callback),
                daemon=True
            )
        else:
            thread = threading.Thread(
                target=self._process_message_local,
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

            # Enhance query with context if it's a follow-up question
            search_query, is_followup, confidence, intent_type = self._process_query_with_context(user_message)
            logger.info(f"Processing local RAG query: {search_query[:100]}... (followup={is_followup}, intent={intent_type})")

            # Perform hybrid search
            from src.rag.models import RAGQueryRequest
            request = RAGQueryRequest(
                query=search_query,  # Use enhanced query for search
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
                # Update conversation context with original query
                self._update_conversation_after_search(user_message, response, is_followup, confidence, intent_type)

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

    def _process_message_streaming(self, user_message: str, callback: Optional[Callable]):
        """Process RAG query with streaming results and cancellation support.

        Uses parallel search execution for faster response times and
        progressive result display.

        Args:
            user_message: The user's query
            callback: Optional callback when processing is complete
        """
        from src.rag.streaming_models import (
            CancellationError,
            CancellationToken,
            StreamEvent,
            StreamEventType,
            StreamingSearchRequest,
        )

        try:
            self.is_processing = True

            # Create cancellation token for this query
            self._current_cancellation_token = CancellationToken()

            # Add user message to RAG tab
            self._add_message_to_rag_tab("User", user_message)

            # Show search progress indicator
            self._show_typing_indicator('search')

            # Get streaming retriever
            retriever = self._get_streaming_retriever()
            if not retriever:
                self._hide_typing_indicator()
                self._display_error("Failed to initialize streaming RAG retriever.")
                return

            # Enhance query with context if it's a follow-up question
            search_query, is_followup, confidence, intent_type = self._process_query_with_context(user_message)
            logger.info(f"Processing streaming RAG query: {search_query[:100]}... (followup={is_followup}, intent={intent_type})")

            # Create streaming search request
            request = StreamingSearchRequest(
                query=search_query,
                top_k=5,
                use_graph_search=True,
                similarity_threshold=0.3,
            )

            # Define thread-safe callback for stream events
            def handle_stream_event(event: StreamEvent):
                """Handle streaming events (called from worker thread)."""
                try:
                    # Update UI from main thread using app.after()
                    if event.event_type == StreamEventType.PROGRESS:
                        self.app.after(0, lambda: self._update_progress_message(event.message))
                    elif event.event_type == StreamEventType.VECTOR_RESULTS:
                        self.app.after(0, lambda: self._show_typing_indicator('search'))
                    elif event.event_type == StreamEventType.SEARCH_COMPLETE:
                        self.app.after(0, lambda: self._show_typing_indicator('generate'))
                    elif event.event_type == StreamEventType.ERROR:
                        logger.error(f"Stream error: {event.message}")
                    elif event.event_type == StreamEventType.CANCELLED:
                        logger.info(f"Stream cancelled: {event.message}")
                except Exception as e:
                    logger.debug(f"Error handling stream event: {e}")

            # Perform streaming hybrid search
            response = retriever.search_streaming(
                request,
                handle_stream_event,
                self._current_cancellation_token,
            )

            if not response.results:
                self._hide_typing_indicator()
                output = (
                    "I couldn't find any relevant information in the document database "
                    "for your query. Try uploading more documents or rephrasing your question."
                )
            else:
                # Update conversation context with original query
                self._update_conversation_after_search(user_message, response, is_followup, confidence, intent_type)

                # Generate AI response using retrieved context
                output = self._generate_rag_response(user_message, response)

            # Hide indicator and add response
            self._hide_typing_indicator()
            self._add_message_to_rag_tab("RAG Assistant", output)

            logger.info(
                f"Streaming RAG query completed: {response.total_results} results "
                f"in {response.processing_time_ms:.0f}ms"
            )

        except CancellationError as e:
            logger.info(f"RAG query cancelled: {e}")
            self._hide_typing_indicator()
            self._add_message_to_rag_tab("System", "Search cancelled.")

        except Exception as e:
            error_msg = f"Error processing streaming RAG query: {str(e)}"
            logger.error(error_msg)
            self._hide_typing_indicator()
            self._display_error(error_msg)

        finally:
            self._hide_typing_indicator()
            self.is_processing = False
            self._current_cancellation_token = None
            if callback:
                self.app.after(0, callback)

    def _update_progress_message(self, message: str):
        """Update progress message in the typing indicator.

        Args:
            message: Progress message to display
        """
        # This is called from the main thread
        try:
            if hasattr(self.app, 'rag_text') and self._typing_indicator_mark:
                # The typing indicator animation already handles the display
                # Just log the progress for now
                logger.debug(f"RAG progress: {message}")
        except Exception as e:
            logger.debug(f"Error updating progress message: {e}")

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

        # Store results for feedback association
        self._last_search_results = response.results if response else []
        self._last_query_text = query

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

            # Store exchange for export functionality
            source_data = []
            for result in response.results:
                source_data.append({
                    "document": result.document_filename,
                    "chunk_text": result.chunk_text[:200] + "..." if len(result.chunk_text) > 200 else result.chunk_text,
                    "score": result.combined_score,
                    "document_id": result.document_id,
                    "chunk_index": result.chunk_index
                })

            self._store_exchange(
                query=query,
                response=response_text,
                sources=source_data,
                processing_time_ms=response.processing_time_ms
            )

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

                # Add feedback buttons for each source (if results available)
                if self._last_search_results:
                    self._add_feedback_buttons()
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

    def _add_feedback_buttons(self):
        """Add feedback buttons for each source in the search results."""
        import tkinter as tk
        import ttkbootstrap as ttk

        if not self._last_search_results:
            return

        try:
            from src.ui.components.rag_feedback_buttons import RAGFeedbackButtons

            # Add a label for the feedback section
            self.app.rag_text.insert("end", "\n**Rate these sources:**\n", "feedback_header")
            self.app.rag_text.tag_config("feedback_header", font=("Arial", 9, "bold"))

            # Create feedback buttons for each result (up to 5)
            for i, result in enumerate(self._last_search_results[:5]):
                doc_id = result.document_id
                chunk_idx = result.chunk_index
                filename = result.document_filename

                # Create container frame
                feedback_frame = ttk.Frame(self.app.rag_text)

                # Source label
                source_label = ttk.Label(
                    feedback_frame,
                    text=f"Source {i+1}: {filename[:30]}{'...' if len(filename) > 30 else ''}",
                    font=("Arial", 9)
                )
                source_label.pack(side=tk.LEFT, padx=(0, 10))

                # Create feedback button component
                feedback_buttons = RAGFeedbackButtons(
                    on_feedback=self._handle_result_feedback,
                    show_flag=True,
                    compact=True
                )

                # Create buttons for this result
                buttons_frame = feedback_buttons.create_buttons(
                    feedback_frame,
                    doc_id,
                    chunk_idx
                )
                buttons_frame.pack(side=tk.LEFT)

                # Insert into text widget
                self.app.rag_text.window_create("end", window=feedback_frame)
                self.app.rag_text.insert("end", "\n")

            self.app.rag_text.insert("end", "\n")

        except ImportError as e:
            logger.debug(f"Feedback buttons not available: {e}")
        except Exception as e:
            logger.error(f"Error adding feedback buttons: {e}")

    def _handle_result_feedback(self, document_id: str, chunk_index: int, feedback_type: str):
        """Handle feedback button click for a search result.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document
            feedback_type: Type of feedback ('upvote', 'downvote', 'flag', or 'remove')
        """
        try:
            if feedback_type == "remove":
                # Remove feedback
                feedback_manager = self._get_feedback_manager()
                if feedback_manager:
                    # Get session ID for removal
                    session_id = getattr(self.app, 'session_id', 'default_session')
                    feedback_manager.remove_feedback(document_id, chunk_index, session_id)
                    logger.info(f"Removed feedback for {document_id}:{chunk_index}")
            else:
                # Record new feedback
                result = self.record_result_feedback(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    feedback_type=feedback_type,
                    query_text=self._last_query_text,
                    original_score=self._get_result_score(document_id, chunk_index)
                )
                if result:
                    logger.info(f"Recorded {feedback_type} for {document_id}:{chunk_index}")

                    # Show brief status message
                    if hasattr(self.app, 'status_manager'):
                        feedback_labels = {
                            'upvote': 'Marked as helpful',
                            'downvote': 'Marked as not helpful',
                            'flag': 'Flagged for review'
                        }
                        self.app.status_manager.info(feedback_labels.get(feedback_type, 'Feedback recorded'))

        except Exception as e:
            logger.error(f"Error handling feedback: {e}")

    def _get_result_score(self, document_id: str, chunk_index: int) -> float:
        """Get the original score for a result.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index

        Returns:
            Combined score from the search result, or 0.0 if not found
        """
        for result in self._last_search_results:
            if result.document_id == document_id and result.chunk_index == chunk_index:
                return result.combined_score
        return 0.0
        
    def _display_error(self, error_message: str):
        """Display an error message in the RAG tab."""
        self._add_message_to_rag_tab("System Error", error_message)
        
    def record_result_feedback(
        self,
        document_id: str,
        chunk_index: int,
        feedback_type: str,
        query_text: str = "",
        original_score: float = 0.0
    ) -> bool:
        """Record user feedback on a search result.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document
            feedback_type: Type of feedback ('upvote', 'downvote', 'flag', 'remove')
            query_text: The query that produced this result
            original_score: Original relevance score

        Returns:
            True if feedback was recorded successfully
        """
        manager = self._get_feedback_manager()
        if not manager:
            logger.warning("Feedback manager not available")
            return False

        try:
            session_id = getattr(self, 'session_id', 'default')

            if feedback_type == "remove":
                # Remove previous feedback
                return manager.remove_feedback(document_id, chunk_index, session_id)
            else:
                # Record new feedback
                from src.rag.feedback_manager import FeedbackType
                fb_type = FeedbackType(feedback_type)
                return manager.record_feedback(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    feedback_type=fb_type,
                    query_text=query_text,
                    session_id=session_id,
                    original_score=original_score,
                )
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            return False

    def clear_history(self):
        """Clear the RAG conversation history."""
        # Clear conversation context for follow-up queries
        self._conversation_history = []
        self._last_query_topics = []

        # Clear conversation exchanges for export
        self._conversation_exchanges = []

        # Clear last search results
        self._last_search_results = []
        self._last_query_text = ""

        # Also clear conversation manager session if available
        if self._use_semantic_followup:
            manager = self._get_conversation_manager()
            if manager:
                try:
                    session_id = getattr(self, 'session_id', 'default')
                    manager.clear_session(session_id)
                except Exception as e:
                    logger.warning(f"Failed to clear conversation manager session: {e}")

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

    # -------------------------------------------------------------------------
    # Export and Attribution Methods
    # -------------------------------------------------------------------------

    def _store_exchange(
        self,
        query: str,
        response: str,
        sources: list = None,
        query_expansion: dict = None,
        processing_time_ms: float = 0.0
    ):
        """Store a conversation exchange for export functionality.

        Args:
            query: The user's query
            response: The AI-generated response
            sources: List of source dictionaries with document info
            query_expansion: Query expansion details if any
            processing_time_ms: Processing time in milliseconds
        """
        exchange = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response,
            "sources": sources or [],
            "query_expansion": query_expansion,
            "processing_time_ms": processing_time_ms
        }

        self._conversation_exchanges.append(exchange)

        # Trim if too long
        if len(self._conversation_exchanges) > self._max_exchanges:
            self._conversation_exchanges = self._conversation_exchanges[-self._max_exchanges:]

    def get_conversation_export_data(self) -> dict:
        """Get conversation data formatted for export.

        Returns:
            Dictionary with session info and exchanges ready for export
        """
        session_id = getattr(self, 'session_id', str(uuid.uuid4()))

        # Calculate metadata
        total_queries = len(self._conversation_exchanges)
        documents_searched = set()
        for exchange in self._conversation_exchanges:
            for source in exchange.get("sources", []):
                doc_name = source.get("document", source.get("document_filename", ""))
                if doc_name:
                    documents_searched.add(doc_name)

        return {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "exchanges": self._conversation_exchanges,
            "metadata": {
                "total_queries": total_queries,
                "documents_searched": len(documents_searched),
                "rag_mode": self.get_rag_mode(),
                "export_timestamp": datetime.now().isoformat()
            }
        }

    def get_recent_queries(self, limit: int = 10) -> list[str]:
        """Get recent queries for autocomplete suggestions.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of recent query strings (most recent first)
        """
        queries = []
        for exchange in reversed(self._conversation_exchanges):
            query = exchange.get("query", "")
            if query and query not in queries:
                queries.append(query)
                if len(queries) >= limit:
                    break

        # Also add from conversation history if not enough
        for query, _ in reversed(self._conversation_history):
            if query and query not in queries:
                queries.append(query)
                if len(queries) >= limit:
                    break

        return queries[:limit]

    def get_source_attributions(self) -> list:
        """Get source attributions from the last search for highlighting.

        Returns:
            List of SourceAttribution-compatible dictionaries
        """
        if not self._last_search_results:
            return []

        attributions = []
        for i, result in enumerate(self._last_search_results):
            attribution = {
                "source_index": i,
                "document_id": getattr(result, 'document_id', ''),
                "document_name": getattr(result, 'document_filename', 'Unknown'),
                "chunk_index": getattr(result, 'chunk_index', 0),
                "chunk_text": getattr(result, 'chunk_text', ''),
                "page_number": result.metadata.get('page_number') if getattr(result, 'metadata', None) else None,
                "score": getattr(result, 'combined_score', 0.0)
            }
            attributions.append(attribution)

        return attributions

    def get_last_search_results(self) -> list:
        """Get the last search results for UI display.

        Returns:
            List of HybridSearchResult objects from the last query
        """
        return self._last_search_results

    def get_last_query(self) -> str:
        """Get the last query text.

        Returns:
            The last query string or empty string
        """
        return self._last_query_text