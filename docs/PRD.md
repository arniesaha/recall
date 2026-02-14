# Recall — Product Requirements Document

**Version:** 1.1
**Date:** 2026-02-14
**Status:** Active

---

## 1. Overview

### 1.1 Problem Statement

As an Engineering Manager with 300+ meetings per year, valuable context is scattered across:
- Meeting notes (Granola transcripts)
- 1:1 documentation
- Project updates
- Decision records
- Personal notes

Finding relevant information requires manually searching through files, leading to:
- Lost context before 1:1s
- Forgotten decisions
- Repeated discussions
- Missed action items

### 1.2 Solution

Build a **personal knowledge system** that:
1. Automatically organizes incoming meeting notes
2. Provides intelligent search across all content
3. Surfaces relevant context proactively
4. Works across both work and personal vaults

### 1.3 Success Metrics

| Metric | Target |
|--------|--------|
| Time to find context for 1:1 | < 30 seconds |
| Query response time | < 5 seconds |
| New file auto-categorization accuracy | > 90% |
| Daily active usage | Used before every 1:1 |

---

## 2. User Stories

### 2.1 Core User Stories

**US-1: Pre-meeting Context**
> As an EM, I want to quickly get context on a person before our 1:1, so I can have a more productive conversation.

Acceptance Criteria:
- Query "prep for 1:1 with Alex" returns recent topics, open action items, and discussion history
- Response includes links to source notes
- Works within 5 seconds

**US-2: Decision Recall**
> As an EM, I want to recall past decisions on a topic, so I don't repeat discussions or contradict prior choices.

Acceptance Criteria:
- Query "what did we decide about the migration timeline?" returns relevant decisions with dates
- Includes context of who was involved and why

**US-3: Action Item Tracking**
> As an EM, I want to see open action items for my team, so nothing falls through the cracks.

Acceptance Criteria:
- Query "open action items for Jordan" returns pending tasks
- Grouped by date/meeting
- Can filter by project

**US-4: Automatic Organization**
> As a user, I want new Granola notes to be automatically categorized, so I don't have to manually organize files.

Acceptance Criteria:
- New files detected within 5 minutes
- Correctly categorized to people/, projects/, team/, etc.
- Frontmatter added automatically

**US-5: Cross-Vault Search**
> As a user, I want to search across both work and personal vaults, so I have one interface for all my knowledge.

Acceptance Criteria:
- Single search endpoint queries both vaults
- Results indicate source vault
- Can filter by vault if needed

**US-6: Temporal Search**
> As a user, I want to search for "meetings this week" and get only this week's results.

Acceptance Criteria:
- Natural language date expressions parsed automatically
- Supports: today, yesterday, this week, last month, specific dates
- Results filtered to correct date range

### 2.2 Future User Stories (v2)

- **US-7:** Weekly digest of themes and patterns
- **US-8:** Meeting prep suggestions based on calendar
- **US-9:** Integration with Slack for quick queries
- **US-10:** Voice query via mobile

---

## 3. Functional Requirements

### 3.1 File Watcher & Restructurer

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-1.1 | Watch work/ and personal/ folders for new/modified files | P0 | ✅ |
| FR-1.2 | Categorize files based on content and filename | P0 | ✅ |
| FR-1.3 | Move files to appropriate subfolders | P0 | ✅ |
| FR-1.4 | Add/update YAML frontmatter | P0 | ⏸️ Skipped |
| FR-1.5 | Extract entities (people, projects) from content | P1 | ✅ |
| FR-1.6 | Configurable watch interval (default: 5 min) | P1 | ✅ |

### 3.2 Indexing Pipeline

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-2.1 | Chunk documents by section/paragraph | P0 | ✅ |
| FR-2.2 | Generate embeddings using nomic-embed-text | P0 | ✅ |
| FR-2.3 | Store vectors in LanceDB with metadata | P0 | ✅ |
| FR-2.4 | Incremental indexing (only new/changed files) | P0 | ✅ |
| FR-2.5 | Full reindex capability | P1 | ✅ |
| FR-2.6 | Track indexing status per file | P1 | ✅ |
| FR-2.7 | GPU offload for fast indexing | P2 | ✅ |

### 3.3 Query API

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-3.1 | Semantic search across indexed content | P0 | ✅ |
| FR-3.2 | Filter by vault (work/personal) | P0 | ✅ |
| FR-3.3 | Filter by category (people, projects, etc.) | P0 | ✅ |
| FR-3.4 | Filter by date range | P1 | ✅ |
| FR-3.5 | Filter by person | P1 | ✅ |
| FR-3.6 | Return source file links | P0 | ✅ |
| FR-3.7 | Temporal expression parsing | P1 | ✅ |

