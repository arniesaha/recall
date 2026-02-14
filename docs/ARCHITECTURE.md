# Recall — Architecture Document

**Version:** 1.1
**Date:** 2026-02-14
**Status:** Active

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   NAS                                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Kubernetes (k3s)                            │   │
│  │                                                                      │   │
│  │   ┌─────────────┐                       ┌─────────────────────┐    │   │
│  │   │   Ollama    │                       │    Recall API       │    │   │
│  │   │   (CPU)     │                       │     (FastAPI)       │    │   │
│  │   │             │                       │                     │    │   │
│  │   │ nomic-embed │◄─────────────────────►│  /search           │    │   │
│  │   │             │                       │  /query            │    │   │
│  │   │             │                       │  /prep/{person}    │    │   │
│  │   └─────────────┘                       │  /index            │    │   │
│  │                                         │  /health           │    │   │
│  │   ┌─────────────┐                       │                     │    │   │
│  │   │ Recall UI   │◄─────────────────────►│    :8080           │    │   │
│  │   │  (React)    │                       └──────────┬──────────┘    │   │
│  │   │    :80      │                                  │               │   │
│  │   └─────────────┘                                  │               │   │
│  └────────────────────────────────────────────────────┼───────────────┘   │
│                                                       │                    │
│  ┌────────────────────────────────────────────────────┼───────────────┐   │
│  │                        File System                 │               │   │
│  │                                                    │               │   │
│  │   /data/                                           │               │   │
│  │   ├── obsidian/                                    │               │   │
│  │   │   ├── work/        (meeting notes, 1:1s)      │ File Watcher  │   │
│  │   │   │   ├── daily-notes/                        │ (incremental) │   │
│  │   │   │   └── Granola/Transcripts/                │               │   │
│  │   │   └── personal/    (personal notes)           │               │   │
│  │   │                                               │               │   │
│  │   ├── pdfs/            (PDF documents)            │               │   │
│  │   │   ├── work/                                   │               │   │
│  │   │   └── personal/                               │               │   │
│  │   │                                               │               │   │
│  │   └── lancedb/         (vector database)     ◄────┘               │   │
│  │       ├── work/        (~20k vectors)                             │   │
│  │       └── personal/    (~100 vectors)                             │   │
│  │                                                                    │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTPS (Cloudflare Tunnel)
                                      ▼
                          ┌─────────────────────┐
                          │   External Access   │
                          │   recall.domain.com │
                          └─────────────────────┘
```

---

## 2. Components

### 2.1 Ollama (Embedding Service)

**Purpose:** Generate vector embeddings for documents and queries

**Model:** `nomic-embed-text`
- 137M parameters
- 768-dimension vectors
- 8192 token context window
- Optimized for CPU inference

**API:**
```bash
POST http://ollama:11434/api/embed
{
  "model": "nomic-embed-text",
  "input": "text to embed"
}
```

---

### 2.2 LanceDB (Embedded Vector Database)

**Purpose:** Store and search document embeddings

**Why LanceDB:**
- Embedded library (no separate server process)
- Data stored as files (easy backup: just copy the folder)
- Fast vector search with filtering
- Simple Python API

**Tables:**

| Table | Content | Est. Vectors |
|-------|---------|--------------|
| `work` | Work vault chunks | ~20,000 |
| `personal` | Personal vault chunks | ~100 |

**Schema:**
```python
class DocumentChunk(LanceModel):
    id: str                    # Unique chunk ID
    vector: Vector(768)        # nomic-embed-text dimension
    file_path: str
    file_hash: str             # MD5 for change detection
    mtime: float               # Modification timestamp
    title: str
    category: str              # daily-notes, Granola, etc.
    people: list[str]          # Mentioned people
    projects: list[str]        # Mentioned projects
    date: str                  # YYYY-MM-DD format
    vault: str                 # "work" or "personal"
    chunk_index: int
    content: str               # Actual text content
    source_type: str           # "markdown" or "pdf"
    page_number: int | None    # PDF page (1-indexed)
```

---

### 2.3 Recall API (FastAPI)

**Purpose:** Main application service

**Key Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/search` | POST | Hybrid search (BM25 + Vector) |
| `/query` | POST | RAG query with LLM answer |
| `/prep/{person}` | GET | 1:1 preparation context |
| `/index/start` | POST | Trigger indexing job |
| `/index/progress` | GET | Real-time indexing progress |

**Features:**
- Temporal expression parsing ("this week", "last month")
- Person-aware search with BM25 boost
- PDF support with page-aware chunking
- Prometheus metrics

---

### 2.4 Recall UI (React)

**Purpose:** Web interface for search and browsing

**Features:**
- Natural language search
- AI-generated answers with sources
- Note viewer with markdown rendering
- Folder browsing
- Mobile responsive

