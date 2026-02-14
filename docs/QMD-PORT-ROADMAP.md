# QMD Improvements Port — Roadmap

**Goal:** Port QMD's search quality, query expansion, reranking, and MCP support to Recall.

**Reference:** https://github.com/tobi/qmd

---

## Current State

| Feature | QMD | Recall | Status |
|---------|-----|--------|--------|
| Vector Search | ✅ embeddinggemma | ✅ Ollama nomic-embed | ✅ Done |
| BM25 (FTS) | ✅ SQLite FTS5 | ✅ SQLite FTS5 | ✅ Done |
| Hybrid Fusion | ✅ RRF | ✅ RRF | ✅ Done |
| Query Expansion | ✅ Fine-tuned 1.7B | ⬜ Basic via reranker | Partial |
| Reranking | ✅ qwen3-reranker | ✅ qwen2.5:0.5b | ✅ Done |
| RAG Answers | ❌ | ✅ Claude/LLM | ✅ Ahead |
| MCP Server | ✅ | ❌ | Future |
| HTTP API | ❌ | ✅ FastAPI | ✅ Ahead |
| Temporal Search | ❌ | ✅ | ✅ Ahead |
| Person-aware Boost | ❌ | ✅ 3:1 BM25 boost | ✅ Ahead |

---

## Phase 1: Hybrid Search (BM25 + Vector + RRF) ✅ DONE

### 1.1 SQLite FTS5 Table ✅

```python
# fts_index.py
class FTSIndex:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self._init_tables()
    
    def _init_tables(self):
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts 
            USING fts5(
                file_path,
                title,
                content,
                people,
                tokenize='porter unicode61'
            )
        """)
    
    def search(self, query: str, vault: str, date_from: str = None, 
               date_to: str = None, limit: int = 30) -> List[dict]:
        # BM25 search with date filtering
        ...
```

### 1.2 Reciprocal Rank Fusion (RRF) ✅

```python
# fusion.py
def reciprocal_rank_fusion(result_lists: List[List[dict]], k: int = 60) -> List[dict]:
    """
    Combine multiple ranked lists using RRF.
    RRF score = Σ 1/(k + rank) for each list the doc appears in
    k=60 is standard (balances high vs low ranked docs)
    """
    scores = {}
    for results in result_lists:
        for rank, doc in enumerate(results):
            doc_id = doc["file_path"]
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    ...
```

### 1.3 Person-Aware Boost ✅

When names detected in query, boost BM25 weight 3:1 vs Vector:
```python
if is_person_query and detected_names:
    result_lists = [bm25_results, bm25_results, bm25_results, vector_results]
else:
    result_lists = [bm25_results, vector_results]
```

---

## Phase 2: Query Expansion ⬜ PARTIAL

### 2.1 Current Implementation

Basic query expansion via the reranker:
```python
async def expand_query(self, query: str) -> List[str]:
    # Generates 2-3 alternative phrasings
    ...
```

### 2.2 Future: Fine-tuned Expander

QMD uses a fine-tuned 1.7B model specifically for query expansion.
Could add similar capability with:
- `qwen2.5:1.5b` or similar small model
- Fine-tune on query → expanded_queries pairs
- Run before hybrid search

---

## Phase 3: Reranking ✅ DONE

### 3.1 Cross-Encoder Reranking

Using Ollama with small model for relevance scoring:
```python
# reranker.py
class Reranker:
    def __init__(self, ollama_url: str, model: str = "qwen2.5:0.5b"):
        ...
    
    async def rerank(self, query: str, documents: List[dict], 
                     content_key: str = "content") -> List[float]:
        # Score each document's relevance to query
        ...
```

### 3.2 Position-Aware Blending

Blend RRF scores with reranker scores:
```python
def position_aware_blend(fused: List[dict], rerank_scores: List[float], 
                         alpha: float = 0.5) -> List[dict]:
    # Combine RRF and reranker scores
    ...
```

---

## Phase 4: MCP Server ⬜ FUTURE

### 4.1 What is MCP?

Model Context Protocol — allows LLMs to call tools/access data sources.

### 4.2 Potential Implementation

```python
# mcp_server.py
from mcp import Server

server = Server("recall")

@server.tool()
async def search_notes(query: str, vault: str = "all") -> str:
    """Search personal knowledge base."""
    results = await searcher.search(query, vault=vault)
    return format_results(results)

@server.tool()
async def prep_for_meeting(person: str) -> str:
    """Get context for 1:1 with a person."""
    ...
```

### 4.3 Benefits

- Claude Desktop could query notes directly
- Other MCP-compatible tools get access
- Standardized interface

---

## Phase 5: Temporal Search ✅ DONE

Added natural language date parsing:

```python
# temporal.py
def parse_temporal_expression(query: str) -> Optional[DateRange]:
    """
    Parse temporal expressions:
    - "this week" → current week
    - "last month" → previous month
    - "yesterday" → yesterday
    - "past 7 days" → last 7 days
    - "in January" → January
    """
    ...
```

Date filtering applied to both BM25 and Vector search.

---

## Implementation Summary

| Phase | Feature | Status | Files |
|-------|---------|--------|-------|
| 1 | Hybrid Search | ✅ Done | fts_index.py, fusion.py |
| 2 | Query Expansion | Partial | reranker.py |
| 3 | Reranking | ✅ Done | reranker.py |
| 4 | MCP Server | ⬜ Future | - |
| 5 | Temporal Search | ✅ Done | temporal.py |

---

## Performance Impact

| Metric | Before | After |
|--------|--------|-------|
| Person queries | Poor (embeddings miss names) | Good (BM25 boost) |
| Keyword search | Poor (semantic only) | Good (BM25 fallback) |
| Temporal queries | Wrong (matched old docs) | Correct (date filtering) |
| Query latency | ~150ms | ~200-300ms (acceptable) |

---

*Last updated: 2026-02-14*
