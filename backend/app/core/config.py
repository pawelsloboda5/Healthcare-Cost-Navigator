"""
Configuration settings for Healthcare Cost Navigator
"""
import os
from typing import Optional

class Settings:
    """Application settings and configuration"""
    
    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:Warmia50587@localhost:5432/healthcare_cost_navigator"
    )
    
    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # API settings
    API_TITLE: str = "Healthcare Cost Navigator"
    API_DESCRIPTION: str = "API for searching hospital costs and getting AI-powered healthcare insights"
    API_VERSION: str = "1.0.0"
    
    # CORS settings
    ALLOWED_ORIGINS: list = ["*"]  # In production, specify actual domains
    
    # Query settings
    DEFAULT_QUERY_LIMIT: int = 20
    MAX_QUERY_LIMIT: int = 100
    
    # Template matching settings
    TEMPLATE_CONFIDENCE_THRESHOLD: float = 0.7
    TEMPLATE_SIMILARITY_THRESHOLD: float = 0.7
    
    # Safety settings
    MAX_SQL_COMPLEXITY: int = 50
    ENABLE_TEMPLATE_LEARNING: bool = True
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __init__(self):
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")

# Global settings instance
settings = Settings()
