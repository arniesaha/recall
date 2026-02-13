"""
Indexer module for note-rag
Handles document chunking, embedding, and storage in LanceDB

Supports:
- Markdown files (from Obsidian vaults)
- PDF files (with page-aware chunking)

Non-blocking version: Uses thread pool for CPU work and yields to event loop
"""

import os
import re
import logging
import hashlib
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import httpx
import frontmatter
import lancedb
from lancedb.pydantic import LanceModel, Vector

# PDF support
try:
    import fitz  # PyMuPDF
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False
    fitz = None

from config import Settings

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound operations (file I/O, hashing, chunking)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="indexer")


class DocumentChunk(LanceModel):
    """Schema for document chunks in LanceDB."""
    id: str                      # Unique chunk ID (file_hash + chunk_index)
    vector: Vector(768)          # nomic-embed-text dimension
    file_path: str
    file_hash: str               # MD5 of file content (for change detection)
    mtime: float                 # File modification time (Unix timestamp) for fast change detection
    title: str
    category: str
    people: List[str]
    projects: List[str]
    date: Optional[str]
    vault: str
    chunk_index: int
    content: str
    source_type: str = "markdown"  # "markdown" or "pdf"
    page_number: Optional[int] = None  # For PDFs: page number (1-indexed)


class Indexer:
    def __init__(self, db: lancedb.DBConnection, settings: Settings, fts_index=None):
        self.db = db
        self.settings = settings
        self.embedding_cache = {}
        self._cancel_requested = False
        self.fts_index = fts_index  # Optional FTS index for hybrid search
    
    def request_cancel(self):
        """Request cancellation of current indexing job."""
        self._cancel_requested = True
    
    async def init_tables(self):
        """Initialize LanceDB tables if they don't exist."""
        existing_tables = self.db.table_names()
        
        if "work" not in existing_tables:
            logger.info("Creating 'work' table")
            self.db.create_table("work", schema=DocumentChunk)
        
        if "personal" not in existing_tables:
            logger.info("Creating 'personal' table")
            self.db.create_table("personal", schema=DocumentChunk)
        
        logger.info("Tables initialized")
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding from Ollama."""
        # Check cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]
        
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
            embedding = data["embeddings"][0]
        
        # Cache it
        self.embedding_cache[cache_key] = embedding
        return embedding
    
    def _chunk_document_sync(self, content: str, metadata: dict) -> List[Dict]:
        """Split document into chunks with overlap. (CPU-bound, runs in thread pool)"""
        chunks = []
        
        # Simple chunking by paragraphs/sections
        # Split on double newlines or headers
        sections = re.split(r'\n\n+|(?=^###?\s)', content, flags=re.MULTILINE)
        
        current_chunk = ""
        chunk_index = 0
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            # If adding this section exceeds chunk size, save current and start new
            if len(current_chunk) + len(section) > self.settings.chunk_size * 4:  # Approx chars
                if current_chunk:
                    chunks.append({
                        "chunk_index": chunk_index,
                        "content": current_chunk.strip(),
                        **metadata
                    })
                    chunk_index += 1
                    # Keep overlap
                    overlap_start = max(0, len(current_chunk) - self.settings.chunk_overlap * 4)
                    current_chunk = current_chunk[overlap_start:] + "\n\n" + section
                else:
                    current_chunk = section
            else:
                current_chunk += "\n\n" + section if current_chunk else section
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "content": current_chunk.strip(),
                **metadata
            })
        
        return chunks
    
    async def chunk_document(self, content: str, metadata: dict) -> List[Dict]:
        """Split document into chunks with overlap. Non-blocking wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, 
            self._chunk_document_sync, 
            content, 
            metadata
        )
    
    def _extract_metadata_sync(self, file_path: Path, content: str) -> Dict:
        """Extract metadata from file. (CPU-bound, runs in thread pool)"""
        # Parse frontmatter
        try:
            post = frontmatter.loads(content)
            fm = post.metadata
            body = post.content
        except:
            fm = {}
            body = content
        
        # Determine vault
        path_str = str(file_path)
        if self.settings.vault_work_path in path_str:
            vault = "work"
        elif self.settings.vault_personal_path in path_str:
            vault = "personal"
        else:
            vault = "unknown"
        
        # Extract category from path
        relative_path = file_path.relative_to(
            self.settings.vault_work_path if vault == "work" 
            else self.settings.vault_personal_path
        )
        category = relative_path.parts[0] if relative_path.parts else "other"
        
        # Get title
        title = fm.get("title", file_path.stem)
        
        # Get date
        date = fm.get("date")
        if date:
            date = str(date)
        else:
            # Try to extract from filename
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_path.name)
            if date_match:
                date = date_match.group(1)
        
        # Get people and projects
        people = fm.get("people", [])
        if isinstance(people, str):
            people = [p.strip() for p in people.split(",")]
        
        projects = fm.get("projects", [])
        if isinstance(projects, str):
            projects = [p.strip() for p in projects.split(",")]
        
        return {
            "file_path": str(file_path),
            "file_hash": hashlib.md5(content.encode()).hexdigest(),
            "title": title,
            "category": category,
            "people": people,
            "projects": projects,
            "date": date,
            "vault": vault,
            "body": body
        }
    
    async def extract_metadata(self, file_path: Path, content: str) -> Dict:
        """Extract metadata from file. Non-blocking wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            self._extract_metadata_sync,
            file_path,
            content
        )
    
    def is_excluded(self, file_path: Path) -> bool:
        """Check if file should be excluded."""
        path_str = str(file_path)
        for excluded in self.settings.excluded_folders_list:
            if excluded in path_str:
                return True
        return False
    
    def _read_file_sync(self, file_path: Path) -> Optional[str]:
        """Read file content. (I/O-bound, runs in thread pool)"""
        try:
            return file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None
    
    async def read_file(self, file_path: Path) -> Optional[str]:
        """Read file content. Non-blocking wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._read_file_sync, file_path)
    
    # ==================== PDF SUPPORT ====================
    
    def _extract_pdf_pages_sync(self, file_path: Path) -> List[Tuple[int, str]]:
        """
        Extract text from each page of a PDF. (CPU-bound, runs in thread pool)
        Returns list of (page_number, text) tuples. Page numbers are 1-indexed.
        """
        if not PDF_ENABLED or fitz is None:
            logger.warning("PyMuPDF not installed, skipping PDF")
            return []
        
        pages = []
        try:
            doc = fitz.open(str(file_path))
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text")
                if text and text.strip():
                    pages.append((page_num, text.strip()))
            doc.close()
        except Exception as e:
            logger.error(f"Error extracting PDF {file_path}: {e}")
        
        return pages
    
    async def extract_pdf_pages(self, file_path: Path) -> List[Tuple[int, str]]:
        """Extract text from PDF pages. Non-blocking wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._extract_pdf_pages_sync, file_path)
    
    def _list_pdf_files_sync(self, pdf_path: Path) -> List[Path]:
        """List all PDF files in path. (I/O-bound, runs in thread pool)"""
        if not pdf_path.exists():
            return []
        files = []
        for pdf_file in pdf_path.rglob("*.pdf"):
            if not pdf_file.name.startswith("."):
                files.append(pdf_file)
        return files
    
    async def list_pdf_files(self, pdf_path: Path) -> List[Path]:
        """List all PDF files in path. Non-blocking wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._list_pdf_files_sync, pdf_path)
    
    def _extract_pdf_metadata_sync(self, file_path: Path, vault: str) -> Dict:
        """Extract metadata from PDF file path. (CPU-bound, runs in thread pool)"""
        # Get title from filename (remove extension)
        title = file_path.stem
        
        # Clean up title (remove date prefixes, etc.)
        # Common patterns: "Document-MMDDYY-HHMMSS.pdf" or "2026-01-15 Meeting Notes.pdf"
        title = re.sub(r'-?\d{6}-\d{6}$', '', title)  # Remove timestamp suffix
        title = re.sub(r'^\d{4}-\d{2}-\d{2}\s*', '', title)  # Remove date prefix
        
        # Extract category from parent folder
        pdf_base = Path(self.settings.pdf_work_path if vault == "work" else self.settings.pdf_personal_path)
        try:
            relative_path = file_path.relative_to(pdf_base)
            category = relative_path.parts[0] if len(relative_path.parts) > 1 else "documents"
        except ValueError:
            category = "documents"
        
        # Try to extract date from filename
        date = None
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_path.name)
        if date_match:
            date = date_match.group(1)
        else:
            # Try MMDDYY format
            date_match = re.search(r'(\d{2})(\d{2})(\d{2})', file_path.name)
            if date_match:
                mm, dd, yy = date_match.groups()
                date = f"20{yy}-{mm}-{dd}"
        
        # Calculate file hash for change detection
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
        except:
            file_hash = hashlib.md5(str(file_path).encode()).hexdigest()
        
        return {
            "file_path": str(file_path),
            "file_hash": file_hash,
            "title": title or file_path.stem,
            "category": category,
            "people": [],  # Could extract from PDF metadata if available
            "projects": [],
            "date": date,
            "vault": vault,
            "source_type": "pdf"
        }
    
    async def extract_pdf_metadata(self, file_path: Path, vault: str) -> Dict:
        """Extract metadata from PDF. Non-blocking wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._extract_pdf_metadata_sync, file_path, vault)
    
    def _chunk_pdf_pages_sync(self, pages: List[Tuple[int, str]], metadata: dict) -> List[Dict]:
        """
        Chunk PDF content with page awareness. (CPU-bound, runs in thread pool)
        
        Strategy: Keep chunks within page boundaries when possible, but allow
        multi-page chunks for continuity. Each chunk records its starting page.
        """
        chunks = []
        current_chunk = ""
        current_page = 1
        chunk_index = 0
        
        for page_num, page_text in pages:
            # If this page would make chunk too big, save current and start new
            if current_chunk and len(current_chunk) + len(page_text) > self.settings.chunk_size * 4:
                chunks.append({
                    "chunk_index": chunk_index,
                    "content": current_chunk.strip(),
                    "page_number": current_page,
                    **metadata
                })
                chunk_index += 1
                # Start new chunk with overlap from previous
                overlap_chars = min(self.settings.chunk_overlap * 4, len(current_chunk))
                current_chunk = current_chunk[-overlap_chars:] + "\n\n" + page_text
                current_page = page_num
            else:
                if not current_chunk:
                    current_page = page_num
                current_chunk += "\n\n" + page_text if current_chunk else page_text
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "content": current_chunk.strip(),
                "page_number": current_page,
                **metadata
            })
        
        return chunks
    
    async def chunk_pdf_pages(self, pages: List[Tuple[int, str]], metadata: dict) -> List[Dict]:
        """Chunk PDF with page awareness. Non-blocking wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._chunk_pdf_pages_sync, pages, metadata)
    
    async def index_pdf_file(self, file_path: Path, table_name: str, mtime: Optional[float] = None) -> int:
        """Index a single PDF file."""
        if not PDF_ENABLED:
            logger.warning("PDF support not available (PyMuPDF not installed)")
            return 0
        
        if self.is_excluded(file_path):
            logger.debug(f"Skipping excluded PDF: {file_path}")
            return 0
        
        # Extract text from all pages
        pages = await self.extract_pdf_pages(file_path)
        if not pages:
            logger.debug(f"Skipping empty/unreadable PDF: {file_path}")
            return 0
        
        # Get mtime if not provided
        if mtime is None:
            try:
                mtime = file_path.stat().st_mtime
            except:
                mtime = 0.0
        
        # Extract metadata
        metadata = await self.extract_pdf_metadata(file_path, table_name)
        
        # Chunk with page awareness
        chunks = await self.chunk_pdf_pages(pages, metadata)
        
        if not chunks:
            return 0
        
        table = self.db.open_table(table_name)
        
        # Generate embeddings and prepare records
        records = []
        for chunk in chunks:
            if self._cancel_requested:
                logger.info("PDF indexing cancelled")
                return len(records)
            
            try:
                embedding = await self.get_embedding(chunk["content"][:8000])
                
                chunk_id = f"{chunk['file_hash']}_{chunk['chunk_index']}"
                
                records.append(DocumentChunk(
                    id=chunk_id,
                    vector=embedding,
                    file_path=chunk["file_path"],
                    file_hash=chunk["file_hash"],
                    mtime=mtime,
                    title=chunk["title"],
                    category=chunk["category"],
                    people=chunk.get("people", []),
                    projects=chunk.get("projects", []),
                    date=chunk.get("date"),
                    vault=chunk["vault"],
                    chunk_index=chunk["chunk_index"],
                    content=chunk["content"],
                    source_type="pdf",
                    page_number=chunk.get("page_number")
                ))
            except Exception as e:
                logger.error(f"Error embedding PDF chunk {chunk['chunk_index']} of {file_path}: {e}")
        
        if records:
            # Delete existing chunks for this file
            try:
                table.delete(f'file_hash = "{metadata["file_hash"]}"')
            except:
                pass
            
            # Add new records
            table.add([r.dict() for r in records])
            logger.info(f"Indexed {len(records)} chunks from PDF: {file_path.name}")
            
            # Also index to FTS for hybrid search
            if self.fts_index:
                try:
                    full_text = "\n\n".join([p[1] for p in pages])
                    self.fts_index.upsert_document(
                        file_path=str(file_path),
                        title=metadata.get("title", ""),
                        content=full_text,
                        vault=table_name,
                        category=metadata.get("category", ""),
                        people=metadata.get("people", []),
                        date=metadata.get("date")
                    )
                except Exception as e:
                    logger.warning(f"FTS indexing failed for PDF {file_path}: {e}")
        
        return len(records)
    
    # ==================== END PDF SUPPORT ====================
    
    async def index_file(self, file_path: Path, table_name: str, mtime: Optional[float] = None) -> int:
        """Index a single file."""
        if self.is_excluded(file_path):
            logger.debug(f"Skipping excluded file: {file_path}")
            return 0
        
        content = await self.read_file(file_path)
        if content is None or len(content.strip()) < 50:
            logger.debug(f"Skipping short/unreadable file: {file_path}")
            return 0
        
        # Get mtime if not provided
        if mtime is None:
            try:
                mtime = file_path.stat().st_mtime
            except:
                mtime = 0.0
        
        metadata = await self.extract_metadata(file_path, content)
        body = metadata.pop("body")
        chunks = await self.chunk_document(body, metadata)
        
        if not chunks:
            return 0
        
        table = self.db.open_table(table_name)
        
        # Generate embeddings and prepare records
        records = []
        for chunk in chunks:
            # Check for cancellation
            if self._cancel_requested:
                logger.info("Indexing cancelled")
                return len(records)
            
            try:
                embedding = await self.get_embedding(chunk["content"][:8000])  # Limit input
                
                chunk_id = f"{chunk['file_hash']}_{chunk['chunk_index']}"
                
                records.append(DocumentChunk(
                    id=chunk_id,
                    vector=embedding,
                    file_path=chunk["file_path"],
                    file_hash=chunk["file_hash"],
                    mtime=mtime,
                    title=chunk["title"],
                    category=chunk["category"],
                    people=chunk["people"],
                    projects=chunk["projects"],
                    date=chunk["date"],
                    vault=chunk["vault"],
                    chunk_index=chunk["chunk_index"],
                    content=chunk["content"],
                    source_type="markdown",
                    page_number=None
                ))
            except Exception as e:
                logger.error(f"Error embedding chunk {chunk['chunk_index']} of {file_path}: {e}")
        
        if records:
            # Delete existing chunks for this file (by file_hash prefix)
            try:
                table.delete(f'file_hash = "{metadata["file_hash"]}"')
            except:
                pass  # Table might be empty
            
            # Add new records
            table.add([r.dict() for r in records])
            logger.info(f"Indexed {len(records)} chunks from {file_path.name}")
            
            # Also index to FTS for hybrid search
            if self.fts_index:
                try:
                    self.fts_index.upsert_document(
                        file_path=str(file_path),
                        title=metadata.get("title", ""),
                        content=body,  # Full document content
                        vault=table_name,
                        category=metadata.get("category", ""),
                        people=metadata.get("people", []),
                        date=metadata.get("date")
                    )
                except Exception as e:
                    logger.warning(f"FTS indexing failed for {file_path}: {e}")
        
        return len(records)
    
    def _list_markdown_files_sync(self, vault_path: Path) -> List[Path]:
        """List all markdown files in vault. (I/O-bound, runs in thread pool)"""
        files = []
        for md_file in vault_path.rglob("*.md"):
            if not md_file.name.startswith("."):
                files.append(md_file)
        return files
    
    async def list_markdown_files(self, vault_path: Path) -> List[Path]:
        """List all markdown files in vault. Non-blocking wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            self._list_markdown_files_sync,
            vault_path
        )
    
    async def full_reindex(self, vault: str = "all") -> int:
        """Full reindex of vault(s). Non-blocking. Includes both Markdown and PDFs."""
        self._cancel_requested = False
        total_indexed = 0
        
        vaults_to_index = []
        if vault in ["all", "work"]:
            vaults_to_index.append(("work", Path(self.settings.vault_work_path), Path(self.settings.pdf_work_path)))
        if vault in ["all", "personal"]:
            vaults_to_index.append(("personal", Path(self.settings.vault_personal_path), Path(self.settings.pdf_personal_path)))
        
        for table_name, vault_path, pdf_path in vaults_to_index:
            if self._cancel_requested:
                break
                
            logger.info(f"Full reindex of {table_name} vault...")
            
            # Clear table
            try:
                table = self.db.open_table(table_name)
                # LanceDB doesn't have truncate, so we delete all
                table.delete("id IS NOT NULL")
            except:
                pass
            
            # === INDEX MARKDOWN FILES ===
            md_files = await self.list_markdown_files(vault_path)
            total_md = len(md_files)
            logger.info(f"Found {total_md} Markdown files to index in {table_name}")
            
            for i, md_file in enumerate(md_files):
                if self._cancel_requested:
                    logger.info("Indexing cancelled by request")
                    break
                
                count = await self.index_file(md_file, table_name)
                total_indexed += count
                
                if i % 10 == 0:
                    await asyncio.sleep(0)
                    if i > 0 and i % 100 == 0:
                        logger.info(f"Markdown progress: {i}/{total_md} files ({table_name})")
            
            # === INDEX PDF FILES ===
            if self.settings.pdf_enabled and PDF_ENABLED:
                pdf_files = await self.list_pdf_files(pdf_path)
                total_pdfs = len(pdf_files)
                if total_pdfs > 0:
                    logger.info(f"Found {total_pdfs} PDF files to index in {table_name}")
                    
                    for i, pdf_file in enumerate(pdf_files):
                        if self._cancel_requested:
                            logger.info("PDF indexing cancelled by request")
                            break
                        
                        count = await self.index_pdf_file(pdf_file, table_name)
                        total_indexed += count
                        
                        if i % 5 == 0:
                            await asyncio.sleep(0)
                            if i > 0:
                                logger.info(f"PDF progress: {i}/{total_pdfs} files ({table_name})")
        
        logger.info(f"Full reindex complete: {total_indexed} chunks (Markdown + PDF)")
        return total_indexed
    
    async def incremental_index(self, vault: str = "all") -> int:
        """
        Incremental index (only new/modified/deleted files). Non-blocking.
        Handles both Markdown and PDF files.
        
        Uses two-tier change detection:
        1. Fast tier: mtime check (filesystem stat) - skip if unchanged
        2. Accurate tier: content hash - only for files where mtime changed
        
        Also handles deletions: removes index entries for files that no longer exist.
        """
        self._cancel_requested = False
        total_indexed = 0
        total_deleted = 0
        
        vaults_to_index = []
        if vault in ["all", "work"]:
            vaults_to_index.append(("work", Path(self.settings.vault_work_path), Path(self.settings.pdf_work_path)))
        if vault in ["all", "personal"]:
            vaults_to_index.append(("personal", Path(self.settings.vault_personal_path), Path(self.settings.pdf_personal_path)))
        
        for table_name, vault_path, pdf_path in vaults_to_index:
            if self._cancel_requested:
                break
                
            logger.info(f"Incremental index of {table_name} vault...")
            
            table = self.db.open_table(table_name)
            
            # Get existing indexed files with mtime and hash
            try:
                existing = table.search().select(["file_path", "file_hash", "mtime"]).limit(100000).to_list()
                # Dedupe by file_path (multiple chunks per file)
                indexed_files = {}
                for r in existing:
                    fp = r["file_path"]
                    if fp not in indexed_files:
                        indexed_files[fp] = {
                            "file_hash": r["file_hash"],
                            "mtime": r.get("mtime", 0.0)  # Handle legacy records without mtime
                        }
            except Exception as e:
                logger.warning(f"Could not read existing index: {e}")
                indexed_files = {}
            
            # List files on disk (non-blocking) - both Markdown and PDF
            md_files = await self.list_markdown_files(vault_path)
            pdf_files = []
            if self.settings.pdf_enabled and PDF_ENABLED:
                pdf_files = await self.list_pdf_files(pdf_path)
            
            disk_files = {str(f) for f in md_files} | {str(f) for f in pdf_files}
            
            # === DELETION HANDLING ===
            # Find files in index but not on disk
            deleted_files = set(indexed_files.keys()) - disk_files
            if deleted_files:
                logger.info(f"Found {len(deleted_files)} deleted files to remove from index")
                for deleted_path in deleted_files:
                    if self._cancel_requested:
                        break
                    try:
                        table.delete(f'file_path = "{deleted_path}"')
                        total_deleted += 1
                        # Also remove from FTS
                        if self.fts_index:
                            try:
                                self.fts_index.delete_document(deleted_path, table_name)
                            except:
                                pass
                    except Exception as e:
                        logger.warning(f"Failed to delete {deleted_path} from index: {e}")
            
            # === MARKDOWN CHANGE DETECTION ===
            files_checked = 0
            files_skipped_mtime = 0
            files_skipped_hash = 0
            
            for md_file in md_files:
                if self._cancel_requested:
                    logger.info("Indexing cancelled by request")
                    break
                
                file_path_str = str(md_file)
                
                # Get current mtime (fast stat call)
                try:
                    current_mtime = md_file.stat().st_mtime
                except Exception as e:
                    logger.warning(f"Could not stat {md_file}: {e}")
                    continue
                
                # TIER 1: mtime check (fast)
                if file_path_str in indexed_files:
                    indexed_mtime = indexed_files[file_path_str].get("mtime", 0.0)
                    if indexed_mtime and abs(current_mtime - indexed_mtime) < 1.0:
                        # mtime unchanged (within 1 second tolerance) - skip
                        files_skipped_mtime += 1
                        continue
                    
                    # mtime changed - need to check content hash
                    content = await self.read_file(md_file)
                    if content is None:
                        continue
                    
                    # TIER 2: content hash check
                    loop = asyncio.get_event_loop()
                    current_hash = await loop.run_in_executor(
                        _executor,
                        lambda c: hashlib.md5(c.encode()).hexdigest(),
                        content
                    )
                    
                    if current_hash == indexed_files[file_path_str]["file_hash"]:
                        # Content unchanged (mtime was misleading, e.g., touch/copy)
                        # Update mtime in index to avoid re-checking next time
                        try:
                            table.update(
                                where=f'file_path = "{file_path_str}"',
                                values={"mtime": current_mtime}
                            )
                        except:
                            pass  # Non-critical
                        files_skipped_hash += 1
                        continue
                
                # File is new or modified - index it
                count = await self.index_file(md_file, table_name, mtime=current_mtime)
                total_indexed += count
                
                files_checked += 1
                # Yield every 10 files to keep server responsive
                if files_checked % 10 == 0:
                    await asyncio.sleep(0)
            
            # === PDF CHANGE DETECTION ===
            pdf_checked = 0
            pdf_skipped = 0
            
            for pdf_file in pdf_files:
                if self._cancel_requested:
                    logger.info("PDF indexing cancelled by request")
                    break
                
                file_path_str = str(pdf_file)
                
                try:
                    current_mtime = pdf_file.stat().st_mtime
                except Exception as e:
                    logger.warning(f"Could not stat PDF {pdf_file}: {e}")
                    continue
                
                # mtime check for PDFs
                if file_path_str in indexed_files:
                    indexed_mtime = indexed_files[file_path_str].get("mtime", 0.0)
                    if indexed_mtime and abs(current_mtime - indexed_mtime) < 1.0:
                        pdf_skipped += 1
                        continue
                
                # PDF is new or modified - index it
                count = await self.index_pdf_file(pdf_file, table_name, mtime=current_mtime)
                total_indexed += count
                
                pdf_checked += 1
                if pdf_checked % 5 == 0:
                    await asyncio.sleep(0)
            
            logger.info(
                f"{table_name}: md_indexed={files_checked}, md_skipped(mtime)={files_skipped_mtime}, "
                f"md_skipped(hash)={files_skipped_hash}, pdf_indexed={pdf_checked}, pdf_skipped={pdf_skipped}, "
                f"deleted={total_deleted}"
            )
        
        logger.info(f"Incremental index complete: {total_indexed} chunks indexed, {total_deleted} files removed")
        return total_indexed
