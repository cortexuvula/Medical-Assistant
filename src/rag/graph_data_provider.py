"""
Graph data models and provider for Knowledge Graph visualization.

Provides data structures and Neo4j query layer for extracting
nodes and relationships from the Graphiti knowledge graph.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


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
    """An edge (relationship) in the knowledge graph visualization."""
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    fact: str = ""
    properties: dict = field(default_factory=dict)

    @property
    def display_type(self) -> str:
        """Get a display-friendly relationship type."""
        # Convert SCREAMING_SNAKE_CASE to Title Case
        return self.relationship_type.replace("_", " ").title()


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
    """Provides graph data from Neo4j for visualization."""

    def __init__(self, graphiti_client=None):
        """Initialize the provider.

        Args:
            graphiti_client: Optional GraphitiClient instance
        """
        self._client = graphiti_client
        self._driver = None

    def _get_neo4j_driver(self):
        """Get or create Neo4j driver."""
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
                from src.settings.settings import SETTINGS
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

        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        return self._driver

    def get_full_graph_data(
        self,
        limit: int = 500,
        entity_types: Optional[list[str]] = None,
    ) -> GraphData:
        """Get all nodes and relationships from the knowledge graph.

        Args:
            limit: Maximum number of nodes to return
            entity_types: Optional list of entity types to filter by

        Returns:
            GraphData containing nodes and edges
        """
        driver = self._get_neo4j_driver()

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
                return GraphData(nodes=nodes, edges=edges)

        except Exception as e:
            logger.error(f"Failed to retrieve graph data: {e}")
            raise

    def health_check(self) -> bool:
        """Check if Neo4j connection is available."""
        try:
            driver = self._get_neo4j_driver()
            with driver.session() as session:
                result = session.run("RETURN 1 as n")
                return result.single()["n"] == 1
        except Exception as e:
            logger.debug(f"Graph health check failed: {e}")
            return False

    def close(self):
        """Close the Neo4j driver."""
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None
