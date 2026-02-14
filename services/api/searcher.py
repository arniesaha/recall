"""
Searcher module for note-rag
Handles semantic search, hybrid search, and RAG queries

v2: Added BM25 + Vector hybrid search with RRF fusion and reranking
v3: Added name-aware hybrid boost for better person search
v4: Added temporal expression parsing for date-aware search
"""

import os
import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path

import httpx
import lancedb

from config import Settings
from fusion import reciprocal_rank_fusion, position_aware_blend, normalize_scores
from fts_index import FTSIndex
from reranker import Reranker
from temporal import parse_temporal_expression, extract_query_without_temporal, DateRange

logger = logging.getLogger(__name__)


# Common words to exclude from name detection
COMMON_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought',
    'used', 'what', 'who', 'which', 'when', 'where', 'why', 'how', 'all',
    'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
    'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
    'just', 'also', 'now', 'here', 'there', 'then', 'once', 'about', 'after',
    'before', 'between', 'into', 'through', 'during', 'above', 'below',
    # Query-specific words
    'meeting', 'meetings', 'one-on-one', '1:1', 'prep', 'prepare', 'notes',
    'summary', 'action', 'items', 'discussion', 'talked', 'discussed', 'said',
    'mentioned', 'topic', 'topics', 'project', 'team', 'work', 'update',
    'weekly', 'daily', 'monthly', 'review', 'feedback', 'performance',
    # Common tech terms that might be capitalized
    'API', 'UI', 'UX', 'SQL', 'AWS', 'GCP', 'PR', 'CI', 'CD',
    # Month names (avoid treating "Jan" as person name)
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec',
    # Days of week
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun',
    # Other common false positives
    'highlights', 'summary', 'overview', 'report', 'analysis',
}


def detect_names(query: str) -> Set[str]:
    """
    Detect likely person names in a query.
    
    Heuristics:
    - Capitalized words that aren't at sentence start
    - Words that aren't common English words
    - Excludes known tech acronyms
    
    Returns:
        Set of detected name tokens
    """
    names = set()
    words = query.split()
    
    for i, word in enumerate(words):
        # Clean the word
        clean = re.sub(r'[^\w]', '', word)
        if not clean:
            continue
        
        # Check if capitalized (but not all caps like "API")
        if clean[0].isupper() and not clean.isupper():
            # Skip if it's a common word
            if clean.lower() not in COMMON_WORDS:
                # Skip if first word (might just be sentence start)
                # Unless it looks like a name (short, no numbers)
                if i > 0 or (len(clean) <= 15 and not any(c.isdigit() for c in clean)):
                    names.add(clean)
    
    return names


def has_person_query_intent(query: str) -> bool:
    """
    Detect if query is looking for information about a specific person.
    
    Signals:
    - Contains phrases like "1:1", "one-on-one", "meeting with"
    - Contains "prep for" or "prepare for"
    - Contains a detected name
    """
    query_lower = query.lower()
    
    # Person-related patterns
    person_patterns = [
        r'\b1:1\b',
        r'\bone[- ]on[- ]one\b',
        r'\bmeeting with\b',
        r'\bprep for\b',
        r'\bprepare for\b',
        r'\bcatch up with\b',
        r'\bsync with\b',
    ]
    
    for pattern in person_patterns:
        if re.search(pattern, query_lower):
            return True
    
    # Check for names
    names = detect_names(query)
    return len(names) > 0


