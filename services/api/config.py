"""
Configuration settings for note-rag API
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # API
    api_token: str = "changeme"
    log_level: str = "INFO"
    
    # Ollama (local/default)
    ollama_url: str = "http://ollama:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    
    # GPU Offload (remote Ollama on GPU machine)
    gpu_ollama_url: str = "http://10.10.10.2:11434"
    gpu_ollama_enabled: bool = True
    gpu_wol_mac: str = "60:cf:84:cb:3f:aa"
    gpu_wol_broadcast: str = "10.10.10.255"
    gpu_boot_wait_seconds: int = 5  # n8n webhook already has 40s sleep built in
    gpu_health_timeout_seconds: int = 120
    gpu_auto_shutdown: bool = True  # Shutdown GPU PC after indexing
    gpu_shutdown_url: str = "http://10.10.10.2:8765/shutdown"
    gpu_shutdown_secret: str = "gpu-shutdown-ok"
    gpu_wol_server_url: str = "http://192.168.1.70:9753"  # WoL HTTP server on NAS host
    
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
