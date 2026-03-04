# Recall API Reference

Base URL: `https://<your-domain>/api` or k8s NodePort

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
Detailed health status and index stats.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "components": {
    "fts": "ok"
  },
  "stats": {
    "work_fts": 2025,
    "personal_fts": 0,
    "active_jobs": 0
  }
}
```

### GET /stats
Index statistics.

**Response:** `200 OK`
```json
{
  "work_fts": 2025,
  "personal_fts": 0
}
```

---

## Search Endpoints

### POST /search
BM25 search across indexed documents with automatic temporal parsing.

**Request Body:**
```json
{
  "query": "string",            // Required: search query
  "vault": "work|personal|all", // Optional, default: "all"
  "limit": 10,                  // Optional, default: 10
  "mode": "vectorless",         // Optional, default: "vectorless"
  "date_from": "YYYY-MM-DD",    // Optional: explicit date filter
  "date_to": "YYYY-MM-DD",      // Optional: explicit date filter
  "person": "string"            // Optional: filter by person
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
      "file_path": "/data/obsidian/work/daily-notes/...",
      "title": "Document Title",
      "excerpt": "Matching snippet with <mark>highlights</mark>...",
      "score": 0.85,
      "vault": "work",
      "category": "daily-notes",
      "date": "2026-02-10"
    }
  ],
  "total": 5,
  "query_time_ms": 234
}
```

### POST /search/vectorless
Explicit vectorless search endpoint (same behavior as `/search`).

### POST /query
RAG-powered query — retrieves relevant context and generates an answer via Gemini.

**Request Body:**
```json
{
  "question": "string",         // Required: question to answer
  "vault": "work|personal|all", // Optional, default: "all"
  "mode": "vectorless|fullcontext" // Optional, default: "vectorless"
}
```

**Modes:**
| Mode | Context Size | Description |
|------|-------------|-------------|
| `vectorless` | ~7K tokens | BM25 top-50 chunks sent to Gemini |
| `fullcontext` | ~100K tokens | Full source files sent to Gemini (best quality) |

**Response:**
```json
{
  "answer": "LLM-generated answer with inline source citations...",
  "sources": [
    {
      "file": "/data/obsidian/work/daily-notes/2026-03-02-Meeting.md",
      "title": "Meeting Title",
      "date": "2026-03-02",
      "vault": "work",
      "score": 45.2,
      "excerpt": "Relevant snippet..."
    }
  ],
  "query_time_ms": 21000
}
```

### POST /query/vectorless
Explicit vectorless RAG endpoint (same behavior as `/query`).

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
Start an FTS indexing job.

**Request Body:**
```json
{
  "vault": "work|personal|all", // Optional, default: "all"
  "full": false                 // Optional: full reindex (clears index)
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "started"
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
  "current_file": "daily-notes/2026-02-10.md",
  "elapsed_seconds": 120
}
```

### POST /index/cancel/{job_id}
Cancel a running indexing job.

---

## Browse & Notes

### GET /browse
Browse vault file tree.

**Query Parameters:**
- `vault`: "work" | "personal" (default: "work")

### GET /note
Get full note content.

**Query Parameters:**
- `path`: Relative path to the note (e.g., `work/daily-notes/2026-03-02-Meeting.md`)

---

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_TOKEN` | (required) | Authentication token |
| `GEMINI_API_KEY` | (required) | Google Gemini API key |
| `VECTORLESS_GEMINI_MODEL` | gemini-2.5-flash | Gemini model for RAG |
| `VECTORLESS_LLM_BACKEND` | gemini | LLM backend (`gemini` or `openclaw`) |
| `VAULT_WORK_PATH` | /data/obsidian/work | Work vault path |
| `VAULT_PERSONAL_PATH` | /data/obsidian/personal | Personal vault path |
| `VECTORLESS_MAX_CONTEXT_CHARS` | 400000 | Max chars for fullcontext mode |
| `VECTORLESS_BM25_TOP_K` | 50 | BM25 results for vectorless mode |
| `PDF_ENABLED` | true | Enable PDF indexing |
| `CHUNK_SIZE` | 500 | Target words per chunk |
| `CHUNK_OVERLAP` | 50 | Overlap between chunks |
| `LOG_LEVEL` | INFO | Logging level |

---

## Metrics

Prometheus metrics available at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `recall_search_latency_seconds` | Histogram | Search latency |
| `recall_search_results_count` | Histogram | Result count per search |
| `recall_rag_query_latency_seconds` | Histogram | RAG query latency |
| `recall_index_total_files` | Gauge | Total files to index |
| `recall_index_processed_files` | Gauge | Files indexed so far |
| `recall_index_progress_percent` | Gauge | Indexing progress % |

---

## OpenAPI Spec

FastAPI auto-generates OpenAPI docs at:
- `/docs` — Swagger UI
- `/redoc` — ReDoc UI
- `/openapi.json` — Raw OpenAPI JSON

---

*Last updated: 2026-03-03*
