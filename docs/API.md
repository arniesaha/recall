# Recall API Reference

Base URL: `https://recall.arnabsaha.com` (external) or k8s internal ClusterIP

## Authentication

All endpoints require Bearer token authentication:
```
Authorization: Bearer <API_TOKEN>
```

---

## Health & Status

### GET /ping
Quick health check.

**Response:** `200 OK`
```json
{"status": "ok"}
```

### GET /health
Detailed health status including Ollama connectivity and index stats.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "ollama": "connected",
  "lancedb": "connected",
  "index": {
    "work": {"count": 245},
    "personal": {"count": 18}
  }
}
```

---

## Search Endpoints

### POST /search
Semantic vector search across indexed documents.

**Request Body:**
```json
{
  "query": "string",           // Required: search query
  "vault": "work|personal|all", // Optional, default: "all"
  "limit": 10,                 // Optional, default: 10
  "mode": "vector|bm25|hybrid", // Optional, default: "vector"
  "filters": {                 // Optional
    "person": "string",        // Filter by person mentioned
    "category": "string",      // Filter by category
    "date_from": "YYYY-MM-DD", // Filter by date range
    "date_to": "YYYY-MM-DD"
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "file_path": "/data/obsidian/work/meetings/...",
      "title": "Document Title",
      "content": "Matching chunk content...",
      "score": 0.85,
      "vault": "work",
      "category": "meetings",
      "date": "2026-02-10",
      "people": ["John", "Jane"],
      "source_type": "markdown",   // or "pdf"
      "page_number": null          // For PDFs: page number
    }
  ],
  "total": 5,
  "query": "original query"
}
```

### POST /query
RAG-powered query with LLM-generated answer.

**Request Body:**
```json
{
  "query": "string",           // Required: question to answer
  "vault": "work|personal|all", // Optional, default: "all"
  "max_context": 5             // Optional: max chunks for context
}
```

**Response:**
```json
{
  "answer": "LLM-generated answer based on context...",
  "sources": [
    {
      "file_path": "...",
      "title": "...",
      "relevance": 0.92
    }
  ]
}
```

---

## 1:1 Prep Endpoint

### GET /prep/{person}
Get context for 1:1 meeting preparation.

**Path Parameters:**
- `person`: Name of the person (e.g., "John")

**Query Parameters:**
- `limit`: Max documents (default: 10)

**Response:**
```json
{
  "person": "John",
  "recent_meetings": [
    {
      "title": "John _ Arnab",
      "date": "2026-02-08",
      "summary": "..."
    }
  ],
  "action_items": ["..."],
  "topics_discussed": ["..."]
}
```

---

## Indexing Endpoints

### POST /index/start
Start an indexing job.

**Request Body:**
```json
{
  "vault": "work|personal|all", // Optional, default: "all"
  "full": false                 // Optional: full reindex (clears table)
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "started"
}
```

### GET /index/jobs
List indexing jobs.

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "uuid",
      "status": "running|completed|error",
      "vault": "work",
      "full": true,
      "started_at": "2026-02-13T10:20:11.532947",
      "indexed": 245
    }
  ]
}
```

### POST /index/cancel/{job_id}
Cancel a running indexing job.

**Response:**
```json
{"status": "cancelled"}
```

---

## Document Schema

Each indexed document chunk contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique chunk ID |
| `file_path` | string | Full file path |
| `file_hash` | string | MD5 hash for change detection |
| `mtime` | float | File modification timestamp |
| `title` | string | Document title |
| `category` | string | Category from folder path |
| `people` | string[] | People mentioned |
| `projects` | string[] | Projects mentioned |
| `date` | string | Date (YYYY-MM-DD) |
| `vault` | string | "work" or "personal" |
| `chunk_index` | int | Chunk number in document |
| `content` | string | Chunk text content |
| `source_type` | string | "markdown" or "pdf" |
| `page_number` | int? | PDF page number (1-indexed) |

---

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_TOKEN` | changeme | Authentication token |
| `OLLAMA_URL` | http://ollama:11434 | Ollama endpoint |
| `LANCEDB_PATH` | /data/lancedb | Vector DB storage |
| `VAULT_WORK_PATH` | /data/obsidian/work | Work vault path |
| `VAULT_PERSONAL_PATH` | /data/obsidian/personal | Personal vault path |
| `PDF_WORK_PATH` | /data/pdfs/work | Work PDFs path |
| `PDF_PERSONAL_PATH` | /data/pdfs/personal | Personal PDFs path |
| `PDF_ENABLED` | true | Enable PDF indexing |
| `CHUNK_SIZE` | 500 | Target tokens per chunk |
| `CHUNK_OVERLAP` | 50 | Overlap between chunks |

---

## OpenAPI Spec

FastAPI auto-generates OpenAPI spec at:
- `/docs` - Swagger UI
- `/redoc` - ReDoc UI  
- `/openapi.json` - Raw OpenAPI JSON

---

## Examples

### Search for meeting notes about a person
```bash
curl -X POST "http://kg.arnabsaha.com/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What did we discuss with John?", "filters": {"person": "John"}}'
```

### Get 1:1 prep context
```bash
curl "http://kg.arnabsaha.com/prep/John?limit=5" \
  -H "Authorization: Bearer $TOKEN"
```

### Full reindex with PDFs
```bash
curl -X POST "http://kg.arnabsaha.com/index/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full": true, "vault": "work"}'
```

### Ask a question (RAG)
```bash
curl -X POST "http://kg.arnabsaha.com/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the key decisions from last week?"}'
```
