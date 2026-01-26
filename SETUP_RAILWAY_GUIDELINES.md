# Railway + Graphiti + Neo4j Setup Guide

## Overview

This guide walks you through setting up the clinical guidelines compliance system with:
- **Railway**: Neo4j hosting with TCP proxy
- **Neon PostgreSQL**: Vector storage for guideline embeddings
- **Graphiti**: Knowledge graph for guideline entities and relationships

## Prerequisites

- Railway account with deployed `neo4j-guidelines` service
- Neon PostgreSQL database created
- Environment variables configured in `.env`
- Railway CLI installed (optional but recommended)

---

## Phase 1: Enable Railway TCP Proxy (MANUAL STEP)

⚠️ **CRITICAL**: Railway's HTTPS proxy doesn't support Neo4j's Bolt protocol (TCP port 7687). You must enable the TCP proxy manually.

### Step-by-Step Instructions

1. **Navigate to Railway Dashboard**
   ```
   https://railway.app/project/2cd02486-ccaf-4e2b-af67-aed24b40f073
   ```

2. **Select the Neo4j Service**
   - Click on `neo4j-guidelines` service

3. **Open Networking Settings**
   - Go to **Settings** tab
   - Click **Networking** section
   - Scroll to **Public Networking**

4. **Add TCP Proxy**
   - Click **"Add TCP Proxy"** button
   - Configure:
     - **Application Port**: `7687` (Neo4j Bolt)
     - Click **Add**

5. **Copy TCP Proxy Endpoint**
   - Railway will generate:
     - **TCP Proxy Domain**: (e.g., `monorail.proxy.rlwy.net`)
     - **TCP Proxy Port**: (e.g., `15432`)
   - **COPY THESE VALUES** - you'll need them next

### Expected Result

You should see something like:
```
TCP Proxy: monorail.proxy.rlwy.net:15432 → neo4j-guidelines:7687
```

---

## Phase 2: Update Environment Variables

### Edit `.env` File

Replace the Neo4j URI with your TCP proxy endpoint:

```bash
# Before (HTTPS proxy - doesn't work for Bolt):
CLINICAL_GUIDELINES_NEO4J_URI=bolt://neo4j-guidelines-production.up.railway.app:7687

# After (TCP proxy - works!):
CLINICAL_GUIDELINES_NEO4J_URI=bolt://<YOUR_TCP_PROXY_DOMAIN>:<YOUR_TCP_PROXY_PORT>
```

### Example

If Railway gave you:
- Domain: `monorail.proxy.rlwy.net`
- Port: `15432`

Your `.env` should have:
```bash
CLINICAL_GUIDELINES_NEO4J_URI=bolt://monorail.proxy.rlwy.net:15432
```

### Verify All Environment Variables

Make sure these are set in `.env`:

```bash
# PostgreSQL (Neon) - CREDENTIALS REDACTED
CLINICAL_GUIDELINES_DATABASE_URL=postgresql://[REDACTED]

# Neo4j (Railway with TCP Proxy) - CREDENTIALS REDACTED
CLINICAL_GUIDELINES_NEO4J_URI=bolt://<RAILWAY_TCP_PROXY_DOMAIN>:<RAILWAY_TCP_PROXY_PORT>
CLINICAL_GUIDELINES_NEO4J_USER=neo4j
CLINICAL_GUIDELINES_NEO4J_PASSWORD=[REDACTED]

# Required for embeddings - CREDENTIALS REDACTED
OPENAI_API_KEY=[REDACTED]
```

---

## Phase 3: Run PostgreSQL Migration

### Execute Migration Script

```bash
psql "$CLINICAL_GUIDELINES_DATABASE_URL" -f scripts/setup_guidelines_db.sql
```

### What This Creates

- **Extensions**:
  - `vector` - pgvector for embeddings
  - `uuid-ossp` - UUID generation

- **Tables**:
  - `guidelines` - Guideline metadata
  - `guideline_embeddings` - Chunks with vectors

