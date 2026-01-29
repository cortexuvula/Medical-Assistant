"""
Graph data models and provider for Knowledge Graph visualization.

Provides data structures and Neo4j query layer for extracting
nodes and relationships from the Graphiti knowledge graph.

Enhanced with:
- Relationship confidence scoring
- Evidence-based reliability metrics
- Circuit breaker for graceful degradation
- Driver reuse for efficiency
"""

import os
import pathlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from dotenv import load_dotenv

from utils.structured_logging import get_logger
from utils.timeout_config import get_timeout

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

logger = get_logger(__name__)


class EntityType(str, Enum):
    """Entity types for knowledge graph nodes."""
    MEDICATION = "medication"
    CONDITION = "condition"
    SYMPTOM = "symptom"
    PROCEDURE = "procedure"
    LAB_TEST = "lab_test"
    ANATOMY = "anatomy"
    DOCUMENT = "document"
    EPISODE = "episode"
    ENTITY = "entity"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "EntityType":
        """Convert string to EntityType, defaulting to UNKNOWN."""
        if not value:
            return cls.UNKNOWN

        value_lower = value.lower().strip()

        # Direct match
        for member in cls:
            if member.value == value_lower:
                return member

        # Fuzzy matching for common variations
        mappings = {
            "drug": cls.MEDICATION,
            "medicine": cls.MEDICATION,
            "pharmaceutical": cls.MEDICATION,
            "disease": cls.CONDITION,
            "diagnosis": cls.CONDITION,
            "disorder": cls.CONDITION,
            "illness": cls.CONDITION,
            "sign": cls.SYMPTOM,
            "finding": cls.SYMPTOM,
            "presentation": cls.SYMPTOM,
            "surgery": cls.PROCEDURE,
            "operation": cls.PROCEDURE,
            "treatment": cls.PROCEDURE,
            "intervention": cls.PROCEDURE,
            "test": cls.LAB_TEST,
            "lab": cls.LAB_TEST,
            "laboratory": cls.LAB_TEST,
            "biomarker": cls.LAB_TEST,
            "body_part": cls.ANATOMY,
            "organ": cls.ANATOMY,
            "structure": cls.ANATOMY,
            "doc": cls.DOCUMENT,
            "file": cls.DOCUMENT,
            "source": cls.DOCUMENT,
            "event": cls.EPISODE,
            "episodic": cls.EPISODE,
        }

        for key, entity_type in mappings.items():
            if key in value_lower:
                return entity_type

        return cls.UNKNOWN


@dataclass
class GraphNode:
    """A node in the knowledge graph visualization."""
    id: str
    name: str
    entity_type: EntityType
    properties: dict = field(default_factory=dict)
    x: float = 0.0  # Canvas position
    y: float = 0.0

    @property
    def display_name(self) -> str:
        """Get a display-friendly name."""
        if len(self.name) > 30:
            return self.name[:27] + "..."
        return self.name

    def matches_search(self, query: str) -> bool:
        """Check if node matches a search query."""
        query_lower = query.lower()
        return (
            query_lower in self.name.lower() or
            query_lower in self.entity_type.value.lower() or
            any(query_lower in str(v).lower() for v in self.properties.values())
        )


