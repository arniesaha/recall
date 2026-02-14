# Recall — Technical Specification

**Status:** ✅ Implemented
**Goal:** Personal knowledge base + intelligence API for note search and retrieval

---

## Vision

Transform meeting notes, documents, and accumulated knowledge into a queryable system that provides:
- Decision recall ("What did we decide about X?")
- 1:1 prep ("Context on Alex before our meeting")
- Project context ("Catch me up on Project Y")
- Temporal search ("What happened this week?")
- Pattern detection ("You've mentioned Z concern 5 times...")

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                   │
├──────────────────┬────────────────────┬─────────────────────────────────┤
│     Granola      │  Existing Obsidian │      Future Sources             │
│ (meeting notes)  │      Vault         │  (Slack exports, docs, etc)     │
└────────┬─────────┴─────────┬──────────┴──────────────┬──────────────────┘
         │                   │                         │
         ▼                   ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         OBSIDIAN VAULT (NAS)                            │
│                                                                         │
│   daily-notes/    Granola/Transcripts/    personal/       PDFs/        │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
   ┌──────────┐            ┌──────────┐            ┌──────────┐
   │ Extract  │            │ Ollama   │            │ LanceDB  │
   │ Metadata │ ─────────→ │ Embed    │ ─────────→ │ (Vector) │
   │          │            │ (local)  │            │          │
   └──────────┘            └──────────┘            └──────────┘
                                                         │
                                                         ▼
                                              ┌──────────────────┐
                                              │  Recall API      │
                                              │  (FastAPI)       │
                                              │  :8080           │
                                              └──────────────────┘
```

---

## Phase 1: Data Pipeline ✅

### 1.1 Granola → Obsidian Sync

**Current Flow:**
```
Granola App (Mac)
        │
        ▼
Obsidian Sync (iCloud)
        │
        ▼
NAS File Sync
        │
        ▼
Obsidian Vault:
  - work/daily-notes/
  - work/Granola/Transcripts/
```

**File Structure:**
```markdown
---
date: 2026-02-14
type: meeting
attendees: [Alex, Jordan]
---

# Meeting Title

## Notes
...

## Action Items
- [ ] Task 1
- [x] Task 2
```

### 1.2 File Watcher

**Implementation:** Built into API using incremental indexing

**Behavior:**
1. Detect new/modified files via mtime
2. Hash content for change detection
3. Chunk and embed changed files only
4. Update FTS index in parallel

---

## Phase 2: Indexing Pipeline ✅

### 2.1 Document Processing

**Chunking Strategy:**
- Target: 500 tokens per chunk
- Overlap: 50 tokens
- Respect section boundaries where possible
- PDF: Page-aware chunking (chunks don't cross pages)

**Metadata Extraction:**
- Date from filename or frontmatter
- People from content (name detection)
- Category from folder path
- Title from first heading or filename

### 2.2 Embedding

**Model:** `nomic-embed-text`
- 768 dimensions
- Local (Ollama)
- CPU: ~3 seconds per document
- GPU: ~0.1 seconds per document

### 2.3 Storage

**LanceDB Tables:**
- `work` - Work vault documents
- `personal` - Personal vault documents

**FTS Index:**
- SQLite FTS5 for BM25 keyword search
- Porter stemming + unicode normalization
- Synced with LanceDB

---

## Phase 3: Query API ✅

### 3.1 Search Modes

| Mode | Algorithm | Use Case |
|------|-----------|----------|
| `vector` | Pure semantic | General questions |
| `bm25` | Pure keyword | Exact matches, names |
| `hybrid` | BM25 + Vector RRF | Recommended default |
| `query` | Hybrid + expansion + rerank | Highest quality |

### 3.2 Temporal Parsing

**Supported Expressions:**
- `today`, `yesterday`
- `this week`, `last week`
- `this month`, `last month`
- `past N days`, `last N days`
- `in January`, `February`, etc.
- `last Monday`, `on Tuesday`
- Specific dates: `Feb 10`, `2026-02-10`

**Implementation:**
```python
# temporal.py
def parse_temporal_expression(query: str) -> Optional[DateRange]:
    # Returns DateRange(start, end, expression) if found
    # Returns None if no temporal expression detected
```

### 3.3 Person-Aware Search

When query contains person names:
1. Detect names using capitalization heuristics
2. Use name-only query for BM25 (avoids phrase matching issues)
3. Boost BM25 weight 3:1 vs Vector
4. Better results for "prep for 1:1 with Alex"

---

## Phase 4: RAG Answers ✅

### 4.1 Context Building

1. Search for relevant chunks (top 10)
2. Deduplicate by file
3. Build prompt with sources
4. Send to LLM

### 4.2 Answer Generation

**Prompt Template:**
```
Based on the following context from my notes, answer this question:

Context:
[chunk 1]
[chunk 2]
...

Question: {user_question}

Provide a concise answer with references to specific sources.
```

---

## Phase 5: Specialized Endpoints ✅

### 5.1 1:1 Prep (`/prep/{person}`)

Returns:
- Recent meeting count
- Last meeting date
- Recent topics discussed
- Open action items
- Recent meeting summaries

### 5.2 Indexing Progress (`/index/progress`)

Returns:
- Running status
- Files processed / total
- Percentage complete
- ETA (human readable)
- Current file being processed

---

## Phase 6: UI ✅

### 6.1 Features

- Natural language search
- AI answers with sources
- Note viewer (markdown rendered)
- Folder browser
- Dark mode default
- Mobile responsive

### 6.2 Tech Stack

- React 18 + Vite
- TailwindCSS
- React Query for data fetching
- Nginx for production serving

---

## Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| Search latency | < 1s | ~200ms |
| RAG query | < 10s | ~3-5s |
| Full reindex (CPU) | < 24h | ~20h |
| Full reindex (GPU) | < 30m | ~5m |
| Index size (20k docs) | < 1GB | ~500MB |

---

## Configuration

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `API_TOKEN` | Authentication token |
| `OLLAMA_URL` | Ollama endpoint |
| `LANCEDB_PATH` | Vector DB location |
| `VAULT_WORK_PATH` | Work notes path |
| `VAULT_PERSONAL_PATH` | Personal notes path |
| `PDF_ENABLED` | Enable PDF indexing |
| `CHUNK_SIZE` | Target chunk size |
| `LOG_LEVEL` | Logging verbosity |

---

## Security

- All data stays on local NAS
- Bearer token authentication
- No external embedding API calls
- LLM API calls configurable (local or cloud)
- Finance folder excluded from LLM context

---

## Future Enhancements

- [ ] Calendar integration for proactive prep
- [ ] Slack/Discord bot for quick queries
- [ ] Voice search
- [ ] Weekly digest emails
- [ ] Pattern detection ("mentioned X 5 times")
- [ ] Multi-user support

---

*Last updated: 2026-02-14*
