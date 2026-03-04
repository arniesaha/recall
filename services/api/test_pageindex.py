#!/usr/bin/env python3
"""
Test script for PageIndex integration.

Usage:
    python test_pageindex.py [--generate] [--search "query"]
    
Examples:
    # Check health
    python test_pageindex.py
    
    # Generate tree for a specific PDF
    python test_pageindex.py --generate "/data/pdfs/work/Metastore-Project Bedrock_ Platform Maturity & Enterprise Readiness Initiative-100126-202541.pdf"
    
    # Search via tree
    python test_pageindex.py --search "What is Project Bedrock?"
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from pageindex_llm import get_pageindex_llm
from pageindex_tree import get_tree_generator
from tree_search import get_tree_searcher


async def test_health():
    """Test LLM health."""
    print("=== PageIndex Health Check ===")
    print(f"PageIndex enabled: {settings.pageindex_enabled}")
    print(f"LLM provider: {settings.pageindex_llm_provider}")
    print(f"Max URL: {settings.max_gateway_url}")
    print(f"Max token configured: {'yes' if settings.max_gateway_token else 'NO'}")
    print(f"Tree dir: {settings.pageindex_tree_dir}")
    
    llm = get_pageindex_llm()
    health = await llm.health_check()
    print(f"\nLLM Health: {json.dumps(health, indent=2)}")
    
    return health


async def test_generate(pdf_path: str, vault: str = "work"):
    """Test tree generation."""
    print(f"\n=== Generating Tree for {Path(pdf_path).name} ===")
    
    # Extract PDF pages
    try:
        import fitz
        doc = fitz.open(pdf_path)
        pages = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            if text and text.strip():
                pages.append((page_num, text.strip()))
        doc.close()
        print(f"Extracted {len(pages)} pages")
    except ImportError:
        print("ERROR: PyMuPDF not installed")
        return None
    except Exception as e:
        print(f"ERROR extracting PDF: {e}")
        return None
    
    # Generate tree
    generator = get_tree_generator()
    
    print("Calling LLM to generate tree structure...")
    tree_data = await generator.generate_tree(
        pages=pages,
        doc_name=Path(pdf_path).name,
        pdf_path=pdf_path,
        vault=vault
    )
    
    print(f"\nTree generated successfully!")
    print(f"Document: {tree_data.get('doc_name')}")
    print(f"Total pages: {tree_data.get('total_pages')}")
    print(f"Generated at: {tree_data.get('generated_at')}")
    
    print("\nStructure:")
    print(json.dumps(tree_data.get("structure", []), indent=2)[:2000])
    
    return tree_data


async def test_search(query: str, vault: str = "all"):
    """Test tree search."""
    print(f"\n=== Tree Search ===")
    print(f"Query: {query}")
    print(f"Vault: {vault}")
    
    searcher = get_tree_searcher()
    
    print("\nSearching...")
    results = await searcher.search(query=query, vault=vault, limit=3)
    
    if not results:
        print("No results found")
        return []
    
    print(f"\nFound {len(results)} results:")
    for i, r in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print(f"Document: {r.get('doc_name')}")
        print(f"Section: {r.get('section')}")
        print(f"Pages: {r.get('pages')}")
        print(f"Summary: {r.get('summary')}")
        print(f"Reasoning: {r.get('reasoning')}")
        print(f"Text preview: {r.get('text', '')[:200]}...")
    
    return results


async def list_trees():
    """List all generated trees."""
    print("\n=== Generated Trees ===")
    generator = get_tree_generator()
    trees = generator.list_trees()
    
    if not trees:
        print("No trees generated yet")
        return []
    
    for t in trees:
        print(f"\n- {t.get('doc_name')}")
        print(f"  Vault: {t.get('vault')}")
        print(f"  Pages: {t.get('total_pages')}")
        print(f"  Nodes: {t.get('node_count')}")
        print(f"  Generated: {t.get('generated_at')}")
    
    return trees


async def main():
    parser = argparse.ArgumentParser(description="Test PageIndex integration")
    parser.add_argument("--generate", metavar="PDF_PATH", help="Generate tree for a PDF")
    parser.add_argument("--search", metavar="QUERY", help="Search using tree")
    parser.add_argument("--vault", default="work", help="Vault to use (work/personal/all)")
    parser.add_argument("--list", action="store_true", help="List generated trees")
    
    args = parser.parse_args()
    
    # Always show health first
    await test_health()
    
    if args.list:
        await list_trees()
    
    if args.generate:
        await test_generate(args.generate, args.vault)
    
    if args.search:
        await test_search(args.search, args.vault)
    
    if not any([args.generate, args.search, args.list]):
        await list_trees()


if __name__ == "__main__":
    asyncio.run(main())