class Searcher:
    def __init__(self, db: lancedb.DBConnection, settings: Settings, fts_db_path: Optional[str] = None, fts_index=None):
        self.db = db
        self.settings = settings
        
        # Use provided FTS index or create one
        if fts_index is not None:
            self.fts_index = fts_index
        elif fts_db_path:
            try:
                self.fts_index = FTSIndex(fts_db_path)
            except Exception as e:
                logger.warning(f"Could not initialize FTS: {e}")
                self.fts_index = None
        else:
            self.fts_index = None
        
        # Initialize reranker
        self.reranker = Reranker(
            ollama_url=settings.ollama_url,
            model="qwen2.5:0.5b"  # Fast model for reranking
        )
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding from Ollama."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.ollama_url}/api/embed",
                json={
                    "model": self.settings.embedding_model,
                    "input": text
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"][0]
    
    async def vector_search(
        self,
        query: str,
        vault: str = "all",
        category: Optional[str] = None,
        person: Optional[str] = None,
        limit: int = 30,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict]:
        """Pure vector search using LanceDB."""
        
        query_embedding = await self.get_embedding(query)
        
        results = []
        
        tables_to_search = []
        if vault in ["all", "work"]:
            tables_to_search.append("work")
        if vault in ["all", "personal"]:
            tables_to_search.append("personal")
        
        for table_name in tables_to_search:
            try:
                table = self.db.open_table(table_name)
                
                search = table.search(query_embedding)
                
                filters = []
                if category:
                    filters.append(f'category = "{category}"')
                if person:
                    filters.append(f'array_contains(people, "{person}")')
                if date_from:
                    filters.append(f'date >= "{date_from}"')
                if date_to:
                    filters.append(f'date <= "{date_to}"')
                
                if filters:
                    search = search.where(" AND ".join(filters))
                
                search_results = search.limit(limit).to_list()
                
                for r in search_results:
                    content = r.get("content", "")
                    excerpt = content[:300] + "..." if len(content) > 300 else content
                    
                    # Convert distance to similarity score (1 / (1 + distance))
                    distance = float(r.get("_distance", 0))
                    score = 1.0 / (1.0 + distance)
                    
                    results.append({
                        "score": score,
                        "file_path": r.get("file_path", ""),
                        "title": r.get("title", ""),
                        "content": content,
                        "excerpt": excerpt,
                        "date": r.get("date"),
                        "people": r.get("people", []),
                        "category": r.get("category", ""),
                        "vault": table_name,
                        "source": "vector"
                    })
            
            except Exception as e:
                logger.error(f"Error searching {table_name}: {e}")
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    async def bm25_search(
        self,
        query: str,
        vault: str = "all",
        person: Optional[str] = None,
        limit: int = 30,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict]:
        """BM25 keyword search using SQLite FTS5."""
        if self.fts_index is None:
            logger.debug("FTS index unavailable, returning empty results")
            return []
        return self.fts_index.search(
            query=query,
            vault=vault,
            limit=limit,
            person=person,
            date_from=date_from,
            date_to=date_to
        )
    
    async def hybrid_search(
        self,
        query: str,
        vault: str = "all",
        category: Optional[str] = None,
        person: Optional[str] = None,
        limit: int = 10,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict]:
        """
        Hybrid search combining BM25 + Vector using RRF fusion.
        
        This is the recommended search method for best quality.
        
        Name-aware boost: When query contains person names, BM25 is weighted
        higher (3:1 ratio) because embedding models don't handle proper nouns well.
        Also uses name-only search for BM25 to avoid FTS phrase matching issues.
        
        Temporal awareness: If query contains temporal expressions like "this week"
        or "last month", automatically filters results to that date range.
        """
        import asyncio
        
        # Parse temporal expressions from query
        date_range = parse_temporal_expression(query)
        if date_range:
            # Use parsed date range
            date_from = date_range.start
            date_to = date_range.end
            # Clean query to remove temporal expression for better semantic search
            search_query = extract_query_without_temporal(query, date_range)
            logger.info(f"Temporal query detected: {date_range}, cleaned query: '{search_query}'")
        else:
            search_query = query
        
        # Detect if this is a person-focused query
        detected_names = detect_names(search_query)
        is_person_query = has_person_query_intent(search_query) or len(detected_names) > 0
        
        # For person queries, use just the name(s) for BM25 to avoid phrase matching issues
        # e.g., "one-on-one with Nikhil" -> BM25 searches for "Nikhil"
        if is_person_query and detected_names:
            bm25_query = " ".join(detected_names)
            logger.info(f"Person query detected. Names: {detected_names}, BM25 query: '{bm25_query}'")
        else:
            bm25_query = search_query
        
        # Run BM25 and vector search in parallel
        bm25_task = self.bm25_search(bm25_query, vault, person, limit=30, date_from=date_from, date_to=date_to)
        vector_task = self.vector_search(search_query, vault, category, person, limit=30, date_from=date_from, date_to=date_to)
        
        bm25_results, vector_results = await asyncio.gather(bm25_task, vector_task)
        
        logger.info(f"Hybrid search: BM25={len(bm25_results)}, Vector={len(vector_results)}, person_query={is_person_query}")
        
        # Build result lists for RRF fusion
        # For person queries, add BM25 results multiple times to boost weight
        if is_person_query and len(bm25_results) > 0:
            # 3:1 BM25 to Vector ratio for name queries
            result_lists = [bm25_results, bm25_results, bm25_results, vector_results]
            logger.info("Using 3:1 BM25 boost for person query")
        else:
            # Standard 1:1 ratio
            result_lists = [bm25_results, vector_results]
        
        # Fuse results using RRF
        fused = reciprocal_rank_fusion(result_lists, k=60)
        
        # Normalize scores to 0-1
        fused = normalize_scores(fused)
        
        return fused[:limit]
    
    async def query_search(
        self,
        query: str,
        vault: str = "all",
        category: Optional[str] = None,
        person: Optional[str] = None,
        limit: int = 10,
        use_reranking: bool = True,
        use_query_expansion: bool = True
    ) -> List[Dict]:
        """
        Full-featured search: query expansion + hybrid search + reranking.
        
        This is the highest quality search but also slowest.
        """
        import asyncio
        
        # Step 1: Query expansion
        if use_query_expansion:
            queries = await self.reranker.expand_query(query)
            logger.info(f"Query expansion: {queries}")
        else:
            queries = [query]
        
        # Step 2: Run hybrid search for each query
        all_results = []
        for q in queries:
            results = await self.hybrid_search(q, vault, category, person, limit=30)
            all_results.append(results)
        
        # Weight original query higher (add it twice)
        if len(all_results) > 1:
            all_results.insert(0, all_results[0])
        
        # Step 3: Fuse all query results
        fused = reciprocal_rank_fusion(all_results, k=60)
        
        # Step 4: Reranking (optional, adds latency)
        if use_reranking and len(fused) > 0:
            # Score top 30 with reranker
            rerank_scores = await self.reranker.rerank(
                query=query,
                documents=fused[:30],
                content_key="content",
                concurrency=5
            )
            
            # Blend RRF and reranker scores
            fused = position_aware_blend(fused, rerank_scores)
            logger.info(f"Reranked {len(rerank_scores)} documents")
        
        return fused[:limit]
    
    async def search(
        self,
        query: str,
        vault: str = "all",
        category: Optional[str] = None,
        person: Optional[str] = None,
        limit: int = 10,
        mode: str = "hybrid",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict]:
        """
        Unified search interface.
        
        Modes:
        - "vector": Pure vector search (fast, semantic)
        - "bm25": Pure BM25 search (fast, keyword)
        - "hybrid": BM25 + Vector with RRF (recommended)
        - "query": Full pipeline with expansion + reranking (best quality)
        
        Temporal: If date_from/date_to are not provided, they are auto-parsed
        from temporal expressions in the query (e.g., "this week", "last month").
        """
        if mode == "vector":
            results = await self.vector_search(query, vault, category, person, limit, date_from, date_to)
        elif mode == "bm25":
            results = await self.bm25_search(query, vault, person, limit, date_from, date_to)
        elif mode == "query":
            results = await self.query_search(query, vault, category, person, limit)
        else:  # hybrid (default)
            results = await self.hybrid_search(query, vault, category, person, limit, date_from, date_to)
        
        # Format results for API response
        formatted = []
        for r in results:
            formatted.append({
                "score": r.get("score", 0),
                "file_path": r.get("file_path", ""),
                "title": r.get("title", ""),
                "excerpt": r.get("excerpt", r.get("snippet", r.get("content", "")[:300])),
                "date": r.get("date"),
                "people": r.get("people", []),
                "category": r.get("category", ""),
                "vault": r.get("vault", "")
            })
        
        return formatted
    
    async def query_with_llm(
        self,
        question: str,
        vault: str = "all",
        search_mode: str = "hybrid"
    ) -> Tuple[str, List[Dict]]:
        """RAG query with Claude-generated answer."""
        
        # Use hybrid search for context retrieval
        search_results = await self.search(
            query=question,
            vault=vault,
            limit=self.settings.max_context_chunks,
            mode=search_mode
        )
        
        if not search_results:
            return "I couldn't find any relevant information in your notes.", []
        
        # Build context from search results
        context_parts = []
        sources = []
        
        for i, result in enumerate(search_results):
            if any(excl in result["file_path"] for excl in self.settings.excluded_folders_list):
                continue
            
            context_parts.append(f"[Source {i+1}: {result['title']} ({result['date'] or 'undated'})]")
            context_parts.append(result["excerpt"])
            context_parts.append("")
            
            sources.append({
                "file": result["file_path"],
                "title": result["title"],
                "excerpt": result["excerpt"][:100] + "..."
            })
        
        context = "\n".join(context_parts)
        
        # Generate answer using Claude via Clawdbot gateway
        try:
            import httpx
            import os
            
            clawdbot_url = os.getenv("CLAWDBOT_URL", "http://host.docker.internal:18789")
            clawdbot_token = os.getenv("CLAWDBOT_TOKEN")
            
            prompt = f"""Based on the following context from my notes, please answer this question:

Question: {question}

Context:
{context}

Please provide a concise, helpful answer based only on the information provided. If the context doesn't contain enough information to fully answer the question, say so."""

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{clawdbot_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {clawdbot_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "clawdbot",
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                response.raise_for_status()
                data = response.json()
                answer = data["choices"][0]["message"]["content"]
        
        except Exception as e:
            logger.error(f"Error calling Clawdbot: {e}")
            answer = f"Error generating answer: {str(e)}\n\nBased on search results, here are relevant excerpts:\n\n{context}"
        
        return answer, sources
    
    async def get_person_context(self, person: str) -> Dict:
        """Get context for 1:1 with a person."""
        
        results = await self.search(
            query=person,
            vault="work",
            person=person,
            limit=20,
            mode="hybrid"
        )
        
        mention_results = await self.search(
            query=f"meeting with {person}",
            vault="work",
            limit=10,
            mode="hybrid"
        )
        
        all_results = results + mention_results
        seen_files = set()
        unique_results = []
        for r in all_results:
            if r["file_path"] not in seen_files:
                seen_files.add(r["file_path"])
                unique_results.append(r)
        
        topics = []
        actions = []
        dates = []
        
        for r in unique_results[:10]:
            if r["date"]:
                dates.append(r["date"])
            
            content = r.get("excerpt", "")
            if person.lower() in content.lower():
                action_match = re.findall(rf'{person}[:\s]+(.+?)(?:\n|$)', content, re.IGNORECASE)
                actions.extend(action_match[:2])
            
            title = r.get("title", "")
            if title and title not in topics:
                topics.append(title)
        
        recent_meetings = []
        for r in unique_results[:5]:
            recent_meetings.append({
                "date": r["date"],
                "title": r["title"],
                "summary": r["excerpt"][:150] + "..."
            })
        
        return {
            "person": person,
            "meeting_count": len(unique_results),
            "last_meeting": max(dates) if dates else None,
            "recent_topics": topics[:5],
            "open_actions": actions[:5],
            "recent_meetings": recent_meetings
        }
    
    async def get_action_items(self, person: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """Get action items from recent meetings."""
        
        query = f"action items {person}" if person else "action items next steps"
        
        results = await self.search(
            query=query,
            vault="work",
            limit=50,
            mode="hybrid"
        )
        
        actions = []
        
        for r in results:
            content = r.get("excerpt", "")
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith(("-", "•", "*")) and len(line) > 10:
                    if person:
                        if person.lower() in line.lower():
                            actions.append({
                                "item": line.lstrip("-•* "),
                                "date": r["date"],
                                "source": r["title"]
                            })
                    else:
                        if any(word in line.lower() for word in ["will", "to do", "action", "next", "follow"]):
                            actions.append({
                                "item": line.lstrip("-•* "),
                                "date": r["date"],
                                "source": r["title"]
                            })
        
        seen = set()
        unique_actions = []
        for a in actions:
            if a["item"] not in seen:
                seen.add(a["item"])
                unique_actions.append(a)
        
        return unique_actions[:limit]
    
    def index_document_fts(
        self,
        file_path: str,
        title: str,
        content: str,
        vault: str,
        category: str = "",
        people: List[str] = None,
        date: str = None
    ):
        """Add/update a document in the FTS index (called during indexing)."""
        if self.fts_index is None:
            return
        self.fts_index.upsert_document(
            file_path=file_path,
            title=title,
            content=content,
            vault=vault,
            category=category,
            people=people,
            date=date
        )