### 3.4 RAG Answers

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-4.1 | Generate natural language answers using LLM | P0 | ✅ |
| FR-4.2 | Include source citations in response | P0 | ✅ |
| FR-4.3 | Support follow-up questions (context retention) | P2 | ⬜ |
| FR-4.4 | Configurable LLM (Claude/local) | P2 | ⬜ |

### 3.5 Specialized Endpoints

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-5.1 | `/prep/{person}` — 1:1 preparation context | P0 | ✅ |
| FR-5.2 | `/actions/{person}` — Open action items | P1 | ⬜ |
| FR-5.3 | `/decisions` — Recent decisions log | P1 | ⬜ |
| FR-5.4 | `/focus` — Weekly focus areas | P2 | ⬜ |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Target | Status |
|----|-------------|--------|--------|
| NFR-1.1 | Query response time | < 5 seconds | ✅ |
| NFR-1.2 | File categorization time | < 2 seconds/file | ✅ |
| NFR-1.3 | Embedding generation (GPU) | < 5 min full reindex | ✅ |
| NFR-1.4 | Concurrent queries supported | 5 | ✅ |

### 4.2 Availability

| ID | Requirement | Target | Status |
|----|-------------|--------|--------|
| NFR-2.1 | Service uptime | 99% (NAS uptime) | ✅ |
| NFR-2.2 | Auto-restart on failure | Yes | ✅ |
| NFR-2.3 | Graceful degradation if Ollama unavailable | Yes | ✅ |

### 4.3 Security & Privacy

| ID | Requirement | Target | Status |
|----|-------------|--------|--------|
| NFR-3.1 | All data stays on NAS | Yes | ✅ |
| NFR-3.2 | No external API for embeddings | Yes (Ollama local) | ✅ |
| NFR-3.3 | LLM API only for answer generation | Configurable | ✅ |
| NFR-3.4 | API authentication | Bearer token | ✅ |

### 4.4 Maintainability

| ID | Requirement | Target | Status |
|----|-------------|--------|--------|
| NFR-4.1 | Containerized deployment | Yes | ✅ |
| NFR-4.2 | Configuration via environment variables | Yes | ✅ |
| NFR-4.3 | Structured logging | Yes | ✅ |
| NFR-4.4 | Health check endpoint | Yes | ✅ |
| NFR-4.5 | Prometheus metrics | Yes | ✅ |

---

## 5. Out of Scope (v1)

- Mobile app
- Real-time sync (polling-based is fine)
- Multi-user support
- Calendar integration
- Slack bot
- Voice interface

---

## 6. Dependencies

| Dependency | Purpose | Status |
|------------|---------|--------|
| Obsidian vault on NAS | Content source | ✅ Ready |
| Granola → Obsidian sync | Work content | ✅ Working |
| Docker/k8s on NAS | Container runtime | ✅ Working |
| Ollama | Embeddings | ✅ Working |
| LanceDB | Vector storage (embedded) | ✅ Working |
| LLM API | Answer generation | ✅ Available |

---

## 7. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| NAS CPU too slow for embeddings | Slow indexing | Medium | ✅ GPU offload implemented |
| Vector DB memory usage too high | NAS instability | Low | ✅ Using LanceDB (file-based) |
| Poor categorization accuracy | Manual cleanup needed | Medium | Improve classification rules |
| Granola sync breaks | Missing new notes | Low | Monitor sync; alert on failures |

---

## 8. Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Infrastructure | 1 week | ✅ Complete |
| Phase 2: Indexing | 1 week | ✅ Complete |
| Phase 3: Query API | 1 week | ✅ Complete |
| Phase 4: UI | 1 week | ✅ MVP Complete |
| Phase 5: Polish | Ongoing | 🔄 Active |

---

## 9. Decisions Made

| Question | Decision |
|----------|----------|
| **Vector DB?** | LanceDB (embedded, file-based, easy backup) |
| **UI framework?** | React + Vite + TailwindCSS |
| **Reindex frequency?** | Incremental on file change + daily full reindex |
| **Search algorithm?** | Hybrid BM25 + Vector with RRF fusion |
| **GPU offload?** | Yes, via WoL to dedicated GPU machine |

---

*Document Version History:*
- v1.1 (2026-02-14): Added temporal search, updated status
- v1.0 (2026-02-01): Initial draft
