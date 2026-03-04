# PageIndex Integration for Recall

## Overview

Integrate PageIndex's vectorless, reasoning-based RAG for PDF documents while keeping
the existing BM25 + vector hybrid search for markdown notes.

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │           Recall API                │
                    ├─────────────────────────────────────┤
                    │                                     │
    Markdown ──────►│  BM25 + Vector Search (existing)   │
                    │                                     │
                    ├─────────────────────────────────────┤
                    │                                     │
    PDF ───────────►│  PageIndex Tree Search (new)       │
                    │                                     │
                    └─────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Tree Generation (Indexing)

**New file: `services/api/pageindex_tree.py`**

```python
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
import httpx

class PageIndexTreeGenerator:
    """Generate PageIndex tree structure from PDF using LLM."""
    
    def __init__(self, llm_url: str, model: str = "gpt-4o"):
        self.llm_url = llm_url
        self.model = model
    
    async def generate_tree(self, pages: List[tuple[int, str]], doc_name: str) -> Dict:
        """
        Generate hierarchical tree structure from PDF pages.
        
        Returns:
            {
                "doc_name": "document.pdf",
                "structure": [
                    {
                        "title": "Section Title",
                        "start_page": 1,
                        "end_page": 5,
                        "summary": "Brief summary...",
                        "node_id": "0001",
                        "nodes": [...]  # children
                    }
                ]
            }
        """
        # Combine pages into single text for analysis
        full_text = "\n\n".join([f"[Page {p}]\n{text}" for p, text in pages])
        
        prompt = f"""Analyze this document and create a hierarchical table of contents structure.
        
Document: {doc_name}

Content:
{full_text[:50000]}  # Truncate for context limits

Return a JSON structure with:
- title: Section title
- start_page: First page of section
- end_page: Last page of section  
- summary: 1-2 sentence summary of section content
- nodes: Array of child sections (recursive)

Focus on logical document structure (chapters, sections, subsections).
Return valid JSON only."""

        # Call LLM
        response = await self._call_llm(prompt)
        return self._parse_tree_response(response, doc_name)
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM API."""
        async with httpx.AsyncClient() as client:
            # Support both OpenAI and local Ollama
            response = await client.post(
                self.llm_url,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0
                },
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    
    def _parse_tree_response(self, response: str, doc_name: str) -> Dict:
        """Parse LLM response into tree structure."""
        # Extract JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            structure = json.loads(response)
            return {
                "doc_name": doc_name,
                "structure": structure if isinstance(structure, list) else [structure]
            }
        except json.JSONDecodeError:
            # Fallback: single node for entire document
            return {
                "doc_name": doc_name,
                "structure": [{
                    "title": doc_name,
                    "start_page": 1,
                    "end_page": 999,
                    "summary": "Full document",
                    "node_id": "0000"
                }]
            }
```

### Phase 2: Tree Storage

**Storage options:**

1. **JSON files** (simple):
   - Store at `data/trees/{vault}/{doc_hash}.json`
   - Pros: Easy to inspect, no schema changes
   - Cons: Separate from main index

2. **SQLite table** (integrated):
   - New table `pdf_trees` with columns: doc_hash, doc_name, tree_json, created_at
   - Pros: Single DB, easy queries
   - Cons: JSON in SQL

**Recommendation:** JSON files for simplicity, with SQLite index for lookups.

### Phase 3: Tree Search (Retrieval)

**New endpoint: `POST /tree-search`**

```python
@app.post("/tree-search")
async def tree_search(query: str, vault: str = "work"):
    """
    Reasoning-based search over PDF documents using PageIndex trees.
    """
    # 1. Load all trees for vault
    trees = load_trees_for_vault(vault)
    
    # 2. LLM selects relevant documents
    doc_selection_prompt = f"""Given this query, which documents are most likely to contain relevant information?

Query: {query}

Available documents:
{format_doc_summaries(trees)}

Return JSON: {{"docs": ["doc1.pdf", "doc2.pdf"]}}"""
    
    selected_docs = await call_llm(doc_selection_prompt)
    
    # 3. For each selected doc, LLM searches tree
    results = []
    for doc in selected_docs:
        tree = trees[doc]
        
        search_prompt = f"""Find sections in this document that answer the query.

Query: {query}

Document structure:
{json.dumps(tree["structure"], indent=2)}

Return JSON: {{"node_ids": ["0001", "0003"], "reasoning": "..."}}"""
        
        node_selection = await call_llm(search_prompt)
        
        # 4. Retrieve full text of selected nodes
        for node_id in node_selection["node_ids"]:
            node = find_node_by_id(tree, node_id)
            text = get_pages_text(doc, node["start_page"], node["end_page"])
            results.append({
                "doc": doc,
                "section": node["title"],
                "pages": f"{node['start_page']}-{node['end_page']}",
                "text": text,
                "reasoning": node_selection["reasoning"]
            })
    
    return {"query": query, "results": results}
```

