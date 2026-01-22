# ADR-003: Neon PostgreSQL + Neo4j for RAG Architecture

## Status

Accepted

## Date

2024-08

## Context

Medical Assistant's RAG (Retrieval-Augmented Generation) system needs to:

1. **Store document embeddings** for semantic search across clinical documents
2. **Model relationships** between medical entities (medications, conditions, procedures)
3. **Support hybrid search** combining vector similarity with keyword/graph traversal
4. **Scale** to thousands of documents per user
5. **Persist** data across sessions (not just in-memory)

The system processes clinical documentation containing interconnected medical concepts that benefit from both semantic similarity search and explicit relationship modeling.

## Decision

We chose a **hybrid database architecture**:

- **Neon PostgreSQL with pgvector** for vector embeddings and full-text search
- **Neo4j** (via Graphiti) for knowledge graph storage and relationship queries

```
┌─────────────────────────────────────────────────────────────┐
│                     Hybrid Retriever                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐       ┌─────────────────────────┐ │
│  │   Neon PostgreSQL   │       │        Neo4j            │ │
│  │   (pgvector)        │       │      (Graphiti)         │ │
│  ├─────────────────────┤       ├─────────────────────────┤ │
│  │ • Document chunks   │       │ • EntityNode            │ │
│  │ • Embeddings        │       │ • EpisodicNode          │ │
│  │ • BM25 full-text    │       │ • Relationships         │ │
│  │ • HNSW index        │       │ • Temporal facts        │ │
│  └─────────────────────┘       └─────────────────────────┘ │
│           │                              │                  │
│           └──────────┬───────────────────┘                  │
│                      ▼                                      │
│              Hybrid Search Results                          │
│       (vector + BM25 + graph, MMR reranked)                │
└─────────────────────────────────────────────────────────────┘
```

## Consequences

### Positive

- **Best of both worlds**: Vector similarity for semantic search, graph for relationship traversal
- **Neon serverless**: Auto-scaling, no infrastructure management, generous free tier
- **pgvector maturity**: Production-ready vector extension with HNSW indexes
- **Neo4j graph power**: Cypher queries for complex relationship patterns
- **Graphiti integration**: Pre-built entity extraction and temporal reasoning
- **Hybrid scoring**: Configurable weights (vector: 0.5, BM25: 0.3, graph: 0.2)
- **BM25 fallback**: Keyword search works even if embeddings fail
- **Entity-centric**: Medical entities (medications, conditions) are first-class graph nodes

### Negative

- **Two databases**: Operational complexity, two connection pools, two failure modes
- **Data synchronization**: Must keep vector store and graph in sync
- **Cost**: Two managed services (though both have free tiers)
- **Latency**: Graph queries add ~50-100ms to search time
- **Learning curve**: Contributors need to understand both pgvector and Cypher
- **Graphiti dependency**: Tied to Graphiti's entity extraction patterns

### Neutral

- Neon and Neo4j both offer cloud-hosted options with local alternatives
- Graph population requires explicit entity extraction step during ingestion

## Alternatives Considered

### Single Database: PostgreSQL Only (pgvector + pg_graphql)

**Rejected because:**
- Graph queries in SQL are cumbersome (recursive CTEs)
- No native graph traversal optimization
- Entity relationships would be awkward foreign key chains
- Lost the semantic richness of a property graph model

### Single Database: Neo4j Only (with vector indexes)

**Rejected because:**
- Neo4j vector search is newer and less mature than pgvector
- Higher cost for vector-heavy workloads
- BM25/full-text search less powerful than PostgreSQL
- Overkill if graph features aren't heavily used

### Pinecone / Weaviate / Qdrant (Dedicated Vector DB)

**Rejected because:**
- Another service to manage
- Pinecone: Proprietary, vendor lock-in
- Weaviate/Qdrant: Self-hosting complexity
- pgvector is "good enough" and integrated with familiar PostgreSQL
- Neon provides managed PostgreSQL with pgvector included

### ChromaDB / FAISS (In-Memory / Local)

**Rejected because:**
- Not suitable for persistent, multi-session data
- ChromaDB: Limited scalability
- FAISS: No persistence without custom serialization
- Both: No cloud sync or multi-device access

### LlamaIndex / LangChain RAG Abstractions

**Rejected because:**
- Added abstraction layer without clear benefit
- We need fine-grained control over search scoring
- Medical domain requires custom query expansion and entity handling
- Framework overhead for our specific use case

## Implementation Details

### Neon Vector Store (`src/rag/neon_vector_store.py`)

- HNSW index for approximate nearest neighbor (10-50x faster than brute force)
- Cosine similarity for semantic matching
- BM25 via PostgreSQL `tsvector` for keyword search
- Connection pooling via `psycopg_pool`

### Neo4j Knowledge Graph (`src/rag/graphiti_client.py`)

- EntityNode: Medications, conditions, symptoms, procedures, anatomy
- EpisodicNode: Document-specific facts with temporal context
- Relationships: TREATS, CAUSES, INDICATES, CONTRAINDICATES, etc.

### Hybrid Retriever (`src/rag/hybrid_retriever.py`)

- Combines vector, BM25, and graph results
- Configurable weights via `SearchQualityConfig`
- MMR reranking for diversity
- Adaptive similarity threshold
- Medical query expansion

### Search Quality Features

| Feature | Component | Purpose |
|---------|-----------|---------|
| Query expansion | `query_expander.py` | Medical abbreviations and synonyms |
| Adaptive threshold | `adaptive_threshold.py` | Dynamic cutoff based on score distribution |
| BM25 hybrid | `bm25_search.py` | Keyword matching alongside vectors |
| MMR diversity | `mmr_reranker.py` | Reduce redundancy in results |
| Feedback boosts | `feedback_manager.py` | User upvotes/downvotes affect ranking |

## References

- [Neon PostgreSQL](https://neon.tech/)
- [pgvector extension](https://github.com/pgvector/pgvector)
- [Neo4j](https://neo4j.com/)
- [Graphiti](https://github.com/getzep/graphiti)
- [src/rag/](../../src/rag/) - RAG implementation
