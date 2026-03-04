"""
Configuration settings for Recall API
Simplified: BM25 (FTS5) + Gemini Flash only. No Ollama, no vectors.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # API
    api_token: str = "changeme"
    log_level: str = "INFO"
    
    # Vaults (Markdown)
    vault_work_path: str = "/data/obsidian/work"
    vault_personal_path: str = "/data/obsidian/personal"
    excluded_folders: str = "personal/finance"
    
    # PDFs
    pdf_work_path: str = "/data/pdfs/work"
    pdf_personal_path: str = "/data/pdfs/personal"
    pdf_enabled: bool = True
    
    # FTS Indexing
    chunk_size: int = 500
    chunk_overlap: int = 50
    transcript_chunk_multiplier: float = 2.5
    fts_db_path: str = "/data/lancedb/fts_index.db"  # Keep same path for compatibility
    
    # Noise filtering for transcripts
    filter_transcript_noise: bool = True
    transcript_noise_phrases: str = "Yeah.|Yep.|Mhmm.|Mm-hmm.|Uh-huh.|Right.|Correct.|Okay.|OK.|Sure.|Got it.|I see.|Exactly.|Absolutely.|Definitely.|Perfect.|Great.|Nice.|Cool.|Alright.|All right.|Um.|Uh.|Like,|You know,|I mean,|So,|Well,|Actually,|Basically,|Obviously,|Honestly,|Literally,"
    
    # Search
    default_search_limit: int = 10
    max_context_chunks: int = 5
    
    # Source boosting
    boost_daily_notes: bool = True
    daily_notes_boost: float = 1.15
    transcript_penalty: float = 0.90
    
    class Config:
        env_file = ".env"
    
    @property
    def excluded_folders_list(self) -> List[str]:
        return [f.strip() for f in self.excluded_folders.split(",") if f.strip()]


settings = Settings()