### Phase 4: Integration with Existing Search

**Hybrid approach in `/query` endpoint:**

```python
@app.post("/query")
async def query(request: QueryRequest):
    # Existing: BM25 + vector search for markdown
    markdown_results = await hybrid_search(request.query, request.vault)
    
    # New: Tree search for PDFs (if enabled)
    pdf_results = []
    if settings.pageindex_enabled:
        pdf_results = await tree_search(request.query, request.vault)
    
    # Combine results
    all_context = format_results(markdown_results, pdf_results)
    
    # Generate answer
    answer = await generate_answer(request.query, all_context)
    
    return {
        "answer": answer,
        "sources": {
            "markdown": markdown_results,
            "pdf": pdf_results
        }
    }
```

## Configuration

Add to `config.py`:

```python
class Settings:
    # ... existing ...
    
    # PageIndex settings
    pageindex_enabled: bool = True
    pageindex_tree_dir: str = "data/trees"
    
    # LLM Provider: "max" (recommended), "gpu", or "openai"
    pageindex_llm_provider: str = "max"
    
    # Max (Mac Mini) - Primary, always on
    max_gateway_url: str = "http://192.168.1.149:18789"
    max_gateway_token: str = ""  # Set from environment
    max_model: str = "anthropic/claude-sonnet-4-5"
    
    # GPU PC - Fallback, free but needs wake
    gpu_ollama_url: str = "http://10.10.10.2:11434"
    gpu_model: str = "qwen2.5:32b"
    
    # OpenAI - Alternative cloud option
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
```

## LLM Provider Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Recall API (NAS)                         │
│                     192.168.1.70:30889                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐│
│  │   Markdown      │    │         PDF Documents               ││
│  │   Documents     │    │                                     ││
│  └────────┬────────┘    └────────────────┬────────────────────┘│
│           │                              │                      │
│           ▼                              ▼                      │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐│
│  │  BM25 + Vector  │    │      PageIndex Tree Search          ││
│  │  (Existing)     │    │      (New)                          ││
│  │  Cost: FREE     │    │                                     ││
│  └─────────────────┘    └────────────────┬────────────────────┘│
│                                          │                      │
└──────────────────────────────────────────┼──────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
          ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
          │   Max (Primary) │    │  GPU PC (Free)  │    │ OpenAI (Cloud)  │
          │   Mac Mini      │    │  RTX 5090       │    │                 │
          │   Claude Sonnet │    │  Ollama         │    │  GPT-4o         │
          ├─────────────────┤    ├─────────────────┤    ├─────────────────┤
          │ IP: 192.168.1   │    │ IP: 10.10.10.2  │    │ api.openai.com  │
          │     .149:18789  │    │     :11434      │    │                 │
          │ Always On: ✅    │    │ Always On: ❌    │    │ Always On: ✅    │
          │ Speed: ~3-5s    │    │ Speed: ~10-20s  │    │ Speed: ~2-3s    │
          │ Cost: API tokens│    │ Cost: $0        │    │ Cost: API tokens│
          └─────────────────┘    └─────────────────┘    └─────────────────┘
                 │                       │
                 │              (Wake via WoL server)
                 │              curl 192.168.1.70:9753/wake
                 │                       │
                 └───────────┬───────────┘
                             │
                    Fallback Chain:
                    1. Try Max (fast, always on)
                    2. If fail → Wake GPU, try Ollama
                    3. If fail → Error
```

## LLM Call Implementation

```python
# pageindex_llm.py

import httpx
import logging
from config import Settings

logger = logging.getLogger(__name__)