**Tech Stack:**
- React 18 + Vite
- TailwindCSS
- React Query

---

### 2.5 FTS Index (SQLite FTS5)

**Purpose:** Keyword search for hybrid retrieval

**Why FTS5:**
- Fast BM25 ranking
- Handles names better than embeddings
- Complements semantic search

**Integration:**
- Maintained alongside LanceDB
- Updated incrementally with new documents
- Used in hybrid search with 3:1 BM25 boost for person queries

---

## 3. Data Flow

### 3.1 Ingestion Flow

```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│  Granola   │────▶│  Obsidian  │────▶│    NAS     │────▶│   File     │
│  Meeting   │     │   Sync     │     │   Vault    │     │  Watcher   │
└────────────┘     └────────────┘     └────────────┘     └─────┬──────┘
                                                               │
     ┌─────────────────────────────────────────────────────────┘
     │
     ▼
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│  Extract   │────▶│   Chunk    │────▶│   Embed    │────▶│   Store    │
│  Metadata  │     │  Content   │     │  (Ollama)  │     │  (Lance)   │
└────────────┘     └────────────┘     └────────────┘     └────────────┘
```

### 3.2 Query Flow

```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│   User     │────▶│  Parse     │────▶│  Hybrid    │────▶│  Retrieve  │
│   Query    │     │  Temporal  │     │  Search    │     │  Top-K     │
└────────────┘     └────────────┘     └────────────┘     └─────┬──────┘
                                                               │
     ┌─────────────────────────────────────────────────────────┘
     │
     ▼
┌────────────┐     ┌────────────┐     ┌────────────┐
│  Build     │────▶│    LLM     │────▶│  Return    │
│  Context   │     │  Generate  │     │  Answer    │
└────────────┘     └────────────┘     └────────────┘
```

### 3.3 Search Algorithm

**Hybrid Search with RRF Fusion:**
1. Parse temporal expressions from query
2. Run BM25 search (keyword matching)
3. Run Vector search (semantic matching)
4. Fuse results using Reciprocal Rank Fusion
5. Optional: Rerank with small LLM

**Person Query Boost:**
When names detected in query:
- BM25 weighted 3:1 vs Vector
- Name-only search for BM25 (avoids phrase matching issues)

---

## 4. Directory Structure

```
recall/
├── docs/                        # Project documentation
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── UI-DESIGN-PLAN.md
├── data/                        # Data volumes (mounted)
│   ├── obsidian/
│   │   ├── work/
│   │   └── personal/
│   ├── pdfs/
│   │   ├── work/
│   │   └── personal/
│   └── lancedb/
├── services/
│   ├── api/                     # FastAPI backend
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   ├── indexer.py
│   │   ├── searcher.py
│   │   ├── temporal.py          # Temporal expression parsing
│   │   ├── fts_index.py         # BM25 search
│   │   ├── fusion.py            # RRF fusion
│   │   └── config.py
│   └── ui/                      # React frontend
│       ├── Dockerfile
│       ├── package.json
│       └── src/
├── helm/                        # Kubernetes deployment
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
├── scripts/                     # Utility scripts
│   ├── daily_vault_sync.py
│   └── gpu_offload.py
└── README.md
```

---

## 5. Deployment

### 5.1 Kubernetes (k3s)

**Services:**
- `recall` - API deployment (NodePort 30889)
- `recall-ui` - UI deployment (NodePort 30890)
- `recall-ollama` - Ollama sidecar (optional, can use external)

**Helm Chart:**
```bash
helm upgrade --install recall ./helm -n apps
```

### 5.2 External Access

Via Cloudflare Tunnel:
- `recall.domain.com` → UI
- `recallapi.domain.com` → API (protected)

---

## 6. Monitoring

### 6.1 Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `recall_search_latency_seconds` | Histogram | Search latency by mode |
| `recall_search_results_count` | Histogram | Results per search |
| `recall_rag_query_latency_seconds` | Histogram | RAG latency |
| `recall_index_progress_percent` | Gauge | Indexing progress |

### 6.2 Grafana Dashboard

Pre-built dashboard with:
- Search latency percentiles
- Query throughput
- Indexing progress
- Error rates

---

## 7. GPU Offload

For faster indexing, supports GPU offload:

1. Wake GPU machine via Wake-on-LAN
2. API calls GPU machine's Ollama for embeddings
3. Shutdown GPU machine when done

**Performance:**
- CPU: ~20 hours for full reindex
- GPU: ~5 minutes for full reindex

---

## 8. Backup

### 8.1 Data to Backup
- `/data/lancedb/` - Vector database
- `/data/obsidian/` - Source documents
- FTS database (if persistent)

### 8.2 Strategy
- Daily incremental backup of lancedb
- Weekly full backup
- Source documents synced from primary (Mac/Granola)

---

*Last updated: 2026-02-14*
