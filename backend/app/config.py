"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database (optional - uses SQLite fallback if PostgreSQL not available)
    database_url: str = "sqlite+aiosqlite:///./papers.db"
    
    # API Keys (optional)
    semantic_scholar_api_key: str | None = None
    unpaywall_email: str = "user@example.com"
    
    # Cache settings
    search_cache_ttl_hours: int = 24
    paper_cache_ttl_days: int = 7
    
    # Search settings
    default_candidates_per_source: int = 100
    top_results_count: int = 20
    
    # Rate limiting
    requests_per_minute: int = 100
    
    # CORS settings
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
