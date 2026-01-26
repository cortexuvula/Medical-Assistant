-- Clinical Guidelines Database Schema
-- Run with: psql 'postgresql://neondb_owner:npg_i40RlDLHzceB@ep-restless-scene-aha4yrpo-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require' -f scripts/setup_guidelines_db.sql

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create guidelines table (metadata for uploaded guideline documents)
CREATE TABLE IF NOT EXISTS guidelines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    specialty TEXT NOT NULL,
    source TEXT NOT NULL,
    version TEXT,
    effective_date DATE,
    document_type TEXT,
    file_path TEXT,
    file_hash TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create guideline_embeddings table (chunks with vectors)
CREATE TABLE IF NOT EXISTS guideline_embeddings (
    id SERIAL PRIMARY KEY,
    guideline_id UUID REFERENCES guidelines(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    section_type TEXT,  -- 'recommendation', 'warning', 'evidence', 'background'
    recommendation_class TEXT,  -- 'I', 'IIa', 'IIb', 'III'
    evidence_level TEXT,  -- 'A', 'B', 'C'
    embedding vector(1536),
    search_vector tsvector,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (guideline_id, chunk_index)  -- Required for upsert operations
);

-- Create indexes for fast similarity search (HNSW)
CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_vector
ON guideline_embeddings USING hnsw (embedding vector_cosine_ops);

-- Create GIN index for BM25 full-text search
CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_search
ON guideline_embeddings USING gin (search_vector);

-- Create indexes for filtering
CREATE INDEX IF NOT EXISTS idx_guidelines_specialty ON guidelines(specialty);
CREATE INDEX IF NOT EXISTS idx_guidelines_source ON guidelines(source);
CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_guideline_id ON guideline_embeddings(guideline_id);
CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_recommendation_class ON guideline_embeddings(recommendation_class);

-- Create function to auto-update search_vector
CREATE OR REPLACE FUNCTION update_guideline_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating search_vector
DROP TRIGGER IF EXISTS trigger_update_guideline_search_vector ON guideline_embeddings;
CREATE TRIGGER trigger_update_guideline_search_vector
    BEFORE INSERT OR UPDATE ON guideline_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_guideline_search_vector();

-- Create updated_at trigger for guidelines
CREATE OR REPLACE FUNCTION update_guidelines_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_guidelines_updated_at ON guidelines;
CREATE TRIGGER trigger_guidelines_updated_at
    BEFORE UPDATE ON guidelines
    FOR EACH ROW
    EXECUTE FUNCTION update_guidelines_updated_at();

-- Verify setup
SELECT 'Extensions:' as info;
SELECT extname FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp');

SELECT 'Tables created:' as info;
SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('guidelines', 'guideline_embeddings');

SELECT 'Indexes created:' as info;
SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename IN ('guidelines', 'guideline_embeddings');