- **Indexes**:
  - HNSW vector index for fast similarity search
  - GIN full-text search index for BM25
  - Filtering indexes for specialty, source, recommendation class

- **Triggers**:
  - Auto-update `search_vector` on insert/update
  - Auto-update `updated_at` timestamp

### Expected Output

```
CREATE EXTENSION
CREATE EXTENSION
CREATE TABLE
CREATE TABLE
CREATE INDEX
CREATE INDEX
...
Extensions:
vector
uuid-ossp

Tables created:
guidelines
guideline_embeddings

Indexes created:
idx_guideline_embeddings_vector
idx_guideline_embeddings_search
...
```

---

## Phase 4: Verify Setup

Run the test scripts in order:

### Test 1: Neo4j Connection

```bash
python scripts/test_neo4j_connection.py
```

**Expected output:**
```
================================================================================
Neo4j Connection Test
================================================================================

URI: bolt://monorail.proxy.rlwy.net:15432
User: neo4j
Password: ****************************

✓ Using Bolt protocol: monorail.proxy.rlwy.net:15432

🔄 Attempting connection...
✅ Connection successful!
   Database: Neo4j v5.15.0
   Total nodes: 0
```

**If this fails:**
- Verify TCP proxy is enabled in Railway dashboard
- Check credentials match Railway environment variables
- Test TCP connectivity: `nc -zv <domain> <port>`

---

### Test 2: Graphiti Client

```bash
python scripts/test_graphiti_client.py
```

**Expected output:**
```
================================================================================
Graphiti Client Health Test
================================================================================

✓ All required environment variables set

🔄 Importing GuidelinesGraphitiClient...
✅ Import successful
🔄 Initializing client...
✅ Client initialized
🔄 Running health check...
✅ Health check passed

📊 Graphiti Client Status:
   Neo4j URI: monorail.proxy.rlwy.net:15432
   Embedding model: text-embedding-3-small
   Ready for document ingestion: ✓
```

**If this fails:**
- Ensure Test 1 (Neo4j) passes first
- Verify `OPENAI_API_KEY` is valid
- Check dependencies: `pip install graphiti-core>=0.3.0`

---

### Test 3: PostgreSQL Schema

```bash
python scripts/verify_guidelines_db.py
```

**Expected output:**
```
================================================================================
Guidelines Database Schema Verification
================================================================================

Database: ep-restless-scene-aha4yrpo-pooler.c-3.us-east-1.aws.neon.tech/neondb

🔄 Connecting to database...
✅ Connection successful

📦 Checking extensions...
   ✓ uuid-ossp v1.1
   ✓ vector v0.6.0

📊 Checking tables...
   ✓ guideline_embeddings (0 rows, 8192 bytes)
   ✓ guidelines (0 rows, 8192 bytes)

🔍 Checking indexes...
   ✓ guideline_embeddings.idx_guideline_embeddings_vector
   ✓ guideline_embeddings.idx_guideline_embeddings_search
   ...

⚡ Checking triggers...
   ✓ guideline_embeddings.trigger_update_guideline_search_vector
   ✓ guidelines.trigger_guidelines_updated_at

📋 Schema verification:
   ✓ guidelines table schema correct
   ✓ guideline_embeddings table schema correct

✅ Database schema verification complete!
```

**If this fails:**
- Run migration script: `psql "$CLINICAL_GUIDELINES_DATABASE_URL" -f scripts/setup_guidelines_db.sql`
- Install dependencies: `pip install 'psycopg[binary]>=3.0.0' pgvector`
- Check database URL is correct

---

### Test 4: Complete Retrieval Pipeline

```bash
python scripts/test_guidelines_retrieval.py
```

