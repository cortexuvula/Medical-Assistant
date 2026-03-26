"""
RAG Feedback and Export Mixin

Handles user feedback on search results, conversation history clearing,
exchange storage, and export functionality for the RAG processor.
"""

import tkinter as tk
import uuid
from datetime import datetime
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class RagFeedbackMixin:
    """Mixin providing feedback, export, and history methods for RagProcessor."""

    def _add_feedback_buttons(self):
        """Add feedback buttons for each source in the search results."""
        import tkinter as tk
        import ttkbootstrap as ttk

        if not self._last_search_results:
            return

        try:
            from ui.components.rag_feedback_buttons import RAGFeedbackButtons

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
        except (tk.TclError, AttributeError, KeyError) as e:
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

        except (ValueError, KeyError, AttributeError) as e:
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
            session_id = self.session_id

            if feedback_type == "remove":
                # Remove previous feedback
                return manager.remove_feedback(document_id, chunk_index, session_id)
            else:
                # Record new feedback
                from rag.feedback_manager import FeedbackType
                fb_type = FeedbackType(feedback_type)
                return manager.record_feedback(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    feedback_type=fb_type,
                    query_text=query_text,
                    session_id=session_id,
                    original_score=original_score,
                )
        except (ValueError, KeyError, AttributeError) as e:
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
                    session_id = self.session_id
                    manager.clear_session(session_id)
                except (AttributeError, KeyError) as e:
                    logger.warning(f"Failed to clear conversation manager session: {e}")

        if hasattr(self.app, 'rag_text'):
            def clear_ui():
                self.app.rag_text.delete("1.0", "end")
                # Re-add welcome message
                self.app.rag_text.insert("1.0", "Welcome to the RAG Document Search!\n\n")
                self.app.rag_text.insert("end", "This interface allows you to search your document database:\n")
                self.app.rag_text.insert("end", "\u2022 Query documents stored in your RAG database\n")
                self.app.rag_text.insert("end", "\u2022 Get relevant information from your knowledge base\n")
                self.app.rag_text.insert("end", "\u2022 Search through previously uploaded documents\n\n")
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
        session_id = self.session_id

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
