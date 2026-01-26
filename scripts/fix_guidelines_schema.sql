-- Fix Guidelines Database Schema Issues
-- Run with: python scripts/run_guidelines_migration.py (this will be updated to use this file)

-- Issue 1: Add missing updated_at column to guideline_embeddings
-- The Python code expects this column but it wasn't created in the initial migration
ALTER TABLE guideline_embeddings
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Issue 2: Add unique constraint on (guideline_id, chunk_index)
-- The Python upsert code uses ON CONFLICT (guideline_id, chunk_index)
-- but this constraint doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'guideline_embeddings'
        AND constraint_name = 'guideline_embeddings_unique_chunk'
    ) THEN
        ALTER TABLE guideline_embeddings
        ADD CONSTRAINT guideline_embeddings_unique_chunk
        UNIQUE (guideline_id, chunk_index);
    END IF;
END $$;

-- Verify changes
SELECT 'Schema fixes applied successfully:' as info;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'guideline_embeddings'
AND column_name = 'updated_at';

SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'guideline_embeddings'
AND constraint_name = 'guideline_embeddings_unique_chunk';
