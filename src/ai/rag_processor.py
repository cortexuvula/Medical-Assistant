"""
RAG Processor for Medical Assistant

Provides local RAG (Retrieval-Augmented Generation) functionality using
Neon pgvector for vector storage and Neo4j for knowledge graph queries.

The RAG system is enabled when NEON_DATABASE_URL is configured in the environment.
"""

import threading
import os
import re
from typing import Optional, Callable
from dotenv import load_dotenv

from managers.data_folder_manager import data_folder_manager
from utils.structured_logging import get_logger

from ai.rag_query import RagQueryMixin
from ai.rag_response import RagResponseMixin
from ai.rag_ui import RagUIMixin
from ai.rag_feedback import RagFeedbackMixin

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


class RagProcessor(RagQueryMixin, RagResponseMixin, RagUIMixin, RagFeedbackMixin):
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
            # Mask the URL for security (hide credentials)
            try:
                import urllib.parse
                parsed = urllib.parse.urlparse(self.neon_database_url)
                masked_url = f"{parsed.scheme}://***:***@{parsed.hostname}/..."
            except Exception:
                masked_url = "postgresql://***:***@***/..."
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

        # Session identifier for conversation management
        self.session_id = 'default'

    def _get_hybrid_retriever(self):
        """Get or create hybrid retriever for local RAG mode."""
        if self._hybrid_retriever is None:
            try:
                from rag.hybrid_retriever import get_hybrid_retriever
                self._hybrid_retriever = get_hybrid_retriever()
            except (ImportError, Exception) as e:
                logger.error(f"Failed to initialize hybrid retriever: {e}")
                return None
        return self._hybrid_retriever

    def _get_streaming_retriever(self):
        """Get or create streaming retriever for local RAG mode."""
        if self._streaming_retriever is None:
            try:
                from rag.streaming_retriever import get_streaming_retriever
                self._streaming_retriever = get_streaming_retriever()
            except (ImportError, Exception) as e:
                logger.error(f"Failed to initialize streaming retriever: {e}")
                return None
        return self._streaming_retriever

    def _get_conversation_manager(self):
        """Get or create conversation manager for semantic context handling."""
        if self._conversation_manager is None:
            try:
                from rag.conversation_manager import get_conversation_manager
                from rag.followup_detector import get_followup_detector
                from rag.conversation_summarizer import get_conversation_summarizer
                from rag.medical_ner import get_ner_extractor

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
            except ImportError as e:
                logger.warning(f"Failed to initialize conversation manager: {e}")
                return None
        return self._conversation_manager

    def _get_feedback_manager(self):
        """Get or create feedback manager for user feedback handling."""
        if self._feedback_manager is None:
            try:
                from rag.feedback_manager import get_feedback_manager
                self._feedback_manager = get_feedback_manager()
                logger.info("Feedback manager initialized")
            except ImportError as e:
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
        except (ConnectionError, OSError, AttributeError):
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

        # Set processing flag immediately to prevent duplicate queries
        self.is_processing = True

        # Check if RAG is configured
        rag_mode = self.get_rag_mode()

        if rag_mode == "none":
            self.is_processing = False
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
