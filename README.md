# Recall 🧠

Your personal knowledge system. Search meeting transcripts, notes, decisions, and PDFs with AI-powered retrieval.

> *"What did we decide about X?" — answered in seconds.*

## Features

- **Web UI** — Clean, Obsidian-inspired interface for search and browsing
- **Hybrid Search** — BM25 keyword + vector semantic search with RRF fusion
- **PDF Support** — Index PDFs with page-aware chunking and citations
- **RAG Answers** — Natural language questions answered with context
- **1:1 Prep** — Quick context for meetings with specific people
- **GPU Offload** — Wake remote GPU machine for fast indexing (~50 vectors/sec)
- **Query Expansion** — LLM generates alternative phrasings
- **LLM Reranking** — Position-aware reranking for quality

## Screenshots

The UI provides:
- **Search** — Hybrid search with AI-powered Q&A
- **Browse** — File tree navigation like Obsidian
- **Note Viewer** — Markdown rendering with syntax highlighting

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Recall UI                                │
│                   (React + Vite + Tailwind)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Recall API                                │
│                    (FastAPI + Python)                           │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   LanceDB     │    │ SQLite FTS5   │    │    Ollama     │
│   (vectors)   │    │   (BM25)      │    │  (embeddings) │
└───────────────┘    └───────────────┘    └───────────────┘
                                                 │
                              ┌──────────────────┘
                              ▼
                    ┌───────────────────┐
                    │   GPU Ollama      │
                    │   (optional)      │
                    └───────────────────┘
```

## Search Modes

| Mode | Speed | Quality | Description |
|------|-------|---------|-------------|
| `hybrid` | Fast | Better | BM25 + Vector + RRF fusion (recommended) |
| `query` | Slow | Best | Expansion + hybrid + reranking |
| `vector` | Fast | Good | Pure semantic search |
| `bm25` | Fast | Good | Pure keyword search |

## Quick Start

### Prerequisites

- Docker & Docker Compose (or Kubernetes)
- Ollama with embedding model (`nomic-embed-text`)
- Markdown files to index (Obsidian vault, Granola transcripts, etc.)

### Setup

1. Clone and configure:

```bash
git clone https://github.com/arniesaha/recall.git
cd recall/services
cp .env.example .env
# Edit .env with your settings
```

2. Start services:

```bash
docker compose up -d
```

3. Pull embedding model:

```bash
docker exec -it recall-ollama ollama pull nomic-embed-text
docker exec -it recall-ollama ollama pull qwen2.5:0.5b  # For reranking
```

4. Index your documents:

```bash
curl -X POST http://localhost:8080/index/start \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{"vault": "all", "full": true}'
```

5. Start the UI:

```bash
cd ui
npm install
npm run dev
```

## Web UI

The React-based UI runs separately and connects to the API.

```bash
cd ui
npm install
npm run dev         # Development
npm run build       # Production build
```

**Features:**
- Dark mode by default (Obsidian-inspired)
- Mobile-friendly responsive design
- Keyboard shortcuts (/, Escape)
- Vault selector (work/personal)
- Real-time search

## API Endpoints

### Search

```bash
curl -X POST http://localhost:8080/search \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{"query": "project timeline", "mode": "hybrid", "limit": 10}'
```

### RAG Query

```bash
curl -X POST http://localhost:8080/query \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{"question": "What did we decide about the API redesign?"}'
```

### 1:1 Prep

```bash
curl http://localhost:8080/prep/PersonName \
  -H "Authorization: Bearer your-api-token"
```

### Indexing with GPU

```bash
curl -X POST http://localhost:8080/index/start \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{"rebuild": true, "use_gpu": true}'
```

### Index Progress

```bash
curl http://localhost:8080/index/progress \
  -H "Authorization: Bearer your-api-token"