@dataclass
class GraphEdge:
    """An edge (relationship) in the knowledge graph visualization.

    Enhanced with confidence scoring and evidence tracking for
    weighted relationship queries.
    """
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    fact: str = ""
    properties: dict = field(default_factory=dict)

    # Confidence scoring fields
    confidence: float = 1.0  # 0.0-1.0 confidence score
    evidence_count: int = 1  # Number of supporting documents
    source_documents: list[str] = field(default_factory=list)
    evidence_type: str = "inferred"  # "explicit", "inferred", "aggregated"
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    @property
    def display_type(self) -> str:
        """Get a display-friendly relationship type."""
        # Convert SCREAMING_SNAKE_CASE to Title Case
        return self.relationship_type.replace("_", " ").title()

    @property
    def reliability_score(self) -> float:
        """Calculate combined reliability considering confidence and evidence.

        Returns:
            Reliability score (0.0-1.0) factoring in:
            - Base confidence
            - Evidence count (more sources = more reliable)
            - Recency (newer = more reliable)
        """
        # More evidence = higher reliability (capped at 3 sources)
        evidence_factor = min(1.0, self.evidence_count / 3)

        # Recency boost (within last year is most relevant)
        recency_factor = 0.5  # Default if no timestamp
        if self.last_seen:
            days_old = (datetime.now() - self.last_seen).days
            recency_factor = max(0.5, 1.0 - (days_old / 365))

        return self.confidence * (0.5 + 0.3 * evidence_factor + 0.2 * recency_factor)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type,
            "fact": self.fact,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "reliability_score": self.reliability_score,
            "evidence_type": self.evidence_type,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class RelationshipConfidenceCalculator:
    """Calculates and updates relationship confidence scores.

    Provides methods for:
    - Initial confidence calculation based on extraction method
    - Confidence merging when same relationship is found again
    - Confidence boosting for multiple evidence sources
    """

    # Base confidence by extraction method
    BASE_CONFIDENCE = {
        "explicit": 0.95,    # Explicitly stated in text
        "inferred": 0.70,    # Inferred from context
        "aggregated": 0.85,  # Multiple sources agree
        "user_validated": 0.99,  # User confirmed
    }

    # Relationship types that require higher evidence threshold
    HIGH_EVIDENCE_TYPES = {
        "treats", "causes", "contraindicated", "interacts_with",
        "increases_risk", "decreases_risk"
    }

    def calculate_confidence(
        self,
        relationship_type: str,
        evidence_text: str,
        extraction_method: str,
        existing_evidence_count: int = 0
    ) -> float:
        """Calculate confidence score for a relationship.

        Args:
            relationship_type: Type of relationship
            evidence_text: Text supporting the relationship
            extraction_method: How the relationship was extracted
            existing_evidence_count: Number of existing supporting documents

        Returns:
            Confidence score (0.0-1.0)
        """
        # Start with base confidence for extraction method
        base = self.BASE_CONFIDENCE.get(extraction_method, 0.5)

        # Boost for more evidence
        evidence_boost = min(0.2, existing_evidence_count * 0.05)

        # Boost for certain relationship types if well-evidenced
        type_boost = 0.0
        if relationship_type in self.HIGH_EVIDENCE_TYPES:
            # Clinical relationships need higher evidence
            if existing_evidence_count >= 2:
                type_boost = 0.1
            elif existing_evidence_count == 0:
                # Penalize single-source clinical claims
                base *= 0.9

        # Check evidence quality (longer text generally means more context)
        if evidence_text:
            text_quality = min(0.1, len(evidence_text) / 1000)
        else:
            text_quality = 0.0

        return min(1.0, base + evidence_boost + type_boost + text_quality)

    def merge_confidence(
        self,
        existing_confidence: float,
        new_confidence: float,
        existing_count: int
    ) -> float:
        """Merge confidence when same relationship found again.

        Uses weighted average with corroboration boost.

        Args:
            existing_confidence: Current confidence score
            new_confidence: New evidence confidence
            existing_count: Number of existing evidence sources

        Returns:
            Merged confidence score
        """
        # Weighted average favoring more evidence
        total_count = existing_count + 1
        weighted = (
            existing_confidence * existing_count + new_confidence
        ) / total_count

        # Boost for corroboration (agreement between sources)
        corroboration_boost = min(0.15, 0.05 * existing_count)

        return min(1.0, weighted + corroboration_boost)

    def should_merge_relationships(
        self,
        edge1: GraphEdge,
        edge2: GraphEdge
    ) -> bool:
        """Determine if two edges should be merged as same relationship.

        Args:
            edge1: First edge
            edge2: Second edge

        Returns:
            True if edges represent same relationship
        """
        return (
            edge1.source_id == edge2.source_id and
            edge1.target_id == edge2.target_id and
            edge1.relationship_type == edge2.relationship_type
        )

    def merge_edges(self, edge1: GraphEdge, edge2: GraphEdge) -> GraphEdge:
        """Merge two edges representing the same relationship.

        Args:
            edge1: Primary edge (will be modified)
            edge2: Secondary edge (source of new evidence)

        Returns:
            Merged edge
        """
        # Merge confidence
        edge1.confidence = self.merge_confidence(
            edge1.confidence,
            edge2.confidence,
            edge1.evidence_count
        )

        # Increment evidence count
        edge1.evidence_count += edge2.evidence_count

        # Merge source documents
        for doc_id in edge2.source_documents:
            if doc_id not in edge1.source_documents:
                edge1.source_documents.append(doc_id)

        # Update timestamps
        if edge2.first_seen:
            if not edge1.first_seen or edge2.first_seen < edge1.first_seen:
                edge1.first_seen = edge2.first_seen

        if edge2.last_seen:
            if not edge1.last_seen or edge2.last_seen > edge1.last_seen:
                edge1.last_seen = edge2.last_seen

        # Merge facts if different
        if edge2.fact and edge2.fact != edge1.fact:
            if edge1.fact:
                edge1.fact = f"{edge1.fact}; {edge2.fact}"
            else:
                edge1.fact = edge2.fact

        # Update evidence type to aggregated
        edge1.evidence_type = "aggregated"

        return edge1