class PageIndexLLM:
    """LLM client for PageIndex with fallback support."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.wol_url = "http://192.168.1.70:9753"
    
    async def call(self, prompt: str) -> str:
        """Call LLM with automatic fallback."""
        
        # Primary: Max (Mac Mini)
        if self.settings.pageindex_llm_provider in ("max", "auto"):
            try:
                return await self._call_max(prompt)
            except Exception as e:
                logger.warning(f"Max unavailable: {e}")
                if self.settings.pageindex_llm_provider == "max":
                    raise
        
        # Fallback: GPU PC (free)
        if self.settings.pageindex_llm_provider in ("gpu", "auto"):
            try:
                await self._wake_gpu_if_needed()
                return await self._call_gpu(prompt)
            except Exception as e:
                logger.warning(f"GPU unavailable: {e}")
                if self.settings.pageindex_llm_provider == "gpu":
                    raise
        
        # Last resort: OpenAI
        if self.settings.openai_api_key:
            return await self._call_openai(prompt)
        
        raise Exception("No LLM provider available")
    
    async def _call_max(self, prompt: str) -> str:
        """Call Max's OpenClaw gateway."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.max_gateway_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.max_gateway_token}"},
                json={
                    "model": self.settings.max_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0
                },
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    
    async def _call_gpu(self, prompt: str) -> str:
        """Call GPU PC's Ollama."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.gpu_ollama_url}/v1/chat/completions",
                json={
                    "model": self.settings.gpu_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0
                },
                timeout=180.0  # Longer timeout for local model
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    
    async def _wake_gpu_if_needed(self) -> bool:
        """Wake GPU PC via WoL server if not responding."""
        async with httpx.AsyncClient() as client:
            # Check if already awake
            try:
                await client.get(
                    f"{self.settings.gpu_ollama_url}/api/tags",
                    timeout=5.0
                )
                return True  # Already awake
            except:
                pass
            
            # Send WoL
            logger.info("Waking GPU PC...")
            await client.get(f"{self.wol_url}/wake", timeout=10.0)
            
            # Wait for it to come up (max 90s)
            for _ in range(18):
                await asyncio.sleep(5)
                try:
                    await client.get(
                        f"{self.settings.gpu_ollama_url}/api/tags",
                        timeout=5.0
                    )
                    logger.info("GPU PC is awake")
                    return True
                except:
                    continue
            
            raise Exception("GPU PC did not wake up in time")
    
    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API directly."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={
                    "model": self.settings.openai_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0
                },
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
```

## File Structure

```
recall/
├── services/api/
│   ├── main.py              # Add /tree-search endpoint
│   ├── indexer.py           # Add tree generation to PDF indexing
│   ├── pageindex_tree.py    # NEW: Tree generation
│   ├── tree_search.py       # NEW: Tree search logic
│   └── config.py            # Add pageindex settings
├── data/
│   ├── lancedb/             # Existing vector store
│   ├── pdfs/                # Existing PDF storage
│   └── trees/               # NEW: Tree JSON files
│       ├── work/
│       └── personal/
```

## Migration Path

1. **Phase 1:** Add tree generation (indexing side)
   - New files: `pageindex_tree.py`
   - Modify: `indexer.py` to generate trees during PDF indexing
   - Trees stored as JSON files

2. **Phase 2:** Add tree search (query side)
   - New files: `tree_search.py`
   - New endpoint: `/tree-search`
   - Keep existing endpoints unchanged

3. **Phase 3:** Integrate into `/query`
   - Combine markdown + PDF results
   - Add `pageindex_enabled` toggle
   - Backwards compatible (disabled by default)

## Cost Considerations

| Operation | LLM Calls | Estimated Cost |
|-----------|-----------|----------------|
| Index 1 PDF (tree gen) | 1-2 | ~$0.05-0.10 |
| Query (doc selection) | 1 | ~$0.01 |
| Query (tree search per doc) | 1-3 | ~$0.02-0.06 |
| **Total per query** | 2-5 | ~$0.03-0.15 |

Compare to current vector search: ~$0 per query (just vector math)

**Recommendation:** Cache tree search results for common queries, or use smaller/local models for tree search.

## Local Model Option

Use Ollama with a capable model for tree generation/search:

```python
# config.py
pageindex_llm_url: str = "http://10.10.10.2:11434/v1/chat/completions"  # GPU PC
pageindex_model: str = "qwen2.5:32b"  # Good at structured output
```

This eliminates API costs but requires GPU PC to be on during indexing.

---

## Next Steps

1. [ ] Review and approve this design
2. [ ] Implement `pageindex_tree.py`
3. [ ] Modify indexer to generate trees
4. [ ] Implement `/tree-search` endpoint
5. [ ] Test with existing PDFs (Richie health reports)
6. [ ] Integrate into `/query` if results are good
