from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_DSN: str = "postgresql://postgres:password@localhost:5432/srdb_v3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "gemma3:12b"
    EMBEDDING_MODEL: str = "bge-m3"

    SYSTEM_EMAIL_ADDRESS: str

    class Config:
        env_file = ".env"
        extra = "forbid"

settings = Settings()
