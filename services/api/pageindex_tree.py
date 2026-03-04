"""
PageIndex Tree Generator

Generate hierarchical tree structures from PDF documents using LLM reasoning.
Trees are stored as JSON files for efficient retrieval.
"""

import json
import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from config import settings
from pageindex_llm import get_pageindex_llm

logger = logging.getLogger(__name__)

# Tree generation prompt
TREE_GENERATION_PROMPT = """Analyze this document and create a hierarchical table of contents structure.

Document: {doc_name}
Total Pages: {total_pages}

Content (page numbers indicated):
{content}

Create a JSON structure representing the document's logical organization. Each node should have:
- "title": Section/chapter title
- "start_page": First page of this section (1-indexed)
- "end_page": Last page of this section (1-indexed)
- "summary": 1-2 sentence summary of what this section covers
- "node_id": Unique 4-digit ID (e.g., "0001", "0002")
- "children": Array of child sections (if any)

Guidelines:
- Focus on logical document structure (chapters, sections, major topics)
- Leaf nodes should be reasonably sized (not too granular)
- Summaries should be informative enough to determine relevance to queries
- If the document has no clear structure, create 2-4 thematic sections
- Ensure page ranges don't overlap and cover the entire document

Return ONLY valid JSON (no markdown, no explanation). Start with [ and end with ]."""


