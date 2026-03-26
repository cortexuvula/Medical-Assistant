"""
RAG Response Generation Mixin

Handles AI response generation, formatting, and sanitization
for the RAG processor.
"""

from datetime import datetime
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class RagResponseMixin:
    """Mixin providing response generation and formatting methods for RagProcessor."""

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

        except (ConnectionError, TimeoutError, KeyError, ValueError) as e:
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
            original_len = len(text)
            text = text[:self.MAX_RESPONSE_LENGTH] + "\n\n[Response truncated due to length]"
            logger.warning(f"Response truncated from {original_len} to {self.MAX_RESPONSE_LENGTH} chars")

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
