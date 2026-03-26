"""
RAG Query Processing Mixin

Handles query context enhancement, follow-up detection, and
conversation history management for the RAG processor.
"""

import re
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class RagQueryMixin:
    """Mixin providing query processing and context methods for RagProcessor."""

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

        # Very short queries (1-2 words) are likely follow-ups
        if len(words) <= 2:
            return True

        # 3-4 word queries are follow-ups only if they contain context references
        if len(words) <= 4:
            for ref in self._CONTEXT_REFS:
                if ref in words:
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
                    session_id = self.session_id
                    manager.update_after_response(
                        session_id=session_id,
                        query=query,
                        response=response_summary,
                        is_followup=is_followup,
                        followup_confidence=confidence,
                        intent_type=intent_type,
                    )
                    return
                except (AttributeError, KeyError, ValueError) as e:
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
                    session_id = self.session_id
                    enhanced_query, is_followup, confidence, intent_type = manager.process_query(
                        session_id=session_id,
                        query=user_message,
                        query_embedding=query_embedding,
                    )
                    return enhanced_query, is_followup, confidence, intent_type
                except (AttributeError, KeyError, ValueError) as e:
                    logger.warning(f"Semantic follow-up detection failed: {e}")

        # Fallback to legacy pattern-based detection
        is_followup = self._is_followup_question(user_message)
        if is_followup:
            enhanced_query = self._enhance_query_with_context(user_message)
            return enhanced_query, True, 0.7, "followup"
        return user_message, False, 0.0, "new_topic"

    def _process_message_local(self, user_message: str, callback):
        """Process RAG query using local vector database.

        Args:
            user_message: The user's query
            callback: Optional callback when processing is complete
        """
        try:
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
            from rag.models import RAGQueryRequest
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

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            error_msg = f"Error processing local RAG query: {str(e)}"
            logger.error(error_msg)
            self._hide_typing_indicator()  # Cleanup on error
            self._display_error(error_msg)

        finally:
            self._hide_typing_indicator()  # Ensure cleanup
            self.is_processing = False
            if callback:
                self.app.after(0, callback)

    def _process_message_streaming(self, user_message: str, callback):
        """Process RAG query with streaming results and cancellation support.

        Uses parallel search execution for faster response times and
        progressive result display.

        Args:
            user_message: The user's query
            callback: Optional callback when processing is complete
        """
        import tkinter as tk
        from rag.streaming_models import (
            CancellationError,
            CancellationToken,
            StreamEvent,
            StreamEventType,
            StreamingSearchRequest,
        )

        try:
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
                except (tk.TclError, AttributeError) as e:
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

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
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