class PageIndexTreeGenerator:
    """Generate and manage PageIndex tree structures for PDFs."""
    
    def __init__(self, tree_dir: Optional[str] = None):
        self.tree_dir = Path(tree_dir or settings.pageindex_tree_dir)
        self.llm = get_pageindex_llm()
    
    def _get_tree_path(self, doc_hash: str, vault: str) -> Path:
        """Get the path for a tree JSON file."""
        vault_dir = self.tree_dir / vault
        vault_dir.mkdir(parents=True, exist_ok=True)
        return vault_dir / f"{doc_hash}.json"
    
    def _compute_doc_hash(self, pdf_path: str) -> str:
        """Compute hash for PDF file (MD5 of path + mtime for change detection)."""
        path = Path(pdf_path)
        try:
            mtime = path.stat().st_mtime
            hash_input = f"{pdf_path}:{mtime}"
        except:
            hash_input = pdf_path
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def tree_exists(self, pdf_path: str, vault: str) -> bool:
        """Check if a tree already exists for this PDF."""
        doc_hash = self._compute_doc_hash(pdf_path)
        tree_path = self._get_tree_path(doc_hash, vault)
        return tree_path.exists()
    
    def load_tree(self, pdf_path: str, vault: str) -> Optional[Dict]:
        """Load existing tree for a PDF."""
        doc_hash = self._compute_doc_hash(pdf_path)
        tree_path = self._get_tree_path(doc_hash, vault)
        
        if not tree_path.exists():
            return None
        
        try:
            with open(tree_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tree {tree_path}: {e}")
            return None
    
    def save_tree(self, tree_data: Dict, pdf_path: str, vault: str) -> Path:
        """Save tree to JSON file."""
        doc_hash = self._compute_doc_hash(pdf_path)
        tree_path = self._get_tree_path(doc_hash, vault)
        
        with open(tree_path, 'w') as f:
            json.dump(tree_data, f, indent=2)
        
        logger.info(f"Saved tree to {tree_path}")
        return tree_path
    
    async def generate_tree(
        self, 
        pages: List[Tuple[int, str]], 
        doc_name: str,
        pdf_path: str,
        vault: str
    ) -> Dict:
        """
        Generate hierarchical tree structure from PDF pages using LLM.
        
        Args:
            pages: List of (page_number, text) tuples
            doc_name: Name of the document
            pdf_path: Full path to PDF file
            vault: Vault name ("work" or "personal")
        
        Returns:
            Tree structure dict with metadata
        """
        if not pages:
            return self._create_fallback_tree(doc_name, pdf_path, vault)
        
        # Prepare content for LLM (with page markers)
        content_parts = []
        total_chars = 0
        max_chars = 50000  # Truncate to fit context
        
        for page_num, text in pages:
            page_text = f"\n[Page {page_num}]\n{text.strip()}"
            if total_chars + len(page_text) > max_chars:
                # Add truncation notice
                content_parts.append(f"\n[... pages {page_num}-{pages[-1][0]} truncated for length ...]")
                break
            content_parts.append(page_text)
            total_chars += len(page_text)
        
        content = "\n".join(content_parts)
        
        # Build prompt
        prompt = TREE_GENERATION_PROMPT.format(
            doc_name=doc_name,
            total_pages=len(pages),
            content=content
        )
        
        try:
            # Call LLM
            response = await self.llm.call(prompt, max_tokens=4096)
            
            # Parse response
            structure = self._parse_tree_response(response)
            
            # Build full tree document
            tree_data = {
                "doc_name": doc_name,
                "pdf_path": pdf_path,
                "vault": vault,
                "total_pages": len(pages),
                "generated_at": datetime.utcnow().isoformat(),
                "structure": structure
            }
            
            # Save tree
            self.save_tree(tree_data, pdf_path, vault)
            
            return tree_data
            
        except Exception as e:
            logger.error(f"Tree generation failed for {doc_name}: {e}")
            return self._create_fallback_tree(doc_name, pdf_path, vault, len(pages))
    
    def _parse_tree_response(self, response: str) -> List[Dict]:
        """Parse LLM response into tree structure."""
        # Clean up response - extract JSON
        text = response.strip()
        
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        # Find JSON array boundaries
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0 and end > start:
            text = text[start:end]
        
        try:
            structure = json.loads(text)
            if isinstance(structure, list):
                return structure
            elif isinstance(structure, dict):
                return [structure]
            else:
                raise ValueError("Unexpected JSON structure")
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}. Response: {text[:500]}")
            raise ValueError(f"Could not parse tree structure: {e}")
    
    def _create_fallback_tree(
        self, 
        doc_name: str, 
        pdf_path: str, 
        vault: str,
        total_pages: int = 1
    ) -> Dict:
        """Create a simple fallback tree when LLM fails."""
        logger.warning(f"Using fallback tree for {doc_name}")
        
        tree_data = {
            "doc_name": doc_name,
            "pdf_path": pdf_path,
            "vault": vault,
            "total_pages": total_pages,
            "generated_at": datetime.utcnow().isoformat(),
            "fallback": True,
            "structure": [{
                "title": doc_name,
                "start_page": 1,
                "end_page": total_pages,
                "summary": "Full document content (no structure extracted)",
                "node_id": "0000",
                "children": []
            }]
        }
        
        self.save_tree(tree_data, pdf_path, vault)
        return tree_data
    
    def list_trees(self, vault: Optional[str] = None) -> List[Dict]:
        """List all generated trees."""
        trees = []
        
        vaults = [vault] if vault else ["work", "personal"]
        
        for v in vaults:
            vault_dir = self.tree_dir / v
            if not vault_dir.exists():
                continue
            
            for tree_file in vault_dir.glob("*.json"):
                try:
                    with open(tree_file, 'r') as f:
                        data = json.load(f)
                        trees.append({
                            "doc_name": data.get("doc_name", "Unknown"),
                            "pdf_path": data.get("pdf_path", ""),
                            "vault": data.get("vault", v),
                            "total_pages": data.get("total_pages", 0),
                            "generated_at": data.get("generated_at", ""),
                            "tree_file": str(tree_file),
                            "node_count": self._count_nodes(data.get("structure", []))
                        })
                except Exception as e:
                    logger.warning(f"Error reading tree {tree_file}: {e}")
        
        return trees
    
    def _count_nodes(self, structure: List[Dict]) -> int:
        """Count total nodes in a tree structure."""
        count = 0
        for node in structure:
            count += 1
            if "children" in node and node["children"]:
                count += self._count_nodes(node["children"])
        return count
    
    def delete_tree(self, pdf_path: str, vault: str) -> bool:
        """Delete tree for a PDF."""
        doc_hash = self._compute_doc_hash(pdf_path)
        tree_path = self._get_tree_path(doc_hash, vault)
        
        if tree_path.exists():
            tree_path.unlink()
            logger.info(f"Deleted tree {tree_path}")
            return True
        return False


# Singleton instance
_generator_instance: Optional[PageIndexTreeGenerator] = None


def get_tree_generator() -> PageIndexTreeGenerator:
    """Get or create the tree generator."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = PageIndexTreeGenerator()
    return _generator_instance
