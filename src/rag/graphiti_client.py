"""
Graphiti client for knowledge graph integration.

Uses Zep AI's Graphiti SDK for building and querying
temporal knowledge graphs from documents.

Enhanced with:
- Circuit breaker for graceful degradation when Neo4j unavailable
- Reduced async timeout (30s instead of 300s) to prevent UI freeze
- Driver reuse in health_check() for efficiency
"""

import asyncio
import atexit
import logging
import os
import pathlib
import queue
import threading
from datetime import datetime
from typing import Any, Callable, Optional

from dotenv import load_dotenv

from src.rag.models import GraphSearchResult
from src.utils.timeout_config import get_timeout

# Load environment variables from multiple possible locations
def _load_env():
    """Load .env from multiple possible locations."""
    paths = []
    try:
        from managers.data_folder_manager import data_folder_manager
        paths.append(data_folder_manager.env_file_path)  # AppData / Application Support
    except Exception:
        pass
    paths.extend([
        pathlib.Path(__file__).parent.parent.parent / '.env',  # Project root
        pathlib.Path.cwd() / '.env',  # Current working directory
    ])

    for p in paths:
        try:
            if p.exists():
                load_dotenv(dotenv_path=str(p))
                return
        except Exception:
            pass
    load_dotenv()  # Try default search

_load_env()

logger = logging.getLogger(__name__)

# Suppress noisy Neo4j warnings about non-existent properties
logging.getLogger("neo4j").setLevel(logging.ERROR)


class _Neo4jWarningFilter(logging.Filter):
    """Filter out Neo4j GqlStatusObject warnings about missing properties."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        if "property key does not exist" in msg:
            return False
        if "GqlStatusObject" in msg and "01N52" in msg:
            return False
        return True


logging.getLogger("neo4j").addFilter(_Neo4jWarningFilter())


class _AsyncWorker:
    """Dedicated async worker thread for Graphiti operations.

    Ensures all async operations run in a single, consistent event loop.
    """

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._started = threading.Event()
        self._stopped = False

    def start(self):
        """Start the worker thread."""
        if self._thread is not None:
            return

        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="graphiti-async-worker",
        )
        self._thread.start()
        # Wait for loop to be ready
        self._started.wait(timeout=5.0)

    def _run_loop(self):
        """Run the event loop in the worker thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started.set()

        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def run_coroutine(self, coro, timeout: Optional[float] = None) -> Any:
        """Run a coroutine in the worker's event loop.

        Args:
            coro: Coroutine to run
            timeout: Optional timeout in seconds (default: 30s from config)

        Returns:
            Result of the coroutine
        """
        if self._loop is None or self._stopped:
            raise RuntimeError("Async worker not running")

        # Use configured timeout, defaulting to 30s to prevent UI freeze
        if timeout is None:
            timeout = get_timeout("neo4j", default=30.0)

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def stop(self):
        """Stop the worker thread."""
        if self._loop is not None and not self._stopped:
            self._stopped = True
            self._loop.call_soon_threadsafe(self._loop.stop)


# Global async worker instance
_async_worker: Optional[_AsyncWorker] = None
_worker_lock = threading.Lock()


def _get_async_worker() -> _AsyncWorker:
    """Get or create the global async worker."""
    global _async_worker
    with _worker_lock:
        if _async_worker is None:
            _async_worker = _AsyncWorker()
            _async_worker.start()
            # Register cleanup on exit
            atexit.register(_cleanup_async_worker)
    return _async_worker


def _cleanup_async_worker():
    """Clean up the async worker on exit."""
    global _async_worker
    if _async_worker is not None:
        try:
            _async_worker.stop()
        except Exception:
            pass
        _async_worker = None


