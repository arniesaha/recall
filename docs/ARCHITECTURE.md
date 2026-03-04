# Recall Architecture — v3 (Vectorless)

## Overview

Recall is a personal knowledge base search engine that reads directly from an Obsidian vault.
It uses **BM25 keyword search** (SQLite FTS5) for retrieval and **Gemini Flash** for answer generation.

**No vector embeddings. No GPU. No Ollama.**

## Architecture

```
Query → BM25 (SQLite FTS5) → Top-K chunks → Gemini 2.5 Flash → Answer
                                    ↓
                           Full files from disk (fullcontext mode)
```

## Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API | FastAPI (Python) | REST endpoints |
| Search | SQLite FTS5 | BM25 keyword search |
| LLM | Gemini 2.5 Flash (1M context) | Answer generation |
| Data | Obsidian vault (Markdown) | Source of truth |
| Hosting | Kubernetes (k3s) | NodePort 30889 |
| UI | Vite + React | recall.arnabsaha.com |

## Search Modes

### vectorless (default)
- BM25 retrieves top-50 relevant chunks
- Name-aware boosting: detects person names, boosts 1:1 notes
- Source ranking: daily-notes boosted, raw transcripts penalized
- Temporal parsing: understands "last week", "this month"
- ~7K tokens context → Gemini Flash → answer

### fullcontext
- BM25 finds relevant files
- Loads FULL file contents from disk (deduped)
- Up to ~100K tokens stuffed into Gemini
- Best quality for complex questions spanning multiple meetings

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | BM25 search (default mode: vectorless) |
| `/search/vectorless` | POST | Explicit vectorless search |
| `/query` | POST | RAG query with LLM answer |
| `/query/vectorless` | POST | Explicit vectorless RAG query |
| `/health` | GET | Health check (FTS status) |
| `/stats` | GET | Index statistics |
| `/index/start` | POST | Trigger FTS reindex |
| `/index/progress` | GET | Indexing progress |

## What Was Removed (v3)

- ❌ Ollama (embedding generation)
- ❌ LanceDB (vector storage)
- ❌ GPU PC wake/sleep cycle
- ❌ Vector search
- ❌ Hybrid fusion (RRF)
- ❌ Reranker (used Ollama)
- ❌ Daily sync cron job (GPU-dependent)

## Indexing

FTS indexing reads all `.md` files from the Obsidian vault, chunks them,
and inserts into SQLite FTS5. This runs in seconds on CPU — no GPU needed.

Trigger manually: `POST /index/start {"full": true}`

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `API_TOKEN` | required | API auth token |
| `GEMINI_API_KEY` | required | Google Gemini API key |
| `VECTORLESS_GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model |
| `VECTORLESS_LLM_BACKEND` | `gemini` | LLM backend (gemini/openclaw) |
| `VAULT_WORK_PATH` | `/data/obsidian/work` | Work vault mount |
| `VAULT_PERSONAL_PATH` | `/data/obsidian/personal` | Personal vault mount |
