from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    POSTGRES_DSN: str
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "gemma2:27b"
    EMBEDDING_MODEL: str = "bge-m3"

    class Config:
        env_file = ".env"

settings = Settings()