**Expected output:**
```
================================================================================
Guidelines Retrieval Pipeline Test
================================================================================

✓ All required environment variables set

================================================================================
Test 1: Import Modules
================================================================================
🔄 Importing GuidelinesGraphitiClient...
✅ GuidelinesGraphitiClient imported
...

================================================================================
Test 3: Component Health Checks
================================================================================
🔄 Checking Graphiti health...
✅ Graphiti health check passed
...

================================================================================
✅ All Tests Passed!
================================================================================

📊 System Status:
   ✓ Graphiti client: Healthy
   ✓ Vector store: Healthy
   ✓ Retriever: Healthy
   ✓ Query execution: Working

🎯 Next Steps:
1. Upload clinical guidelines via the UI:
   - Use the Guidelines Upload dialog
   - Upload PDF/DOCX guideline documents

2. Test compliance analysis:
   - Generate a SOAP note
   - Run compliance check
   - Verify guideline citations
```

**If this fails:**
- Run Tests 1-3 individually first
- Check all environment variables
- Verify database migration completed

---

## Phase 5: Upload Your First Guideline

### Via UI (Recommended)

1. **Launch Application**
   ```bash
   python main.py
   ```

2. **Open Guidelines Upload Dialog**
   - Menu: Tools → Upload Clinical Guidelines
   - Or use keyboard shortcut (if configured)

3. **Upload a Guideline**
   - Select a PDF or DOCX guideline document
   - Fill in metadata:
     - Title: "ACC/AHA Hypertension Guideline 2017"
     - Specialty: "Cardiology"
     - Source: "ACC/AHA"
     - Version: "2017"
   - Click **Upload**

4. **Verify Upload**
   - Check for success message
   - View in guidelines list

### Via Script (Optional)

You can also upload programmatically:

```python
from src.rag.guidelines_vector_store import GuidelinesVectorStore
import asyncio

async def upload_guideline():
    store = GuidelinesVectorStore()

    guideline_id = await store.add_guideline(
        title="ACC/AHA Hypertension Guideline 2017",
        specialty="Cardiology",
        source="ACC/AHA",
        version="2017",
        document_type="Clinical Practice Guideline",
        file_path="/path/to/guideline.pdf"
    )

    # Extract and add chunks
    chunks = [
        "For adults with hypertension, the recommended BP target is <130/80 mm Hg.",
        "First-line medications include thiazide diuretics, ACE inhibitors, ARBs, and CCBs.",
        # ... more chunks
    ]

    await store.add_chunks(
        guideline_id=guideline_id,
        chunks=chunks,
        section_types=["recommendation"] * len(chunks)
    )

    await store.close()

asyncio.run(upload_guideline())
```

---

## Troubleshooting

### Connection Timeout

**Symptom:**
```
❌ Connection failed: ServiceUnavailable
   Error: Unable to retrieve routing information
```

**Solution:**
1. Verify TCP proxy is enabled in Railway dashboard
2. Check Neo4j service is running
3. Test TCP connectivity:
   ```bash
   nc -zv <proxy-domain> <proxy-port>
   ```
4. If `nc` shows connection refused, TCP proxy isn't enabled

---

### Authentication Failed

**Symptom:**
```
❌ Connection failed: AuthError
   Error: The client is unauthorized due to authentication failure
```

**Solution:**
1. Verify password in `.env` matches Railway environment variable
2. Check Railway dashboard → neo4j-guidelines → Variables
3. Reset password if needed:
   ```bash
   # In Railway dashboard
   NEO4J_AUTH=neo4j/your_new_password
   ```
4. Update `.env` with new password

---

### PostgreSQL Extension Error

**Symptom:**
```
ERROR: extension "vector" does not exist
```

**Solution:**
1. Verify Neon database supports pgvector
2. All Neon databases created after 2024 have pgvector enabled
3. Run migration script again:
   ```bash
   psql "$CLINICAL_GUIDELINES_DATABASE_URL" -f scripts/setup_guidelines_db.sql
   ```

---

### Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'graphiti'
```

**Solution:**
Install dependencies:
```bash
pip install graphiti-core>=0.3.0
pip install openai>=1.0.0
pip install neo4j>=5.0.0
pip install 'psycopg[binary]>=3.0.0'
pip install pgvector
```

---

## Alternative: Neo4j Aura (If TCP Proxy Doesn't Work)

If Railway TCP proxy isn't working, use Neo4j Aura instead:

### Step 1: Create Free Neo4j Aura Instance

1. Go to https://neo4j.com/cloud/aura/
2. Sign up for free tier
3. Create new instance:
   - Name: "clinical-guidelines"
   - Region: Choose closest to you
   - Memory: 1 GB (free tier)

### Step 2: Get Connection URI

After creation, you'll get:
```
URI: neo4j+s://xxxxx.databases.neo4j.io
Username: neo4j
Password: (generated password)
```

### Step 3: Update `.env`

```bash
CLINICAL_GUIDELINES_NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
CLINICAL_GUIDELINES_NEO4J_USER=neo4j
CLINICAL_GUIDELINES_NEO4J_PASSWORD=<aura_password>
```

### Step 4: Retest

```bash
python scripts/test_neo4j_connection.py
```

**Pros:**
- Guaranteed connectivity (no TCP proxy needed)
- Managed backups
- Better performance
- Free tier available

**Cons:**
- Requires credit card (even for free tier)
- Data stored outside Railway
- Free tier limits (1 GB memory, 200k nodes)

---

## Verification Checklist

### Pre-Deployment
- [ ] Railway TCP Proxy enabled for port 7687
- [ ] TCP proxy domain and port obtained
- [ ] `.env` updated with new Neo4j URI
- [ ] PostgreSQL migration script executed
- [ ] All test scripts pass

### Post-Deployment
- [ ] Test 1: Neo4j connection passes
- [ ] Test 2: Graphiti client health check passes
- [ ] Test 3: PostgreSQL schema verification passes
- [ ] Test 4: Retrieval pipeline test passes
- [ ] All environment variables correct

### End-to-End Validation
- [ ] Upload test guideline via UI
- [ ] Verify document in PostgreSQL
- [ ] Verify embeddings created
- [ ] Verify knowledge graph entities in Neo4j
- [ ] Test compliance analysis with SOAP note
- [ ] Verify hybrid search returns results
- [ ] Check guideline citations in compliance report

---

## Next Steps

Once setup is complete:

1. **Upload Guidelines**
   - Upload 5-10 key clinical guidelines
   - Cover major specialties (Cardiology, Endocrinology, etc.)

2. **Test Compliance Analysis**
   - Generate a SOAP note
   - Click "Check Compliance" button
   - Review guideline citations

3. **Monitor Performance**
   - Check query response times
   - Monitor Neo4j memory usage
   - Review PostgreSQL query performance

4. **Configure Additional Settings**
   - Adjust retrieval parameters (top_k, weights)
   - Customize compliance analysis prompts
   - Set specialty-specific filters

---

## Support

If you encounter issues not covered in this guide:

1. Check Railway service logs:
   ```bash
   railway logs -s neo4j-guidelines
   ```

2. Check Neo4j logs in Railway dashboard

3. Verify all environment variables:
   ```bash
   python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Neo4j URI:', os.getenv('CLINICAL_GUIDELINES_NEO4J_URI'))"
   ```

4. Review the plan transcript for additional context:
   ```
   /home/cortexuvula/.claude/projects/-home-cortexuvula-Development-Medical-Assistant/ed813844-f834-468e-ac72-277cd485c922.jsonl
   ```

---

## Summary

**Phase 1**: Enable Railway TCP Proxy for port 7687 ✅
**Phase 2**: Update `.env` with TCP proxy endpoint ✅
**Phase 3**: Run PostgreSQL migration ✅
**Phase 4**: Verify with test scripts ✅
**Phase 5**: Upload first guideline ✅

All infrastructure is now ready for clinical guidelines compliance analysis!
