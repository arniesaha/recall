"""
Recall Indexer — FTS-only (simplified)
Indexes Obsidian vault markdown files into SQLite FTS5.
No embeddings, no vectors, no GPU needed.
"""

import os
import re
import logging
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Callable

from config import Settings
from fts_index import FTSIndex

logger = logging.getLogger(__name__)


class Indexer:
    """FTS-only indexer for Obsidian vault files."""
    
    def __init__(self, settings: Settings, fts_index: FTSIndex):
        self.settings = settings
        self.fts_index = fts_index
        self._cancel_requested = False
        
        # Vault paths
        self.vault_paths = {
            "work": Path(settings.vault_work_path),
            "personal": Path(settings.vault_personal_path),
        }
        
        # Noise phrases for transcript cleaning
        self.noise_phrases = []
        if settings.filter_transcript_noise:
            self.noise_phrases = [
                p.strip() for p in settings.transcript_noise_phrases.split("|") if p.strip()
            ]
    
    def request_cancel(self):
        self._cancel_requested = True
    
    def _is_cancelled(self) -> bool:
        return self._cancel_requested
    
    def _extract_metadata(self, content: str, file_path: Path) -> dict:
        """Extract metadata from markdown content."""
        title = file_path.stem
        date = None
        people = []
        category = ""
        
        # Extract date from filename (YYYY-MM-DD prefix)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', file_path.stem)
        if date_match:
            date = date_match.group(1)
        
        # Extract category from parent folder
        parts = file_path.parts
        for part in parts:
            if part in ("daily-notes", "Granola", "people", "projects", "agent-memory"):
                category = part
                break
        
        # Clean title
        if date:
            title = re.sub(r'^\d{4}-\d{2}-\d{2}[-_\s]*', '', title).strip()
        if not title:
            title = file_path.stem
        
        return {
            "title": title,
            "date": date,
            "people": people,
            "category": category,
        }
    
    def _clean_transcript(self, content: str) -> str:
        """Remove noise phrases from transcript content."""
        if not self.noise_phrases:
            return content
        for phrase in self.noise_phrases:
            content = content.replace(phrase, "")
        # Clean up extra whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()
    
    def _chunk_content(self, content: str, is_transcript: bool = False) -> List[str]:
        """Split content into chunks for FTS indexing."""
        chunk_size = self.settings.chunk_size
        if is_transcript:
            chunk_size = int(chunk_size * self.settings.transcript_chunk_multiplier)
        
        overlap = self.settings.chunk_overlap
        words = content.split()
        chunks = []
        
        i = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunks.append(" ".join(chunk_words))
            i += chunk_size - overlap
        
        return chunks if chunks else [content]
    
    async def full_reindex(self, vault: str = "all", progress_callback: Optional[Callable] = None) -> int:
        """Full reindex of all vault files into FTS."""
        self._cancel_requested = False
        total_indexed = 0
        
        vaults_to_index = []
        if vault in ("all", "work"):
            vaults_to_index.append(("work", self.vault_paths["work"]))
        if vault in ("all", "personal"):
            vaults_to_index.append(("personal", self.vault_paths["personal"]))
        
        # Collect all files
        all_files = []
        for vault_name, vault_path in vaults_to_index:
            if not vault_path.exists():
                logger.warning(f"Vault path does not exist: {vault_path}")
                continue
            for root, dirs, files in os.walk(vault_path):
                # Skip hidden dirs
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for fname in files:
                    if fname.endswith('.md') and not fname.startswith('.'):
                        fpath = Path(root) / fname
                        all_files.append((vault_name, fpath))
        
        total = len(all_files)
        logger.info(f"Full reindex: {total} files across {len(vaults_to_index)} vaults")
        
        # Clear existing FTS data
        for vault_name, _ in vaults_to_index:
            try:
                self.fts_index.clear_vault(vault_name)
            except Exception as e:
                logger.warning(f"Could not clear FTS for {vault_name}: {e}")
        
        for i, (vault_name, fpath) in enumerate(all_files):
            if self._is_cancelled():
                logger.info("Indexing cancelled")
                break
            
            try:
                count = await self._index_file(fpath, vault_name)
                total_indexed += count
                
                if progress_callback and i % 10 == 0:
                    await progress_callback(i + 1, total, str(fpath.name))
                    
            except Exception as e:
                logger.error(f"Error indexing {fpath}: {e}")
        
        if progress_callback:
            await progress_callback(total, total, "Complete")
        
        logger.info(f"Full reindex complete: {total_indexed} chunks from {total} files")
        return total_indexed
    
    async def incremental_index(self, vault: str = "all", progress_callback: Optional[Callable] = None) -> int:
        """Incremental index — only re-index modified files."""
        self._cancel_requested = False
        total_indexed = 0
        
        vaults_to_index = []
        if vault in ("all", "work"):
            vaults_to_index.append(("work", self.vault_paths["work"]))
        if vault in ("all", "personal"):
            vaults_to_index.append(("personal", self.vault_paths["personal"]))
        
        # Get existing indexed file mtimes from FTS
        indexed_files = {}
        try:
            indexed_files = self.fts_index.get_indexed_mtimes()
        except Exception:
            pass
        
        files_to_index = []
        for vault_name, vault_path in vaults_to_index:
            if not vault_path.exists():
                continue
            for root, dirs, files in os.walk(vault_path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for fname in files:
                    if fname.endswith('.md') and not fname.startswith('.'):
                        fpath = Path(root) / fname
                        mtime = os.path.getmtime(fpath)
                        fpath_str = str(fpath)
                        
                        # Only index if new or modified
                        if fpath_str not in indexed_files or mtime > indexed_files[fpath_str]:
                            files_to_index.append((vault_name, fpath))
        
        total = len(files_to_index)
        logger.info(f"Incremental index: {total} new/modified files")
        
        for i, (vault_name, fpath) in enumerate(files_to_index):
            if self._is_cancelled():
                break
            try:
                count = await self._index_file(fpath, vault_name)
                total_indexed += count
                if progress_callback and i % 10 == 0:
                    await progress_callback(i + 1, total, str(fpath.name))
            except Exception as e:
                logger.error(f"Error indexing {fpath}: {e}")
        
        if progress_callback:
            await progress_callback(total, total, "Complete")
        
        logger.info(f"Incremental index complete: {total_indexed} chunks from {total} files")
        return total_indexed
    
    async def _index_file(self, file_path: Path, vault_name: str) -> int:
        """Index a single file into FTS."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Cannot read {file_path}: {e}")
            return 0
        
        if not content.strip():
            return 0
        
        metadata = self._extract_metadata(content, file_path)
        
        # Clean transcripts
        is_transcript = "transcript" in str(file_path).lower()
        if is_transcript:
            content = self._clean_transcript(content)
        
        # Chunk and index
        chunks = self._chunk_content(content, is_transcript)
        
        for chunk in chunks:
            try:
                self.fts_index.upsert_document(
                    file_path=str(file_path),
                    title=metadata["title"],
                    content=chunk,
                    vault=vault_name,
                    category=metadata["category"],
                    people=metadata["people"],
                    date=metadata["date"],
                )
            except Exception as e:
                logger.error(f"FTS upsert error for {file_path}: {e}")
        
        return len(chunks)
