# Recall 🧠

Your personal knowledge system. Search meeting transcripts, notes, decisions, and PDFs with AI-powered retrieval.

> *"What did we decide about X?" — answered in seconds.*

## Features

- **Hybrid Search** — BM25 keyword + vector semantic search with RRF fusion
- **PDF Support** — Index PDFs with page-aware chunking
- **RAG Answers** — Natural language questions answered with context
- **1:1 Prep** — Quick context for meetings with specific people
- **Query Expansion** — LLM generates alternative phrasings
- **LLM Reranking** — Position-aware reranking for quality

## Architecture

```
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

- Docker & Docker Compose
- Ollama with embedding model (`nomic-embed-text`)
- Markdown files to index (Obsidian vault, Granola transcripts, etc.)

### Setup

1. Clone and configure:

```bash
git clone https://github.com/arniesaha/note-rag.git
cd note-rag/services
cp .env.example .env
# Edit .env with your settings
```

2. Start services:

```bash
docker compose up -d
```

3. Pull embedding model:

```bash
docker exec -it kg-ollama ollama pull nomic-embed-text
docker exec -it kg-ollama ollama pull qwen2.5:0.5b  # For reranking
```

4. Index your documents:

```bash
curl -X POST http://localhost:8080/index/start \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{"vault": "all", "full": true}'
```

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

### Health Check

```bash
curl http://localhost:8080/health
```

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

## Project Structure

```
note-rag/
├── services/
│   ├── api/
│   │   ├── main.py          # FastAPI application
│   │   ├── searcher.py      # Search logic (hybrid, RRF)
│   │   ├── indexer.py       # Document indexing
│   │   ├── fts_index.py     # SQLite FTS5 wrapper
│   │   ├── fusion.py        # RRF implementation
│   │   ├── reranker.py      # LLM reranking
│   │   ├── config.py        # Settings
│   │   └── Dockerfile
│   ├── docker-compose.yml
│   └── .env.example
├── scripts/                   # Utility scripts
│   ├── daily_sync.py         # Sync from sources
│   └── cleanup_sources.py
├── docs/                      # Documentation
│   └── QMD-PORT-ROADMAP.md
└── n8n/                       # n8n workflow configs
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_TOKEN` | Authentication token | (required) |
| `OLLAMA_URL` | Ollama API endpoint | `http://ollama:11434` |
| `LANCEDB_PATH` | Vector DB storage path | `/data/lancedb` |
| `VAULT_WORK_PATH` | Work vault path | `/data/obsidian/work` |
| `VAULT_PERSONAL_PATH` | Personal vault path | `/data/obsidian/personal` |
| `EXCLUDED_FOLDERS` | Folders to skip | `personal/finance` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Models Used

| Model | Purpose | Size |
|-------|---------|------|
| `nomic-embed-text` | Embeddings | ~275MB |
| `qwen2.5:0.5b` | Reranking + query expansion | ~400MB |

## Development

```bash
# Install dependencies
cd services/api
pip install -r requirements.txt

# Run locally
uvicorn main:app --reload --port 8080
```

## Credits

- Search pipeline inspired by [QMD](https://github.com/tobi/qmd) by Tobi Lütke
- Vector search: [LanceDB](https://lancedb.com/)
- Embeddings: [Ollama](https://ollama.ai/) + nomic-embed-text

## License

MIT
