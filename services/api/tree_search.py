"""
PageIndex Tree Search

LLM-powered search over PDF documents using hierarchical tree structures.
The LLM reasons over the tree to find relevant sections without embeddings.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import settings
from pageindex_llm import get_pageindex_llm
from pageindex_tree import get_tree_generator

logger = logging.getLogger(__name__)

# Document selection prompt
DOC_SELECTION_PROMPT = """Given this query, which documents are most likely to contain relevant information?

Query: {query}

Available documents:
{doc_summaries}

Return a JSON object with the documents to search (max 3):
{{"docs": ["doc1.pdf", "doc2.pdf"]}}

If no documents seem relevant, return: {{"docs": []}}

Return ONLY valid JSON, no explanation."""

# Tree search prompt
TREE_SEARCH_PROMPT = """Find sections in this document that answer or relate to the query.

Query: {query}

Document: {doc_name}
Structure:
{tree_structure}

Examine the tree and select the most relevant sections. Consider:
- Which sections might contain the answer?
- What topics/keywords in the query match section summaries?
- Prefer leaf nodes when specific, parent nodes when topic is broad

Return a JSON object:
{{
  "node_ids": ["0001", "0003"],
  "reasoning": "Brief explanation of why these sections are relevant"
}}

If no sections are relevant, return: {{"node_ids": [], "reasoning": "No relevant content found"}}

