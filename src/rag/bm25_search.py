"""
BM25-style full-text search for RAG system.

Uses PostgreSQL's ts_vector/ts_query for keyword-based search
to complement vector similarity search.
"""

from utils.structured_logging import get_logger
import re
from typing import Optional

from rag.search_config import SearchQualityConfig, get_search_quality_config

logger = get_logger(__name__)


class BM25SearchResult:
    """Result from BM25 full-text search."""

    def __init__(
        self,
        document_id: str,
        chunk_index: int,
        chunk_text: str,
        bm25_score: float,
        metadata: Optional[dict] = None,
    ):
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.chunk_text = chunk_text
        self.bm25_score = bm25_score
        self.metadata = metadata or {}


class BM25Searcher:
    """Full-text search using PostgreSQL tsvector."""

    def __init__(
        self,
        vector_store=None,
        config: Optional[SearchQualityConfig] = None
    ):
        """Initialize BM25 searcher.

        Args:
            vector_store: NeonVectorStore instance
            config: Search quality configuration
        """
        self._vector_store = vector_store
        self.config = config or get_search_quality_config()

    def _get_vector_store(self):
        """Get or create vector store."""
        if self._vector_store is None:
            from rag.neon_vector_store import get_vector_store
            self._vector_store = get_vector_store()
        return self._vector_store

    def search(
        self,
        query: str,
        expanded_terms: Optional[list[str]] = None,
        top_k: int = 10,
        filter_document_ids: Optional[list[str]] = None,
    ) -> list[BM25SearchResult]:
        """Perform BM25 full-text search.

        Args:
            query: Search query
            expanded_terms: Additional terms from query expansion
            top_k: Number of results to return
            filter_document_ids: Optional document IDs to filter

        Returns:
            List of BM25SearchResult objects
        """
        if not self.config.enable_bm25:
            return []

        try:
            vector_store = self._get_vector_store()
            pool = vector_store._get_pool()

            # Build search query with expanded terms
            search_terms = self._build_search_query(query, expanded_terms)

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Build SQL query using ts_vector search
                    # PostgreSQL's ts_rank provides BM25-like ranking
                    sql = """
                        SELECT
                            document_id,
                            chunk_index,
                            chunk_text,
                            ts_rank_cd(search_vector, plainto_tsquery('english', %s)) as rank,
                            metadata
                        FROM document_embeddings
                        WHERE search_vector @@ plainto_tsquery('english', %s)
                    """
                    params = [search_terms, search_terms]

                    # Add document filter if specified
                    if filter_document_ids:
                        placeholders = ",".join(["%s::uuid"] * len(filter_document_ids))
                        sql += f" AND document_id IN ({placeholders})"
                        params.extend(filter_document_ids)

                    sql += " ORDER BY rank DESC LIMIT %s"
                    params.append(top_k)

                    cur.execute(sql, params)
                    rows = cur.fetchall()

            results = []
            for row in rows:
                doc_id, chunk_idx, chunk_text, rank, metadata = row

                # Parse metadata
                if metadata is None:
                    meta = {}
                elif isinstance(metadata, dict):
                    meta = metadata
                else:
                    import json
                    meta = json.loads(metadata)

                # Normalize rank to 0-1 range
                # ts_rank_cd typically returns values < 1
                normalized_score = min(1.0, float(rank) * 10)

                results.append(BM25SearchResult(
                    document_id=str(doc_id),
                    chunk_index=chunk_idx,
                    chunk_text=chunk_text,
                    bm25_score=normalized_score,
                    metadata=meta,
                ))

            logger.debug(f"BM25 search: '{query}' -> {len(results)} results")
            return results

        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []

    def search_with_websearch_query(
        self,
        query: str,
        expanded_terms: Optional[list[str]] = None,
        top_k: int = 10,
        filter_document_ids: Optional[list[str]] = None,
    ) -> list[BM25SearchResult]:
        """Perform BM25 search using websearch_to_tsquery for more flexibility.

        This supports more natural query syntax with AND/OR operators.

        Args:
            query: Search query
            expanded_terms: Additional terms from query expansion
            top_k: Number of results to return
            filter_document_ids: Optional document IDs to filter

        Returns:
            List of BM25SearchResult objects
        """
        if not self.config.enable_bm25:
            return []

        try:
            vector_store = self._get_vector_store()
            pool = vector_store._get_pool()

            # Build websearch-style query
            search_terms = self._build_websearch_query(query, expanded_terms)

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                        SELECT
                            document_id,
                            chunk_index,
                            chunk_text,
                            ts_rank_cd(search_vector, websearch_to_tsquery('english', %s)) as rank,
                            metadata
                        FROM document_embeddings
                        WHERE search_vector @@ websearch_to_tsquery('english', %s)
                    """
                    params = [search_terms, search_terms]

                    if filter_document_ids:
                        placeholders = ",".join(["%s::uuid"] * len(filter_document_ids))
                        sql += f" AND document_id IN ({placeholders})"
                        params.extend(filter_document_ids)

                    sql += " ORDER BY rank DESC LIMIT %s"
                    params.append(top_k)

                    cur.execute(sql, params)
                    rows = cur.fetchall()

            results = []
            for row in rows:
                doc_id, chunk_idx, chunk_text, rank, metadata = row

                if metadata is None:
                    meta = {}
                elif isinstance(metadata, dict):
                    meta = metadata
                else:
                    import json
                    meta = json.loads(metadata)

                normalized_score = min(1.0, float(rank) * 10)

                results.append(BM25SearchResult(
                    document_id=str(doc_id),
                    chunk_index=chunk_idx,
                    chunk_text=chunk_text,
                    bm25_score=normalized_score,
                    metadata=meta,
                ))

            return results

        except Exception as e:
            logger.warning(f"BM25 websearch failed: {e}")
            # Fall back to simple search
            return self.search(query, expanded_terms, top_k, filter_document_ids)

    def _build_search_query(
        self,
        query: str,
        expanded_terms: Optional[list[str]] = None
    ) -> str:
        """Build search query string for plainto_tsquery.

        Args:
            query: Original query
            expanded_terms: Additional terms to include

        Returns:
            Search query string
        """
        # Start with original query
        terms = [self._clean_term(query)]

        # Add expanded terms
        if expanded_terms:
            for term in expanded_terms[:5]:  # Limit expansion terms
                cleaned = self._clean_term(term)
                if cleaned and cleaned not in terms:
                    terms.append(cleaned)

        # Join with spaces (plainto_tsquery treats them as AND)
        return " ".join(terms)

    def _build_websearch_query(
        self,
        query: str,
        expanded_terms: Optional[list[str]] = None
    ) -> str:
        """Build search query string for websearch_to_tsquery.

        websearch_to_tsquery supports:
        - "quoted phrases"
        - term OR term
        - -excluded_term

        Args:
            query: Original query
            expanded_terms: Additional terms to include

        Returns:
            Websearch query string
        """
        # Quote the original query as a phrase
        base_query = f'"{query}"'

        # Add expanded terms with OR
        if expanded_terms:
            for term in expanded_terms[:3]:  # Limit for websearch
                cleaned = self._clean_term(term)
                if cleaned:
                    base_query += f' OR "{cleaned}"'

        return base_query

    def _clean_term(self, term: str) -> str:
        """Clean a search term for use in tsquery.

        Args:
            term: Search term

        Returns:
            Cleaned term
        """
        # Remove special characters that could break tsquery
        cleaned = re.sub(r'[^\w\s]', ' ', term)
        # Collapse whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip().lower()

    def check_search_vector_exists(self) -> bool:
        """Check if the search_vector column exists in the database.

        Returns:
            True if search_vector column exists
        """
        try:
            vector_store = self._get_vector_store()
            pool = vector_store._get_pool()

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'document_embeddings'
                        AND column_name = 'search_vector'
                    """)
                    result = cur.fetchone()
                    return result is not None

        except Exception as e:
            logger.warning(f"Failed to check search_vector column: {e}")
            return False


# Singleton instance
_searcher: Optional[BM25Searcher] = None


def get_bm25_searcher() -> BM25Searcher:
    """Get the global BM25 searcher instance.

    Returns:
        BM25Searcher instance
    """
    global _searcher
    if _searcher is None:
        _searcher = BM25Searcher()
    return _searcher


def reset_bm25_searcher():
    """Reset the global BM25 searcher instance."""
    global _searcher
    _searcher = None


def search_bm25(
    query: str,
    expanded_terms: Optional[list[str]] = None,
    top_k: int = 10,
) -> list[BM25SearchResult]:
    """Convenience function for BM25 search.

    Args:
        query: Search query
        expanded_terms: Additional terms from query expansion
        top_k: Number of results

    Returns:
        List of BM25SearchResult objects
    """
    searcher = get_bm25_searcher()
    return searcher.search(query, expanded_terms, top_k)