@dataclass
class GraphData:
    """Container for graph nodes and edges."""
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_edges_for_node(self, node_id: str) -> list[GraphEdge]:
        """Get all edges connected to a node."""
        return [
            edge for edge in self.edges
            if edge.source_id == node_id or edge.target_id == node_id
        ]

    def get_connected_nodes(self, node_id: str) -> list[GraphNode]:
        """Get all nodes connected to a given node."""
        connected_ids = set()
        for edge in self.edges:
            if edge.source_id == node_id:
                connected_ids.add(edge.target_id)
            elif edge.target_id == node_id:
                connected_ids.add(edge.source_id)

        return [node for node in self.nodes if node.id in connected_ids]

    def filter_by_type(self, entity_type: EntityType) -> "GraphData":
        """Return a new GraphData filtered to only include nodes of the given type."""
        filtered_nodes = [n for n in self.nodes if n.entity_type == entity_type]
        filtered_node_ids = {n.id for n in filtered_nodes}

        # Include edges where both endpoints are in the filtered set
        filtered_edges = [
            e for e in self.edges
            if e.source_id in filtered_node_ids and e.target_id in filtered_node_ids
        ]

        return GraphData(nodes=filtered_nodes, edges=filtered_edges)

    def search(self, query: str) -> list[GraphNode]:
        """Search nodes matching the query."""
        if not query:
            return self.nodes
        return [node for node in self.nodes if node.matches_search(query)]


