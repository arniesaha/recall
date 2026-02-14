# Recall API Reference

Base URL: `https://<your-domain>/api` or k8s internal ClusterIP

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
Hybrid search (BM25 + Vector) across indexed documents with automatic temporal parsing.

**Request Body:**
```json
{
  "query": "string",           // Required: search query
  "vault": "work|personal|all", // Optional, default: "all"
  "limit": 10,                 // Optional, default: 10
  "mode": "vector|bm25|hybrid|query", // Optional, default: "hybrid"
  "date_from": "YYYY-MM-DD",   // Optional: explicit date filter
  "date_to": "YYYY-MM-DD",     // Optional: explicit date filter
  "person": "string",          // Optional: filter by person
  "category": "string"         // Optional: filter by category
}
```

**Temporal Parsing:**
If `date_from`/`date_to` not provided, temporal expressions are auto-parsed:
- "this week" → current week (Mon-today)
- "last month" → previous month
- "yesterday" → yesterday's date
- "past 7 days" → last 7 days
- "in January" → January of current/recent year

**Response:**
```json
{
  "results": [
    {
      "file_path": "/data/obsidian/work/meetings/...",
      "title": "Document Title",
      "excerpt": "Matching snippet with <mark>highlights</mark>...",
      "score": 0.85,
      "vault": "work",
      "category": "meetings",
      "date": "2026-02-10",
      "people": ["Alex", "Jordan"],
      "source_type": "markdown",
      "page_number": null
    }
  ],
  "total": 5,
  "query_time_ms": 234
}
```

### POST /query
RAG-powered query with LLM-generated answer.

**Request Body:**
```json
{
  "question": "string",        // Required: question to answer
  "vault": "work|personal|all" // Optional, default: "all"
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
  ],
  "query_time_ms": 3456
}
```

---

## 1:1 Prep Endpoint

### GET /prep/{person}
Get context for 1:1 meeting preparation.

**Path Parameters:**
- `person`: Name of the person (e.g., "Alex")

**Query Parameters:**
- `limit`: Max documents (default: 10)

**Response:**
```json
{
  "person": "Alex",
  "meeting_count": 12,
  "last_meeting": "2026-02-08",
  "recent_topics": ["roadmap", "performance"],
  "open_actions": ["Review PR by Friday"],
  "recent_meetings": [
    {
      "title": "Weekly 1:1",
      "date": "2026-02-08",
      "file_path": "..."
    }
  ]
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
      "status": "running|completed|failed",
      "vault": "work",
      "full": true,
      "started_at": "2026-02-13T10:20:11.532947",
      "indexed": 245
    }
  ]
}
```

### GET /index/progress
Get real-time indexing progress.

**Response:**
```json
{
  "running": true,
  "processed": 150,
  "total": 500,
  "percent": 30.0,
  "eta_human": "3m 20s",
  "current_file": "meetings/2026-02-10.md",
  "elapsed_seconds": 120
}
```

### POST /index/cancel/{job_id}
Cancel a running indexing job.

**Response:**
```json
{"status": "cancelled"}
```

---

## GPU Offload Endpoints

### POST /index/gpu
Trigger GPU-accelerated indexing (wakes GPU machine if needed).

**Request Body:**
```json
{
  "vault": "work|personal|all",
  "full": false
}
```

**Response:**
```json
{
  "status": "started",
  "gpu_status": "waking|ready",
  "estimated_time": "5 minutes"
}
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
| `API_TOKEN` | (required) | Authentication token |
| `OLLAMA_URL` | http://ollama:11434 | Ollama endpoint |
| `LANCEDB_PATH` | /data/lancedb | Vector DB storage |
| `VAULT_WORK_PATH` | /data/obsidian/work | Work vault path |
| `VAULT_PERSONAL_PATH` | /data/obsidian/personal | Personal vault path |
| `PDF_WORK_PATH` | /data/pdfs/work | Work PDFs path |
| `PDF_PERSONAL_PATH` | /data/pdfs/personal | Personal PDFs path |
| `PDF_ENABLED` | true | Enable PDF indexing |
| `CHUNK_SIZE` | 500 | Target tokens per chunk |
| `CHUNK_OVERLAP` | 50 | Overlap between chunks |
| `LOG_LEVEL` | INFO | Logging level |

---

## OpenAPI Spec

FastAPI auto-generates OpenAPI spec at:
- `/docs` - Swagger UI
- `/redoc` - ReDoc UI  
- `/openapi.json` - Raw OpenAPI JSON

---

## Examples

### Search for meeting notes with temporal filter
```bash
curl -X POST "http://localhost:8080/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What did we discuss this week?", "vault": "work"}'
```

### Get 1:1 prep context
```bash
curl "http://localhost:8080/prep/Alex?limit=5" \
  -H "Authorization: Bearer $TOKEN"
```

### Full reindex with PDFs
```bash
curl -X POST "http://localhost:8080/index/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full": true, "vault": "work"}'
```

### Ask a question (RAG)
```bash
curl -X POST "http://localhost:8080/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key decisions from last week?"}'
```

---

## Metrics

Prometheus metrics available at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `recall_search_latency_seconds` | Histogram | Search latency by mode |
| `recall_search_results_count` | Histogram | Result count per search |
| `recall_rag_query_latency_seconds` | Histogram | RAG query latency |
| `recall_index_total_files` | Gauge | Total files to index |
| `recall_index_processed_files` | Gauge | Files indexed so far |
| `recall_index_progress_percent` | Gauge | Indexing progress % |

---

*Last updated: 2026-02-14*
