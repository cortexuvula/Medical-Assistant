"""
Clinical Guidelines Graphiti Client for Knowledge Graph Integration.

Separate Graphiti client for clinical guidelines, isolated from patient documents.
Uses Zep AI's Graphiti SDK for building and querying temporal knowledge graphs.

Architecture Note:
    This client uses SEPARATE Neo4j credentials (CLINICAL_GUIDELINES_NEO4J_*)
    to ensure complete isolation from patient data in the main knowledge graph.
"""

import asyncio
import atexit
import logging
import time
from utils.structured_logging import get_logger
import os
import threading
from datetime import datetime
from typing import Any, Optional

from rag.guidelines_env import load_guidelines_env
from rag.guidelines_models import GuidelineSearchResult
from utils.timeout_config import get_timeout

load_guidelines_env()

logger = get_logger(__name__)


# Suppress noisy graphiti-core / neo4j errors that are harmless:
# - "EquivalentSchemaRuleAlreadyExists" from index creation on startup
# - "property key does not exist" warnings for optional properties
# - "index or constraint already exists" INFO-level notifications (gql_status 00NA0)
# - "Received notification from DBMS server" general notification noise
class _GraphitiNoiseFilter(logging.Filter):
    """Filter harmless Neo4j/Graphiti log noise."""

    _SUPPRESS = (
        "EquivalentSchemaRuleAlreadyExists",
        "equivalent index already exists",
        "index or constraint already exists",
        "property key does not exist",
        "Received notification from DBMS server",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(s in msg for s in self._SUPPRESS)


for _logger_name in (
    "graphiti_core.driver.neo4j_driver",
    "graphiti_core.driver",
    "neo4j",
    "neo4j.notifications",
    "neo4j.io",
    "neo4j.pool",
):
    logging.getLogger(_logger_name).addFilter(_GraphitiNoiseFilter())


class _GuidelinesAsyncWorker:
    """Dedicated async worker thread for Guidelines Graphiti operations.

    Separate from main Graphiti worker to ensure isolation.
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
            name="guidelines-graphiti-worker",
        )
        self._thread.start()
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
        """Run a coroutine in the worker's event loop."""
        if self._loop is None or self._stopped:
            raise RuntimeError("Guidelines async worker not running")

        if timeout is None:
            timeout = get_timeout("neo4j", default=30.0)

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def stop(self):
        """Stop the worker thread."""
        if self._loop is not None and not self._stopped:
            self._stopped = True
            self._loop.call_soon_threadsafe(self._loop.stop)


# Global async worker for guidelines
_guidelines_async_worker: Optional[_GuidelinesAsyncWorker] = None
_guidelines_worker_lock = threading.Lock()


def _get_guidelines_async_worker() -> _GuidelinesAsyncWorker:
    """Get or create the global guidelines async worker."""
    global _guidelines_async_worker
    with _guidelines_worker_lock:
        if _guidelines_async_worker is None:
            _guidelines_async_worker = _GuidelinesAsyncWorker()
            _guidelines_async_worker.start()
            atexit.register(_cleanup_guidelines_async_worker)
    return _guidelines_async_worker


def _cleanup_guidelines_async_worker():
    """Clean up the guidelines async worker on exit."""
    global _guidelines_async_worker
    if _guidelines_async_worker is not None:
        try:
            _guidelines_async_worker.stop()
        except Exception:
            pass
        _guidelines_async_worker = None


class GuidelinesGraphitiClient:
    """Client for Guidelines knowledge graph operations.

    Uses SEPARATE Neo4j database configured via CLINICAL_GUIDELINES_NEO4J_* vars.
    This ensures complete isolation from patient data.
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        """Initialize Guidelines Graphiti client.

        Args:
            neo4j_uri: Neo4j connection URI for guidelines DB
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            openai_api_key: OpenAI API key for entity extraction
        """
        self._neo4j_uri = neo4j_uri
        self._neo4j_user = neo4j_user
        self._neo4j_password = neo4j_password
        self._openai_api_key = openai_api_key
        self._client = None
        self._neo4j_driver = None
        self._initialized = False
        self._init_lock = threading.Lock()
        # Circuit breaker: skip operations for COOLDOWN seconds after a failure
        self._circuit_open_until: float = 0.0
        self._CIRCUIT_COOLDOWN = 120.0  # 2 minutes

    def _get_config(self):
        """Get configuration from environment or settings.

        Note: Uses CLINICAL_GUIDELINES_NEO4J_* environment variables,
        NOT the main NEO4J_* variables.
        """
        # Use CLINICAL_GUIDELINES_* env vars for isolation
        uri = self._neo4j_uri or os.environ.get("CLINICAL_GUIDELINES_NEO4J_URI")
        user = self._neo4j_user or os.environ.get("CLINICAL_GUIDELINES_NEO4J_USER", "neo4j")
        password = self._neo4j_password or os.environ.get("CLINICAL_GUIDELINES_NEO4J_PASSWORD")
        openai_key = self._openai_api_key or os.environ.get("OPENAI_API_KEY")

        # Fall back to settings if not in env
        if not uri or not password:
            try:
                from settings.settings import SETTINGS
                guidelines_settings = SETTINGS.get("clinical_guidelines", {})
                uri = uri or guidelines_settings.get("neo4j_uri")
                user = user or guidelines_settings.get("neo4j_user", "neo4j")
                password = password or guidelines_settings.get("neo4j_password")
            except Exception:
                pass

        # Get OpenAI key from API key manager if not set
        if not openai_key:
            try:
                from managers.api_key_manager import get_api_key_manager
                manager = get_api_key_manager()
                openai_key = manager.get_key("openai")
            except Exception:
                pass

        return uri, user, password, openai_key

    def _get_client(self):
        """Get or create Graphiti client for guidelines."""
        if self._client is not None:
            return self._client

        try:
            from graphiti_core import Graphiti
            from graphiti_core.llm_client import OpenAIClient
            from graphiti_core.llm_client.config import LLMConfig
        except ImportError:
            raise ImportError(
                "graphiti-core is required for guidelines knowledge graph features. "
                "Install with: pip install graphiti-core"
            )

        uri, user, password, openai_key = self._get_config()

        if not uri or not password:
            raise ValueError(
                "Clinical Guidelines Neo4j connection details not found. "
                "Set CLINICAL_GUIDELINES_NEO4J_URI and CLINICAL_GUIDELINES_NEO4J_PASSWORD."
            )

        if not openai_key:
            raise ValueError("OpenAI API key required for Guidelines Graphiti.")

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
        """Initialize the guidelines knowledge graph schema (async)."""
        client = self._get_client()
        await client.build_indices_and_constraints()
        logger.info("Guidelines knowledge graph initialized")

    def _ensure_vector_indexes(self):
        """Create vector indexes that graphiti-core does not create.

        graphiti-core queries RELATES_TO.fact_embedding with
        vector.similarity.cosine() but only creates range/fulltext
        indexes.  Without a vector index the query still works but
        triggers Neo4j warnings and uses brute-force scanning.
        """
        driver = self._get_neo4j_driver()
        if driver is None:
            return

        queries = [
            (
                "CREATE VECTOR INDEX rel_fact_embedding IF NOT EXISTS "
                "FOR ()-[r:RELATES_TO]-() ON (r.fact_embedding) "
                "OPTIONS {indexConfig: {"
                "`vector.dimensions`: 1536, "
                "`vector.similarity_function`: 'cosine'}}"
            ),
            (
                "CREATE VECTOR INDEX entity_name_embedding IF NOT EXISTS "
                "FOR (n:Entity) ON (n.name_embedding) "
                "OPTIONS {indexConfig: {"
                "`vector.dimensions`: 1536, "
                "`vector.similarity_function`: 'cosine'}}"
            ),
        ]

        try:
            with driver.session() as session:
                for query in queries:
                    try:
                        session.run(query)
                    except Exception as e:
                        logger.debug(f"Could not create vector index: {e}")
            logger.info("Guidelines Neo4j vector indexes ensured")
        except Exception as e:
            logger.warning(f"Failed to create Neo4j vector indexes: {e}")

    def _check_circuit(self) -> bool:
        """Check if the circuit breaker is open (Neo4j recently unreachable).

        Returns True if operations should be skipped.
        """
        if self._circuit_open_until > 0 and time.monotonic() < self._circuit_open_until:
            return True
        return False

    def _trip_circuit(self):
        """Open the circuit breaker after a connection failure."""
        self._circuit_open_until = time.monotonic() + self._CIRCUIT_COOLDOWN
        logger.warning(
            f"Neo4j circuit breaker tripped — skipping graph operations "
            f"for {self._CIRCUIT_COOLDOWN:.0f}s"
        )

    def initialize(self):
        """Initialize the guidelines knowledge graph schema (sync)."""
        with self._init_lock:
            if self._initialized:
                return
            if self._check_circuit():
                raise ConnectionError("Neo4j circuit breaker is open")

            try:
                worker = _get_guidelines_async_worker()
                worker.run_coroutine(self._initialize_async())
                self._ensure_vector_indexes()
                self._initialized = True
            except Exception:
                self._trip_circuit()
                raise

    async def _add_guideline_episode_async(
        self,
        guideline_id: str,
        content: str,
        metadata: Optional[dict] = None,
        source_description: str = "clinical_guideline",
    ):
        """Add guideline as episode (async)."""
        try:
            from graphiti_core.nodes import EpisodeType
        except ImportError:
            logger.warning("graphiti_core not available")
            return

        client = self._get_client()

        episode_name = f"guideline_{guideline_id}"
        description = source_description
        if metadata:
            if "title" in metadata and metadata["title"]:
                description = f"{metadata['title']}"
            if "source" in metadata:
                description = f"{description} ({metadata['source']})"
            if "version" in metadata:
                description = f"{description} v{metadata['version']}"
            if "specialty" in metadata and metadata["specialty"]:
                description = f"{description} [specialty: {metadata['specialty']}]"

        reference_time = self._extract_reference_time(metadata)

        await client.add_episode(
            name=episode_name,
            episode_body=content,
            source=EpisodeType.text,
            source_description=description,
            reference_time=reference_time,
        )
        logger.info(f"Added guideline {guideline_id} to knowledge graph")

    @staticmethod
    def _extract_reference_time(metadata: Optional[dict]) -> datetime:
        """Extract reference_time from metadata effective_date, falling back to now().

        Supports date, datetime, or ISO-format string values.
        """
        if metadata and "effective_date" in metadata and metadata["effective_date"]:
            ed = metadata["effective_date"]
            if isinstance(ed, datetime):
                return ed
            if hasattr(ed, 'year'):  # date object
                return datetime(ed.year, ed.month, ed.day)
            if isinstance(ed, str):
                try:
                    from datetime import date as date_type
                    parsed = date_type.fromisoformat(ed)
                    return datetime(parsed.year, parsed.month, parsed.day)
                except (ValueError, TypeError):
                    pass
        return datetime.now()

    def add_guideline_episode_sync(
        self,
        guideline_id: str,
        content: str,
        metadata: Optional[dict] = None,
        source_description: str = "clinical_guideline",
    ):
        """Add guideline as episode (sync)."""
        if self._check_circuit():
            logger.debug("Skipping graph episode add — circuit breaker open")
            return

        if not self._initialized:
            self.initialize()

        try:
            worker = _get_guidelines_async_worker()
            worker.run_coroutine(
                self._add_guideline_episode_async(
                    guideline_id, content, metadata, source_description
                )
            )
        except Exception:
            self._trip_circuit()
            raise

    async def _search_async(
        self,
        query: str,
        num_results: int = 10,
    ) -> list[dict]:
        """Search the guidelines knowledge graph (async)."""
        client = self._get_client()

        try:
            results = await client.search(query, num_results=num_results)

            graph_results = []
            for result in results:
                entity_name = getattr(result, "name", "")
                entity_type = getattr(result, "entity_type", "guideline")
                fact = getattr(result, "fact", getattr(result, "content", ""))
                source_desc = getattr(result, "source_description", None)

                # Extract guideline ID from episode name (format: "guideline_{uuid}")
                # Note: source_description contains title text, not the ID
                guideline_id = None
                episode_name = getattr(result, "name", "") or ""
                if episode_name.startswith("guideline_"):
                    guideline_id = episode_name[len("guideline_"):]
                elif source_desc and source_desc.startswith("guideline_"):
                    # Fallback to source_description for older episodes
                    guideline_id = source_desc[len("guideline_"):]

                graph_results.append({
                    "entity_name": entity_name,
                    "entity_type": entity_type,
                    "fact": fact,
                    "guideline_id": guideline_id,
                    "source_description": source_desc,
                    "relevance_score": 0.8,
                })

            return graph_results

        except Exception as e:
            logger.error(f"Guidelines knowledge graph search failed: {e}")
            return []

    def search(self, query: str, num_results: int = 10) -> list[dict]:
        """Search the guidelines knowledge graph (sync).

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            List of result dicts with entity_name, fact, guideline_id, etc.
        """
        if self._check_circuit():
            return []

        if not self._initialized:
            try:
                self.initialize()
            except Exception as e:
                logger.warning(f"Failed to initialize Guidelines Graphiti: {e}")
                return []

        try:
            worker = _get_guidelines_async_worker()
            return worker.run_coroutine(self._search_async(query, num_results))
        except Exception as e:
            self._trip_circuit()
            logger.warning(f"Guidelines graph search failed: {e}")
            return []

    async def _get_guideline_context_async(
        self,
        guideline_id: str,
    ) -> dict:
        """Get context around a guideline (async)."""
        client = self._get_client()

        try:
            search_results = await client.search(f"guideline_{guideline_id}", num_results=10)
            return {
                "guideline_id": guideline_id,
                "related_facts": [
                    getattr(r, "fact", getattr(r, "content", ""))
                    for r in search_results
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get guideline context: {e}")
            return {"guideline_id": guideline_id, "related_facts": []}

    def get_guideline_context(self, guideline_id: str) -> dict:
        """Get context around a guideline (sync)."""
        if not self._initialized:
            self.initialize()

        worker = _get_guidelines_async_worker()
        return worker.run_coroutine(
            self._get_guideline_context_async(guideline_id)
        )

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

        connect_timeout = get_timeout("neo4j_connect", default=5.0)
        self._neo4j_driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=connect_timeout,
        )
        return self._neo4j_driver

    def health_check(self) -> bool:
        """Check if the guidelines knowledge graph is accessible."""
        try:
            driver = self._get_neo4j_driver()
            if driver is None:
                return False

            with driver.session() as session:
                result = session.run("RETURN 1 as n")
                return result.single()["n"] == 1
        except Exception as e:
            logger.debug(f"Guidelines Graphiti health check failed: {e}")
            return False

    def close(self):
        """Close the client connection and cached driver."""
        if self._client:
            try:
                worker = _get_guidelines_async_worker()
                worker.run_coroutine(self._client.close())
            except Exception:
                pass
            self._client = None
            self._initialized = False

        if self._neo4j_driver:
            try:
                self._neo4j_driver.close()
            except Exception:
                pass
            self._neo4j_driver = None


# Singleton instance
_guidelines_graphiti_client: Optional[GuidelinesGraphitiClient] = None


def get_guidelines_graphiti_client() -> Optional[GuidelinesGraphitiClient]:
    """Get the global Guidelines Graphiti client instance."""
    global _guidelines_graphiti_client

    if _guidelines_graphiti_client is None:
        # Check if guidelines Neo4j is configured
        uri = os.environ.get("CLINICAL_GUIDELINES_NEO4J_URI")
        if not uri:
            try:
                from settings.settings import SETTINGS
                guidelines_settings = SETTINGS.get("clinical_guidelines", {})
                uri = guidelines_settings.get("neo4j_uri")
            except Exception:
                pass

        if not uri:
            logger.debug("Guidelines Graphiti not configured - Neo4j URI not found")
            return None

        try:
            _guidelines_graphiti_client = GuidelinesGraphitiClient()
        except Exception as e:
            logger.warning(f"Failed to create Guidelines Graphiti client: {e}")
            return None

    return _guidelines_graphiti_client


def reset_guidelines_graphiti_client():
    """Reset the global Guidelines Graphiti client instance."""
    global _guidelines_graphiti_client
    if _guidelines_graphiti_client:
        _guidelines_graphiti_client.close()
        _guidelines_graphiti_client = None
