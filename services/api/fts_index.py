"""
FTS Index - SQLite FTS5 full-text search for note-rag

Provides BM25 keyword search alongside vector search for hybrid retrieval.
"""

import sqlite3
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class FTSIndex:
    """SQLite FTS5 full-text search index."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
        # Ensure parent directory exists
        parent_dir = Path(db_path).parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created FTS directory: {parent_dir}")
            except Exception as e:
                logger.warning(f"Could not create FTS directory {parent_dir}: {e}")
                # Fall back to /tmp
                db_path = "/tmp/fts_index.db"
                self.db_path = db_path
                logger.info(f"Using fallback FTS path: {db_path}")
        
        try:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._init_tables()
        except sqlite3.OperationalError as e:
            logger.warning(f"Could not open FTS at {db_path}: {e}, trying /tmp")
            self.db_path = "/tmp/fts_index.db"
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._init_tables()
    
    def _init_tables(self):
        """Create FTS5 virtual table if not exists."""
        # Main content table (for deduplication)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fts_documents (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE,
                file_hash TEXT,
                title TEXT,
                vault TEXT,
                category TEXT,
                people TEXT,
                date TEXT,
                content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # FTS5 virtual table
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                file_path,
                title,
                content,
                people,
                content='fts_documents',
                content_rowid='id',
                tokenize='porter unicode61 remove_diacritics 1'
            )
        """)
        
        # Triggers to keep FTS in sync
        self.conn.execute("""
            CREATE TRIGGER IF NOT EXISTS fts_documents_ai AFTER INSERT ON fts_documents BEGIN
                INSERT INTO documents_fts(rowid, file_path, title, content, people)
                VALUES (new.id, new.file_path, new.title, new.content, new.people);
            END
        """)
        
        self.conn.execute("""
            CREATE TRIGGER IF NOT EXISTS fts_documents_ad AFTER DELETE ON fts_documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, file_path, title, content, people)
                VALUES('delete', old.id, old.file_path, old.title, old.content, old.people);
            END
        """)
        
        self.conn.execute("""
            CREATE TRIGGER IF NOT EXISTS fts_documents_au AFTER UPDATE ON fts_documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, file_path, title, content, people)
                VALUES('delete', old.id, old.file_path, old.title, old.content, old.people);
                INSERT INTO documents_fts(rowid, file_path, title, content, people)
                VALUES (new.id, new.file_path, new.title, new.content, new.people);
            END
        """)
        
        self.conn.commit()
        logger.info(f"FTS index initialized at {self.db_path}")
    
    def upsert_document(
        self,
        file_path: str,
        title: str,
        content: str,
        vault: str,
        category: str = "",
        people: List[str] = None,
        date: str = None
    ) -> bool:
        """Insert or update a document in the FTS index."""
        file_hash = hashlib.md5(content.encode()).hexdigest()
        people_str = ", ".join(people or [])
        
        try:
            self.conn.execute("""
                INSERT INTO fts_documents (file_path, file_hash, title, vault, category, people, date, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    title = excluded.title,
                    vault = excluded.vault,
                    category = excluded.category,
                    people = excluded.people,
                    date = excluded.date,
                    content = excluded.content,
                    updated_at = CURRENT_TIMESTAMP
            """, (file_path, file_hash, title, vault, category, people_str, date, content))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error upserting document {file_path}: {e}")
            return False
    
    def _escape_fts_query(self, query: str) -> str:
        """
        Escape query for FTS5 to prevent syntax errors.
        FTS5 interprets special chars: ':' (column), '-' (NOT), '*' (prefix), etc.
        Always wrap in double quotes to treat as literal phrase search.
        """
        # Always quote the query to prevent FTS5 syntax interpretation
        # This treats the entire query as a literal phrase
        escaped = query.replace('"', '""')
        return f'"{escaped}"'
    
    def search(
        self,
        query: str,
        vault: str = "all",
        limit: int = 30,
        person: Optional[str] = None
    ) -> List[Dict]:
        """
        BM25 full-text search.
        
        Returns list of results with:
        - file_path, title, vault, category, people, date
        - snippet: highlighted excerpt
        - score: BM25 relevance score (higher = better)
        """
        # Escape query for FTS5 syntax
        fts_query = self._escape_fts_query(query)
        
        # Build WHERE clause
        where_parts = ["documents_fts MATCH ?"]
        params = [fts_query]
        
        if vault != "all":
            where_parts.append("d.vault = ?")
            params.append(vault)
        
        if person:
            where_parts.append("d.people LIKE ?")
            params.append(f"%{person}%")
        
        where_clause = " AND ".join(where_parts)
        params.append(limit)
        
        try:
            cursor = self.conn.execute(f"""
                SELECT 
                    d.file_path,
                    d.title,
                    d.vault,
                    d.category,
                    d.people,
                    d.date,
                    snippet(documents_fts, 2, '<mark>', '</mark>', '...', 64) as snippet,
                    bm25(documents_fts, 1.0, 2.0, 1.0, 0.5) as score
                FROM documents_fts
                JOIN fts_documents d ON d.id = documents_fts.rowid
                WHERE {where_clause}
                ORDER BY score
                LIMIT ?
            """, params)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "file_path": row["file_path"],
                    "title": row["title"],
                    "vault": row["vault"],
                    "category": row["category"],
                    "people": row["people"].split(", ") if row["people"] else [],
                    "date": row["date"],
                    "snippet": row["snippet"],
                    "score": abs(row["score"]),  # BM25 returns negative scores
                    "source": "bm25"
                })
            
            return results
            
        except sqlite3.OperationalError as e:
            # Handle invalid FTS query syntax
            if "fts5: syntax error" in str(e):
                logger.warning(f"Invalid FTS query: {query}")
                return []
            raise
    
    def get_document_count(self, vault: str = "all") -> int:
        """Get number of indexed documents."""
        if vault == "all":
            cursor = self.conn.execute("SELECT COUNT(*) FROM fts_documents")
        else:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM fts_documents WHERE vault = ?", 
                (vault,)
            )
        return cursor.fetchone()[0]
    
    def delete_document(self, file_path: str, vault: str = None) -> bool:
        """Remove a document from the FTS index."""
        try:
            if vault:
                self.conn.execute(
                    "DELETE FROM fts_documents WHERE file_path = ? AND vault = ?",
                    (file_path, vault)
                )
            else:
                self.conn.execute(
                    "DELETE FROM fts_documents WHERE file_path = ?",
                    (file_path,)
                )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting document {file_path}: {e}")
            return False
    
    def clear_vault(self, vault: str):
        """Remove all documents from a vault."""
        self.conn.execute("DELETE FROM fts_documents WHERE vault = ?", (vault,))
        self.conn.commit()
    
    def close(self):
        """Close the database connection."""
        self.conn.close()