class GraphDataProvider:
    """Provides graph data from Neo4j for visualization.

    Enhanced with circuit breaker for resilience.
    """

    def __init__(self, graphiti_client=None):
        """Initialize the provider.

        Args:
            graphiti_client: Optional GraphitiClient instance
        """
        self._client = graphiti_client
        self._driver = None

    def _get_neo4j_driver(self):
        """Get or create Neo4j driver with connection timeout."""
        if self._driver is not None:
            return self._driver

        import os
        try:
            from neo4j import GraphDatabase
        except ImportError:
            raise ImportError(
                "neo4j package is required. Install with: pip install neo4j"
            )

        # Get config from environment or settings
        uri = os.environ.get("NEO4J_URI")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD")

        if not uri or not password:
            try:
                from settings.settings import SETTINGS
                uri = uri or SETTINGS.get("graphiti_neo4j_uri")
                user = user or SETTINGS.get("graphiti_neo4j_user", "neo4j")
                password = password or SETTINGS.get("graphiti_neo4j_password")
            except Exception:
                pass

        if not uri or not password:
            raise ValueError(
                "Neo4j connection details not found. "
                "Set NEO4J_URI and NEO4J_PASSWORD environment variables."
            )

        # Use short connection timeout from config
        connect_timeout = get_timeout("neo4j_connect", default=5.0)
        self._driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=connect_timeout,
        )
        return self._driver

    def _record_success(self):
        """Record successful operation for circuit breaker."""
        try:
            from rag.rag_resilience import get_neo4j_circuit_breaker
            cb = get_neo4j_circuit_breaker()
            cb._on_success()
        except Exception:
            pass

    def _record_failure(self):
        """Record failed operation for circuit breaker."""
        try:
            from rag.rag_resilience import get_neo4j_circuit_breaker
            cb = get_neo4j_circuit_breaker()
            cb._on_failure()
        except Exception:
            pass

    def get_full_graph_data(
        self,
        limit: int = 500,
        entity_types: Optional[list[str]] = None,
    ) -> GraphData:
        """Get all nodes and relationships from the knowledge graph.

        Uses circuit breaker to fail fast when Neo4j is unavailable.

        Args:
            limit: Maximum number of nodes to return
            entity_types: Optional list of entity types to filter by

        Returns:
            GraphData containing nodes and edges (empty if circuit breaker open)
        """
        # Check circuit breaker first for fast fail
        try:
            from rag.rag_resilience import get_neo4j_circuit_breaker
            from utils.resilience import CircuitState

            cb = get_neo4j_circuit_breaker()
            if cb.state == CircuitState.OPEN:
                logger.warning("Neo4j circuit breaker open, returning empty graph data")
                return GraphData(nodes=[], edges=[])
        except ImportError:
            pass  # Resilience module not available

        try:
            driver = self._get_neo4j_driver()
        except Exception as e:
            logger.error(f"Failed to get Neo4j driver: {e}")
            self._record_failure()
            return GraphData(nodes=[], edges=[])

        nodes = []
        edges = []
        node_ids = set()

        try:
            with driver.session() as session:
                # First, try Graphiti-specific labels (EntityNode, EpisodicNode)
                # If no results, fall back to querying all nodes
                node_query = """
                MATCH (n)
                WHERE n:EntityNode OR n:EpisodicNode OR n:Entity OR n:Episode
                   OR n:Medication OR n:Condition OR n:Symptom OR n:Procedure
                   OR n:Document OR n:Chunk
                RETURN
                    elementId(n) as id,
                    coalesce(n.name, n.title, n.content, n.text, 'Unknown') as name,
                    coalesce(n.entity_type, n.type, labels(n)[0], 'entity') as entity_type,
                    properties(n) as props
                LIMIT $limit
                """

                result = session.run(node_query, limit=limit)

                for record in result:
                    node_id = record["id"]
                    entity_type_str = record["entity_type"]

                    # Filter by entity type if specified
                    if entity_types:
                        entity_type = EntityType.from_string(entity_type_str)
                        if entity_type.value not in entity_types:
                            continue

                    props = record["props"] or {}
                    # Remove large properties that aren't needed for visualization
                    props.pop("embedding", None)
                    props.pop("content", None)

                    node = GraphNode(
                        id=node_id,
                        name=record["name"],
                        entity_type=EntityType.from_string(entity_type_str),
                        properties=props,
                    )
                    nodes.append(node)
                    node_ids.add(node_id)

                # If no nodes found with specific labels, try querying ALL nodes
                if not node_ids:
                    logger.info("No nodes found with expected labels, trying all nodes...")

                    # Log available labels for debugging
                    labels_result = session.run("CALL db.labels() YIELD label RETURN collect(label) as labels")
                    labels_record = labels_result.single()
                    if labels_record:
                        logger.info(f"Available labels in database: {labels_record['labels']}")

                    # Try getting all nodes
                    fallback_query = """
                    MATCH (n)
                    RETURN
                        elementId(n) as id,
                        coalesce(n.name, n.title, n.content, n.text, 'Unknown') as name,
                        coalesce(n.entity_type, n.type, labels(n)[0], 'entity') as entity_type,
                        properties(n) as props
                    LIMIT $limit
                    """
                    result = session.run(fallback_query, limit=limit)

                    for record in result:
                        node_id = record["id"]
                        entity_type_str = record["entity_type"]

                        props = record["props"] or {}
                        props.pop("embedding", None)
                        props.pop("content", None)

                        node = GraphNode(
                            id=node_id,
                            name=record["name"],
                            entity_type=EntityType.from_string(entity_type_str),
                            properties=props,
                        )
                        nodes.append(node)
                        node_ids.add(node_id)

                if not node_ids:
                    logger.info("No nodes found in the knowledge graph")
                    return GraphData(nodes=[], edges=[])

                # Query for relationships between retrieved nodes
                edge_query = """
                MATCH (n)-[r]->(m)
                WHERE elementId(n) IN $node_ids AND elementId(m) IN $node_ids
                RETURN
                    elementId(r) as id,
                    elementId(n) as source,
                    elementId(m) as target,
                    type(r) as rel_type,
                    coalesce(r.fact, '') as fact,
                    properties(r) as props
                """

                result = session.run(edge_query, node_ids=list(node_ids))

                for record in result:
                    props = record["props"] or {}
                    props.pop("embedding", None)

                    edge = GraphEdge(
                        id=record["id"],
                        source_id=record["source"],
                        target_id=record["target"],
                        relationship_type=record["rel_type"],
                        fact=record["fact"],
                        properties=props,
                    )
                    edges.append(edge)

                logger.info(f"Retrieved {len(nodes)} nodes and {len(edges)} edges")
                self._record_success()
                return GraphData(nodes=nodes, edges=edges)

        except Exception as e:
            logger.error(f"Failed to retrieve graph data: {e}")
            self._record_failure()
            raise

    def health_check(self) -> bool:
        """Check if Neo4j connection is available.

        Uses circuit breaker state for fast-fail.
        """
        # Fast-fail if circuit breaker is open
        try:
            from rag.rag_resilience import get_neo4j_circuit_breaker
            from utils.resilience import CircuitState

            cb = get_neo4j_circuit_breaker()
            if cb.state == CircuitState.OPEN:
                logger.debug("Neo4j circuit breaker open, health check returns False")
                return False
        except ImportError:
            pass

        try:
            driver = self._get_neo4j_driver()
            with driver.session() as session:
                result = session.run("RETURN 1 as n")
                success = result.single()["n"] == 1
                if success:
                    self._record_success()
                return success
        except Exception as e:
            logger.debug(f"Graph health check failed: {e}")
            self._record_failure()
            return False

    def close(self):
        """Close the Neo4j driver."""
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None
