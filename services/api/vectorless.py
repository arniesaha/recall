"""
Vectorless RAG module for Recall

Uses BM25 retrieval + long-context LLM for answering instead of vector embeddings.
Eliminates the need for Ollama/GPU for search — only needs an LLM API.

Search flow:
  Query → Temporal parsing → BM25 retrieval (top-K) → Stuff into LLM context → Answer

Supports two modes:
  - "vectorless": BM25 retrieval + LLM answer (fast, no GPU)
  - "fullcontext": Load entire vault files matching BM25 hits into LLM context (best quality)
"""

import os
import logging
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import httpx

from config import Settings
from fts_index import FTSIndex
from temporal import parse_temporal_expression, extract_query_without_temporal

logger = logging.getLogger(__name__)


class VectorlessSearcher:
    """
    Vectorless RAG searcher that uses BM25 + long-context LLM.
    No embeddings needed. No GPU needed. Just keyword search + smart LLM.
    """
    
    def __init__(self, settings: Settings, fts_index: Optional[FTSIndex] = None):
        self.settings = settings
        self.fts_index = fts_index
        
        # LLM config
        self.llm_url = os.getenv(
            "VECTORLESS_LLM_URL",
            os.getenv("CLAWDBOT_URL", "http://host.docker.internal:18789")
        )
        self.llm_token = os.getenv(
            "VECTORLESS_LLM_TOKEN",
            os.getenv("CLAWDBOT_TOKEN", "")
        )
        self.llm_model = os.getenv("VECTORLESS_LLM_MODEL", "openclaw")
        
        # Retrieval settings
        self.bm25_top_k = int(os.getenv("VECTORLESS_BM25_TOP_K", "50"))
        self.max_context_chars = int(os.getenv("VECTORLESS_MAX_CONTEXT_CHARS", "400000"))  # ~100K tokens
        
        # Vault paths for full-context mode
        self.vault_paths = {
            "work": Path(settings.vault_work_path),
            "personal": Path(settings.vault_personal_path),
        }
    
    async def search(
        self,
        query: str,
        vault: str = "all",
        limit: int = 10,
        person: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict]:
        """Vectorless search using BM25 only."""
        if self.fts_index is None:
            logger.error("FTS index not available for vectorless search")
            return []
        
        # Parse temporal expressions
        date_range = parse_temporal_expression(query)
        if date_range:
            date_from = date_from or date_range.start
            date_to = date_to or date_range.end
            search_query = extract_query_without_temporal(query, date_range)
            logger.info(f"Vectorless temporal: {date_range}, cleaned: '{search_query}'")
        else:
            search_query = query
        
        results = self.fts_index.search(
            query=search_query,
            vault=vault,
            limit=self.bm25_top_k,
            person=person,
            date_from=date_from,
            date_to=date_to,
        )
        
        logger.info(f"Vectorless BM25: {len(results)} results for '{search_query}'")
        
        # Normalize BM25 result fields to match SearchResponse schema
        normalized = []
        for r in results[:limit]:
            normalized.append({
                "score": r.get("score", 0),
                "file_path": r.get("file_path", ""),
                "title": r.get("title", ""),
                "excerpt": r.get("snippet", r.get("excerpt", r.get("content", "")[:300])),
                "content": r.get("content", r.get("snippet", "")),
                "date": r.get("date"),
                "people": r.get("people", []),
                "category": r.get("category", ""),
                "vault": r.get("vault", ""),
            })
        return normalized
    
    async def query_with_llm(
        self,
        question: str,
        vault: str = "all",
        mode: str = "vectorless",
    ) -> Tuple[str, List[Dict], Dict]:
        """
        RAG query using vectorless approach.
        
        Modes:
          - "vectorless": BM25 top-K chunks → stuff into LLM context → answer
          - "fullcontext": Load full files matching BM25 hits → LLM context → answer
        
        Returns: (answer, sources, metadata)
        """
        start = time.time()
        
        # Step 1: BM25 retrieval
        bm25_results = await self.search(query=question, vault=vault, limit=self.bm25_top_k)
        
        if not bm25_results:
            return (
                "I couldn't find any relevant information in your notes.",
                [],
                {"mode": mode, "chunks_used": 0, "query_time_ms": int((time.time() - start) * 1000)},
            )
        
        # Step 2: Build context
        if mode == "fullcontext":
            context, sources = await self._build_fullcontext(bm25_results)
        else:
            context, sources = self._build_chunked_context(bm25_results)
        
        context_chars = len(context)
        context_est_tokens = context_chars // 4
        
        logger.info(
            f"Vectorless context: {len(sources)} sources, "
            f"~{context_est_tokens:,} tokens ({context_chars:,} chars)"
        )
        
        # Step 3: LLM generation
        answer = await self._generate_answer(question, context, sources)
        
        duration_ms = int((time.time() - start) * 1000)
        
        metadata = {
            "mode": mode,
            "chunks_used": len(sources),
            "context_chars": context_chars,
            "context_est_tokens": context_est_tokens,
            "bm25_retrieved": len(bm25_results),
            "query_time_ms": duration_ms,
        }
        
        return answer, sources, metadata
    
    def _build_chunked_context(self, results: List[Dict]) -> Tuple[str, List[Dict]]:
        """Build context from BM25 result chunks within token budget."""
        context_parts = []
        sources = []
        total_chars = 0
        
        for i, result in enumerate(results):
            content = result.get("content", result.get("excerpt", ""))
            title = result.get("title", "Unknown")
            date = result.get("date", "undated")
            file_path = result.get("file_path", "")
            vault = result.get("vault", "")
            score = result.get("score", 0)
            
            if any(excl in file_path for excl in self.settings.excluded_folders_list):
                continue
            
            chunk_text = f"[Source {i+1}: {title} | {date} | {vault}]\n{content}\n"
            if total_chars + len(chunk_text) > self.max_context_chars:
                logger.info(f"Context budget reached at source {i+1}/{len(results)}")
                break
            
            context_parts.append(chunk_text)
            total_chars += len(chunk_text)
            
            sources.append({
                "file": file_path,
                "title": title,
                "date": date,
                "vault": vault,
                "score": score,
                "excerpt": content[:200] + "..." if len(content) > 200 else content,
            })
        
        return "\n".join(context_parts), sources
    
    async def _build_fullcontext(self, results: List[Dict]) -> Tuple[str, List[Dict]]:
        """Build full-file context from BM25 hits (deduped by file)."""
        context_parts = []
        sources = []
        seen_files = set()
        total_chars = 0
        
        for result in results:
            file_path = result.get("file_path", "")
            if file_path in seen_files:
                continue
            seen_files.add(file_path)
            
            if any(excl in file_path for excl in self.settings.excluded_folders_list):
                continue
            
            # Load full file
            full_content = self._load_file_content(file_path)
            if not full_content:
                full_content = result.get("content", result.get("excerpt", ""))
            
            title = result.get("title", "Unknown")
            date = result.get("date", "undated")
            vault = result.get("vault", "")
            
            file_text = f"=== {title} ({date}) [{vault}/{file_path}] ===\n{full_content}\n\n"
            
            if total_chars + len(file_text) > self.max_context_chars:
                logger.info(f"Full context budget reached at {len(seen_files)} files")
                break
            
            context_parts.append(file_text)
            total_chars += len(file_text)
            
            sources.append({
                "file": file_path,
                "title": title,
                "date": date,
                "vault": vault,
                "score": result.get("score", 0),
                "full_file": True,
                "chars": len(full_content),
            })
        
        return "\n".join(context_parts), sources
    
    def _load_file_content(self, file_path: str) -> Optional[str]:
        """Load full file content from vault paths."""
        for vault_name, vault_path in self.vault_paths.items():
            full_path = vault_path / file_path
            if full_path.exists():
                try:
                    return full_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.error(f"Error reading {full_path}: {e}")
            
            # Try stripping vault prefix
            parts = Path(file_path).parts
            if parts and parts[0] == vault_name:
                stripped = Path(*parts[1:])
                full_path = vault_path / stripped
                if full_path.exists():
                    try:
                        return full_path.read_text(encoding="utf-8")
                    except Exception as e:
                        logger.error(f"Error reading {full_path}: {e}")
        
        return None
    
    async def _generate_answer(self, question: str, context: str, sources: List[Dict]) -> str:
        """Generate answer using long-context LLM."""
        
        source_list = "\n".join(
            f"- {s['title']} ({s.get('date', 'undated')})" for s in sources[:10]
        )
        
        prompt = f"""You are a personal knowledge assistant searching through meeting notes, daily notes, and documents.

Answer this question based ONLY on the provided context. Be specific and cite dates/sources when possible.
If the context doesn't contain enough information, say so clearly.

Question: {question}

Sources ({len(sources)} documents):
{source_list}

Context:
{context}

Answer concisely but thoroughly. Reference specific meetings, dates, and people when relevant."""

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.llm_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2000,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            fallback_parts = [f"⚠️ LLM unavailable ({e}). Top BM25 results:\n"]
            for s in sources[:5]:
                fallback_parts.append(f"**{s['title']}** ({s.get('date', 'undated')})")
                fallback_parts.append(s.get("excerpt", "")[:300])
                fallback_parts.append("")
            return "\n".join(fallback_parts)
