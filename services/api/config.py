"""
Configuration settings for note-rag API
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # API
    api_token: str = "changeme"
    log_level: str = "INFO"
    
    # Ollama
    ollama_url: str = "http://ollama:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    
    # LanceDB
    lancedb_path: str = "/data/lancedb"
    
    # Vaults (Markdown)
    vault_work_path: str = "/data/obsidian/work"
    vault_personal_path: str = "/data/obsidian/personal"
    excluded_folders: str = "personal/finance"
    
    # PDFs
    pdf_work_path: str = "/data/pdfs/work"
    pdf_personal_path: str = "/data/pdfs/personal"
    pdf_enabled: bool = True
    
    # Indexing
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # Search
    default_search_limit: int = 10
    similarity_threshold: float = 0.7
    
    # RAG
    max_context_chunks: int = 5
    
    class Config:
        env_file = ".env"
    
    @property
    def excluded_folders_list(self) -> List[str]:
        return [f.strip() for f in self.excluded_folders.split(",") if f.strip()]


settings = Settings()