Return ONLY valid JSON, no markdown."""


class PageIndexTreeSearcher:
    """Search PDFs using PageIndex tree reasoning."""
    
    def __init__(self):
        self.llm = get_pageindex_llm()
        self.tree_generator = get_tree_generator()
        self._page_cache: Dict[str, Dict[int, str]] = {}  # pdf_path -> {page_num: text}
    
    async def search(
        self, 
        query: str, 
        vault: str = "all",
        limit: int = 5
    ) -> List[Dict]:
        """
        Search PDFs using tree-based reasoning.
        
        Args:
            query: Search query
            vault: "work", "personal", or "all"
            limit: Max results to return
        
        Returns:
            List of result dicts with doc info and text
        """
        # Load all trees for vault(s)
        vaults = ["work", "personal"] if vault == "all" else [vault]
        all_trees = []
        
        for v in vaults:
            trees = self.tree_generator.list_trees(v)
            all_trees.extend(trees)
        
        if not all_trees:
            logger.info(f"No trees found for vault(s): {vault}")
            return []
        
        # Step 1: LLM selects relevant documents
        selected_docs = await self._select_documents(query, all_trees)
        
        if not selected_docs:
            logger.info(f"No documents selected for query: {query[:50]}...")
            return []
        
        # Step 2: For each selected doc, search its tree
        results = []
        
        for doc_info in selected_docs[:3]:  # Limit to 3 docs
            doc_results = await self._search_document(query, doc_info)
            results.extend(doc_results)
        
        # Sort by relevance (reasoning score could be added later)
        # For now, just return in order
        return results[:limit]
    
    async def _select_documents(
        self, 
        query: str, 
        trees: List[Dict]
    ) -> List[Dict]:
        """Use LLM to select which documents to search."""
        if not trees:
            return []
        
        # Format document summaries for LLM
        doc_summaries = []
        for tree in trees:
            # Get top-level section summaries
            tree_data = self._load_full_tree(tree.get("tree_file", ""))
            if not tree_data:
                continue
            
            sections = tree_data.get("structure", [])
            section_summaries = [
                f"  - {s.get('title', 'Unknown')}: {s.get('summary', '')[:100]}"
                for s in sections[:5]  # First 5 top-level sections
            ]
            
            doc_summaries.append(
                f"- {tree.get('doc_name', 'Unknown')} ({tree.get('total_pages', 0)} pages, {tree.get('vault', '')} vault)\n" +
                "\n".join(section_summaries)
            )
        
        if not doc_summaries:
            return trees[:2]  # Fallback: search first 2 docs
        
        prompt = DOC_SELECTION_PROMPT.format(
            query=query,
            doc_summaries="\n\n".join(doc_summaries)
        )
        
        try:
            response = await self.llm.call(prompt, max_tokens=256)
            selected = self._parse_doc_selection(response)
            
            # Map selected names back to full tree info
            result = []
            for tree in trees:
                if tree.get("doc_name", "") in selected:
                    result.append(tree)
            
            return result if result else trees[:2]
            
        except Exception as e:
            logger.warning(f"Document selection failed: {e}. Searching all docs.")
            return trees[:2]
    
    def _parse_doc_selection(self, response: str) -> List[str]:
        """Parse LLM response for document selection."""
        text = response.strip()
        
        # Extract JSON
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            text = text[start:end]
        
        try:
            data = json.loads(text)
            return data.get("docs", [])
        except json.JSONDecodeError:
            logger.warning(f"Could not parse doc selection: {response[:200]}")
            return []
    
    async def _search_document(
        self, 
        query: str, 
        doc_info: Dict
    ) -> List[Dict]:
        """Search within a single document using its tree."""
        tree_file = doc_info.get("tree_file", "")
        tree_data = self._load_full_tree(tree_file)
        
        if not tree_data:
            return []
        
        # Format tree for LLM
        tree_structure = self._format_tree_for_search(tree_data.get("structure", []))
        
        prompt = TREE_SEARCH_PROMPT.format(
            query=query,
            doc_name=tree_data.get("doc_name", "Unknown"),
            tree_structure=tree_structure
        )
        
        try:
            response = await self.llm.call(prompt, max_tokens=512)
            search_result = self._parse_tree_search(response)
            
            if not search_result.get("node_ids"):
                return []
            
            # Get text for selected nodes
            results = []
            pdf_path = tree_data.get("pdf_path", "")
            
            for node_id in search_result["node_ids"]:
                node = self._find_node_by_id(tree_data.get("structure", []), node_id)
                if not node:
                    continue
                
                # Get page text for this node
                text = await self._get_node_text(
                    pdf_path,
                    node.get("start_page", 1),
                    node.get("end_page", 1)
                )
                
                results.append({
                    "doc_name": tree_data.get("doc_name", ""),
                    "pdf_path": pdf_path,
                    "vault": tree_data.get("vault", ""),
                    "section": node.get("title", ""),
                    "summary": node.get("summary", ""),
                    "pages": f"{node.get('start_page', 1)}-{node.get('end_page', 1)}",
                    "start_page": node.get("start_page", 1),
                    "end_page": node.get("end_page", 1),
                    "text": text[:3000],  # Truncate for response size
                    "reasoning": search_result.get("reasoning", "")
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Tree search failed for {doc_info.get('doc_name')}: {e}")
            return []
    
    def _load_full_tree(self, tree_file: str) -> Optional[Dict]:
        """Load full tree data from file."""
        if not tree_file:
            return None
        
        try:
            with open(tree_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tree {tree_file}: {e}")
            return None
    
    def _format_tree_for_search(self, structure: List[Dict], indent: int = 0) -> str:
        """Format tree structure for LLM prompt."""
        lines = []
        prefix = "  " * indent
        
        for node in structure:
            node_line = (
                f"{prefix}[{node.get('node_id', '????')}] {node.get('title', 'Unknown')} "
                f"(pages {node.get('start_page', '?')}-{node.get('end_page', '?')})"
            )
            if node.get('summary'):
                node_line += f"\n{prefix}    Summary: {node.get('summary', '')}"
            lines.append(node_line)
            
            # Recurse for children
            if node.get("children"):
                child_text = self._format_tree_for_search(node["children"], indent + 1)
                lines.append(child_text)
        
        return "\n".join(lines)
    
    def _parse_tree_search(self, response: str) -> Dict:
        """Parse LLM response for tree search."""
        text = response.strip()
        
        # Extract JSON
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            text = text[start:end]
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse tree search: {response[:200]}")
            return {"node_ids": [], "reasoning": "Parse error"}
    
    def _find_node_by_id(self, structure: List[Dict], node_id: str) -> Optional[Dict]:
        """Find a node in the tree by its ID."""
        for node in structure:
            if node.get("node_id") == node_id:
                return node
            if node.get("children"):
                found = self._find_node_by_id(node["children"], node_id)
                if found:
                    return found
        return None
    
    async def _get_node_text(
        self, 
        pdf_path: str, 
        start_page: int, 
        end_page: int
    ) -> str:
        """Get text for pages in a node's range."""
        if not pdf_path:
            return ""
        
        # Use cached pages if available
        if pdf_path not in self._page_cache:
            self._page_cache[pdf_path] = await self._extract_pdf_pages(pdf_path)
        
        pages = self._page_cache[pdf_path]
        
        text_parts = []
        for page_num in range(start_page, end_page + 1):
            if page_num in pages:
                text_parts.append(f"[Page {page_num}]\n{pages[page_num]}")
        
        return "\n\n".join(text_parts)
    
    async def _extract_pdf_pages(self, pdf_path: str) -> Dict[int, str]:
        """Extract all pages from a PDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF not installed")
            return {}
        
        pages = {}
        try:
            doc = fitz.open(pdf_path)
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text")
                if text and text.strip():
                    pages[page_num] = text.strip()
            doc.close()
        except Exception as e:
            logger.error(f"Error extracting PDF {pdf_path}: {e}")
        
        return pages
    
    def clear_cache(self):
        """Clear the page cache."""
        self._page_cache.clear()


# Singleton instance
_searcher_instance: Optional[PageIndexTreeSearcher] = None


def get_tree_searcher() -> PageIndexTreeSearcher:
    """Get or create the tree searcher."""
    global _searcher_instance
    if _searcher_instance is None:
        _searcher_instance = PageIndexTreeSearcher()
    return _searcher_instance