class GraphitiClient:
    """Client for Graphiti knowledge graph operations.

    Enhanced with circuit breaker pattern for resilience.
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        """Initialize Graphiti client.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            openai_api_key: OpenAI API key for entity extraction
        """
        self._neo4j_uri = neo4j_uri
        self._neo4j_user = neo4j_user
        self._neo4j_password = neo4j_password
        self._openai_api_key = openai_api_key
        self._client = None
        self._neo4j_driver = None  # Cached driver for health checks
        self._initialized = False
        self._init_lock = threading.Lock()

    def _get_config(self):
        """Get configuration from environment or settings."""
        uri = self._neo4j_uri or os.environ.get("NEO4J_URI")
        user = self._neo4j_user or os.environ.get("NEO4J_USER", "neo4j")
        password = self._neo4j_password or os.environ.get("NEO4J_PASSWORD")
        openai_key = self._openai_api_key or os.environ.get("OPENAI_API_KEY")

        if not uri or not password:
            try:
                from src.settings.settings import SETTINGS
                uri = uri or SETTINGS.get("graphiti_neo4j_uri")
                user = user or SETTINGS.get("graphiti_neo4j_user", "neo4j")
                password = password or SETTINGS.get("graphiti_neo4j_password")
            except Exception:
                pass

        if not openai_key:
            try:
                from src.managers.api_key_manager import get_api_key_manager
                manager = get_api_key_manager()
                openai_key = manager.get_key("openai")
            except Exception:
                pass

        return uri, user, password, openai_key

    def _get_client(self):
        """Get or create Graphiti client."""
        if self._client is not None:
            return self._client

        try:
            from graphiti_core import Graphiti
            from graphiti_core.llm_client import OpenAIClient
            from graphiti_core.llm_client.config import LLMConfig
        except ImportError:
            raise ImportError(
                "graphiti-core is required for knowledge graph features. "
                "Install with: pip install graphiti-core"
            )

        uri, user, password, openai_key = self._get_config()

        if not uri or not password:
            raise ValueError(
                "Neo4j connection details not found. "
                "Set NEO4J_URI and NEO4J_PASSWORD environment variables."
            )

        if not openai_key:
            raise ValueError("OpenAI API key required for Graphiti.")

        llm_config = LLMConfig(
            api_key=openai_key,
            model="gpt-4o-mini",
            small_model="gpt-4o-mini",
            max_tokens=16384,
        )

        llm_client = OpenAIClient(config=llm_config)
        self._client = Graphiti(uri, user, password, llm_client=llm_client)

        return self._client

    async def _initialize_async(self):
        """Initialize the knowledge graph schema (async)."""
        client = self._get_client()
        await client.build_indices_and_constraints()
        logger.info("Graphiti knowledge graph initialized")

    def initialize(self):
        """Initialize the knowledge graph schema (sync)."""
        with self._init_lock:
            if self._initialized:
                return

            worker = _get_async_worker()
            worker.run_coroutine(self._initialize_async())
            self._initialized = True

    def initialize_sync(self):
        """Synchronous initialization (alias for initialize)."""
        self.initialize()

    async def _add_document_episode_async(
        self,
        document_id: str,
        content: str,
        metadata: Optional[dict] = None,
        source_description: str = "document",
    ):
        """Add document as episode (async)."""
        try:
            from graphiti_core.nodes import EpisodeType
        except ImportError:
            logger.warning("graphiti_core not available")
            return

        client = self._get_client()

        episode_name = f"doc_{document_id}"
        description = source_description
        if metadata:
            if "filename" in metadata:
                description = f"{source_description}: {metadata['filename']}"
            if "title" in metadata and metadata["title"]:
                description = f"{description} - {metadata['title']}"

        await client.add_episode(
            name=episode_name,
            episode_body=content,
            source=EpisodeType.text,
            source_description=description,
            reference_time=datetime.now(),
        )
        logger.info(f"Added document {document_id} to knowledge graph")

    def add_document_episode_sync(
        self,
        document_id: str,
        content: str,
        metadata: Optional[dict] = None,
        source_description: str = "document",
    ):
        """Add document as episode (sync)."""
        if not self._initialized:
            self.initialize()

        worker = _get_async_worker()
        worker.run_coroutine(
            self._add_document_episode_async(
                document_id, content, metadata, source_description
            )
        )

    async def _search_async(
        self,
        query: str,
        num_results: int = 10,
    ) -> list[GraphSearchResult]:
        """Search the knowledge graph (async)."""
        client = self._get_client()

        try:
            results = await client.search(query, num_results=num_results)

            graph_results = []
            for result in results:
                entity_name = getattr(result, "name", "")
                entity_type = getattr(result, "entity_type", "entity")
                fact = getattr(result, "fact", getattr(result, "content", ""))
                source_doc = getattr(result, "source_description", None)

                source_doc_id = None
                if source_doc and source_doc.startswith("doc_"):
                    source_doc_id = source_doc[4:]

                graph_results.append(GraphSearchResult(
                    entity_name=entity_name,
                    entity_type=entity_type,
                    fact=fact,
                    source_document_id=source_doc_id,
                    relevance_score=0.8,
                ))

            return graph_results

        except Exception as e:
            logger.error(f"Knowledge graph search failed: {e}")
            return []

    def search(self, query: str, num_results: int = 10) -> list[GraphSearchResult]:
        """Search the knowledge graph (sync).

        Uses circuit breaker to fail fast when Neo4j is unavailable.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            List of GraphSearchResult (empty if circuit breaker open)
        """
        # Check circuit breaker first for fast fail
        try:
            from src.rag.rag_resilience import (
                get_neo4j_circuit_breaker,
                CircuitOpenError,
            )
            from src.utils.resilience import CircuitState

            cb = get_neo4j_circuit_breaker()
            if cb.state == CircuitState.OPEN:
                logger.warning("Neo4j circuit breaker open, skipping graph search")
                return []
        except ImportError:
            pass  # Resilience module not available, continue without CB

        if not self._initialized:
            try:
                self.initialize()
            except Exception as e:
                logger.warning(f"Failed to initialize Graphiti: {e}")
                self._record_failure()
                return []

        try:
            worker = _get_async_worker()
            result = worker.run_coroutine(self._search_async(query, num_results))
            self._record_success()
            return result
        except Exception as e:
            logger.warning(f"Graph search failed: {e}")
            self._record_failure()
            return []

    def _record_success(self):
        """Record successful operation for circuit breaker."""
        try:
            from src.rag.rag_resilience import get_neo4j_circuit_breaker
            cb = get_neo4j_circuit_breaker()
            cb._on_success()
        except Exception:
            pass

    def _record_failure(self):
        """Record failed operation for circuit breaker."""
        try:
            from src.rag.rag_resilience import get_neo4j_circuit_breaker
            cb = get_neo4j_circuit_breaker()
            cb._on_failure()
        except Exception:
            pass

    async def _get_entity_context_async(
        self,
        entity_name: str,
        depth: int = 2,
    ) -> dict:
        """Get context around entity (async)."""
        client = self._get_client()

        try:
            search_results = await client.search(entity_name, num_results=10)
            return {
                "entity": entity_name,
                "related_facts": [
                    getattr(r, "fact", getattr(r, "content", ""))
                    for r in search_results
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get entity context: {e}")
            return {"entity": entity_name, "related_facts": []}

    def get_entity_context(self, entity_name: str, depth: int = 2) -> dict:
        """Get context around entity (sync)."""
        if not self._initialized:
            self.initialize()

        worker = _get_async_worker()
        return worker.run_coroutine(
            self._get_entity_context_async(entity_name, depth)
        )

    async def _delete_document_episodes_async(self, document_id: str):
        """Delete episodes for document (async)."""
        logger.warning(
            f"Episode deletion not fully implemented for document {document_id}"
        )

    def delete_document_episodes(self, document_id: str):
        """Delete episodes for document (sync)."""
        worker = _get_async_worker()
        worker.run_coroutine(self._delete_document_episodes_async(document_id))

    def _get_neo4j_driver(self):
        """Get or create cached Neo4j driver."""
        if self._neo4j_driver is not None:
            return self._neo4j_driver

        try:
            from neo4j import GraphDatabase
        except ImportError:
            raise ImportError(
                "neo4j package is required. Install with: pip install neo4j"
            )

        uri, user, password, _ = self._get_config()
        if not uri or not password:
            return None

        # Use short connection timeout from config
        connect_timeout = get_timeout("neo4j_connect", default=5.0)
        self._neo4j_driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=connect_timeout,
        )
        return self._neo4j_driver

    def health_check(self) -> bool:
        """Check if the knowledge graph is accessible.

        Uses circuit breaker state for fast-fail and reuses cached driver.
        """
        # Fast-fail if circuit breaker is open
        try:
            from src.rag.rag_resilience import get_neo4j_circuit_breaker
            from src.utils.resilience import CircuitState

            cb = get_neo4j_circuit_breaker()
            if cb.state == CircuitState.OPEN:
                logger.debug("Neo4j circuit breaker open, health check returns False")
                return False
        except ImportError:
            pass  # Resilience module not available

        try:
            driver = self._get_neo4j_driver()
            if driver is None:
                return False

            with driver.session() as session:
                result = session.run("RETURN 1 as n")
                success = result.single()["n"] == 1
                if success:
                    self._record_success()
                return success
        except Exception as e:
            logger.debug(f"Graphiti health check failed: {e}")
            self._record_failure()
            return False

    def close(self):
        """Close the client connection and cached driver."""
        if self._client:
            try:
                worker = _get_async_worker()
                worker.run_coroutine(self._client.close())
            except Exception:
                pass
            self._client = None
            self._initialized = False

        # Also close cached driver
        if self._neo4j_driver:
            try:
                self._neo4j_driver.close()
            except Exception:
                pass
            self._neo4j_driver = None


# Singleton instance
_graphiti_client: Optional[GraphitiClient] = None


def get_graphiti_client() -> Optional[GraphitiClient]:
    """Get the global Graphiti client instance."""
    global _graphiti_client

    if _graphiti_client is None:
        uri = os.environ.get("NEO4J_URI")
        if not uri:
            try:
                from src.settings.settings import SETTINGS
                uri = SETTINGS.get("graphiti_neo4j_uri")
            except Exception:
                pass

        if not uri:
            logger.debug("Graphiti not configured - Neo4j URI not found")
            return None

        try:
            _graphiti_client = GraphitiClient()
        except Exception as e:
            logger.warning(f"Failed to create Graphiti client: {e}")
            return None

    return _graphiti_client


def reset_graphiti_client():
    """Reset the global Graphiti client instance."""
    global _graphiti_client
    if _graphiti_client:
        _graphiti_client.close()
        _graphiti_client = None