```

### Health Check

```bash
curl http://localhost:8080/health
```

## GPU Offload

For large indexes, Recall can offload embedding generation to a remote GPU machine:

1. **Auto Wake-on-LAN** — Automatically wakes GPU PC when indexing starts
2. **Health Check** — Waits for Ollama to be ready
3. **Fast Indexing** — ~50 vectors/sec on GPU vs ~2/sec on CPU
4. **Auto Shutdown** — Powers off GPU PC when done (optional)

See [docs/GPU-OFFLOAD.md](docs/GPU-OFFLOAD.md) for setup instructions.

## Key Algorithms

### Reciprocal Rank Fusion (RRF)

Combines multiple ranked lists:

```
score = Σ 1/(k + rank + 1)  where k=60
```

Plus top-rank bonus: +0.05 for #1, +0.02 for #2-3.

### Position-Aware Reranking

Blends retrieval scores with LLM reranker:

- Top 1-3: 75% retrieval, 25% reranker (preserve exact matches)
- Top 4-10: 60% retrieval, 40% reranker
- Top 11+: 40% retrieval, 60% reranker (trust reranker more)

### Person-Aware Search

When queries mention person names (detected via NLP), the search adjusts:

- BM25 weight increases to 3:1 ratio (vs default 1:1)
- Filename matches boosted (person names often in meeting titles)
- FTS5 uses OR search with wildcards: `"John" OR John*`

## Project Structure

```
recall/
├── services/
│   └── api/
│       ├── main.py          # FastAPI application
│       ├── searcher.py      # Search logic (hybrid, RRF)
│       ├── indexer.py       # Document indexing
│       ├── gpu_offload.py   # GPU PC wake/shutdown
│       ├── fts_index.py     # SQLite FTS5 wrapper
│       ├── fusion.py        # RRF implementation
│       ├── reranker.py      # LLM reranking
│       ├── config.py        # Settings
│       └── Dockerfile
├── ui/                       # React frontend
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Route pages
│   │   ├── api/             # API client
│   │   └── hooks/           # Custom hooks
│   ├── package.json
│   └── Dockerfile
├── helm/                     # Kubernetes deployment
│   ├── templates/
│   └── values.yaml
├── grafana/                  # Monitoring dashboards
│   └── recall-dashboard.json
├── scripts/                  # Utility scripts
│   ├── wol-server.py        # Wake-on-LAN HTTP server
│   ├── gpu-shutdown-server.py
│   ├── daily_vault_sync.py  # Daily sync orchestrator
│   ├── reorganize_v2.py     # Vault reorganization (optional)
│   └── GPU-SETUP.md
└── docs/
    ├── GPU-OFFLOAD.md       # GPU setup guide
    └── UI-DESIGN-PLAN.md    # UI design docs
```

## Vault Structure

Recall indexes Markdown files from configured vaults. The recommended structure is **flat date-based naming**:

```
obsidian/
├── work/
│   ├── daily-notes/           # Meeting summaries (synced from Granola)
│   │   ├── 2025-04-07-Team Standup.md
│   │   ├── 2025-04-07-PM __ Arnab.md
│   │   └── ...
│   └── Granola/
│       └── Transcripts/       # Raw meeting transcripts
│           ├── 2025-04-07-Team Standup-transcript.md
│           └── ...
└── personal/
    └── notes/                 # Personal notes
```

### Why Flat Structure?

1. **Search works well** — BM25 finds person names in filenames, vector search finds semantic content
2. **Simple sync** — Granola exports directly to flat folders
3. **Date-based navigation** — Easy chronological browsing in the UI
4. **No maintenance** — No need to reorganize files into person/project folders

### Reorganization (Optional)

The `scripts/reorganize_v2.py` script can analyze your vault and optionally create derived folders by person/project:

```bash
# Preview what would change (dry run)
python3 scripts/reorganize_v2.py

# Apply changes
python3 scripts/reorganize_v2.py --apply
```

### Daily Sync

The `scripts/daily_vault_sync.py` orchestrates a full reindex cycle:

1. Run reorganization (if enabled)
2. Wake GPU PC via Wake-on-LAN
3. Trigger full reindex with GPU
4. Shutdown GPU PC when done

Configure as a cron job for automated daily syncs.

## Kubernetes Deployment

Deploy with Helm:

```bash
helm upgrade --install recall ./helm -n apps
```

The chart includes:
- API deployment with Ollama sidecar
- UI deployment with nginx
- Services and ingress
- ConfigMaps for settings

## Monitoring

Prometheus metrics available at `/metrics`:

- `recall_search_latency_seconds` — Search latency by mode
- `recall_index_progress_percent` — Indexing progress
- `recall_index_job_running` — Active indexing job indicator
- `recall_ollama_latency_seconds` — Ollama API latency

Grafana dashboard: `grafana/recall-dashboard.json`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_TOKEN` | Authentication token | (required) |
| `OLLAMA_URL` | Ollama API endpoint | `http://ollama:11434` |
| `GPU_OLLAMA_URL` | Remote GPU Ollama | `http://10.10.10.2:11434` |
| `GPU_OLLAMA_ENABLED` | Enable GPU offload | `false` |
| `LANCEDB_PATH` | Vector DB storage path | `/data/lancedb` |
| `VAULT_WORK_PATH` | Work vault path | `/data/obsidian/work` |
| `VAULT_PERSONAL_PATH` | Personal vault path | `/data/obsidian/personal` |
| `PDF_WORK_PATH` | Work PDFs path | `/data/pdfs/work` |
| `EXCLUDED_FOLDERS` | Folders to skip | `personal/finance` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Models Used

| Model | Purpose | Size |
|-------|---------|------|
| `nomic-embed-text` | Embeddings | ~275MB |
| `qwen2.5:0.5b` | Reranking + query expansion | ~400MB |

## Development

### API

```bash
cd services/api
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### UI

```bash
cd ui
npm install
npm run dev
```

## Credits

- Search pipeline inspired by [QMD](https://github.com/tobi/qmd) by Tobi Lütke
- Vector search: [LanceDB](https://lancedb.com/)
- Embeddings: [Ollama](https://ollama.ai/) + nomic-embed-text
- UI: React + Vite + Tailwind CSS

## License

MIT
