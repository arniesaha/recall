# Recall Services

Docker-based API and UI for the Recall knowledge system.

## Quick Start

### 1. Setup Environment

```bash
cp .env.example .env
# Edit .env: set API_TOKEN and GEMINI_API_KEY
```

### 2. Configure Vault Paths

Set environment variables or edit docker-compose:

```bash
export OBSIDIAN_PATH=/path/to/your/obsidian/vault
```

### 3. Start Services

```bash
docker compose up -d
```

### 4. Index Documents

```bash
curl -X POST http://localhost:8080/index/start \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vault": "all", "full": true}'
```

### 5. Test

```bash
# Health check
curl http://localhost:8080/health

# Search
curl -X POST http://localhost:8080/search \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "project timeline", "limit": 5}'

# RAG query
curl -X POST http://localhost:8080/query/vectorless \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What did we decide about the migration?"}'
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `recall-api` | 8080 | FastAPI application |
| `recall-ui` | 3000 | React frontend |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | GET | Fast liveness check |
| `/health` | GET | Health check + FTS stats |
| `/search` | POST | BM25 search |
| `/query` | POST | RAG query with Gemini answer |
| `/query/vectorless` | POST | Explicit vectorless RAG query |
| `/prep/{person}` | GET | 1:1 preparation context |
| `/index/start` | POST | Start FTS indexing |
| `/index/progress` | GET | Indexing progress |
| `/stats` | GET | Index statistics |
| `/browse` | GET | File tree |
| `/note` | GET | Note content |

## Search Modes

| Mode | Context | Description |
|------|---------|-------------|
| `vectorless` | ~7K tokens | BM25 top-50 chunks → Gemini (default) |
| `fullcontext` | ~100K tokens | Full source files → Gemini (best quality) |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_TOKEN` | Yes | API authentication |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `VECTORLESS_LLM_BACKEND` | No | `gemini` (default) or `openclaw` |
| `VECTORLESS_GEMINI_MODEL` | No | Default: `gemini-2.5-flash` |

## Logs

```bash
docker logs -f recall-api
```
