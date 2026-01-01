from langchain_ollama import ChatOllama, OllamaEmbeddings
from dispute_resolution.config import settings

# LLM for reasoning, decisions, summaries
llm = ChatOllama(
    base_url=settings.OLLAMA_BASE_URL,   # ✅ supported
    model=settings.LLM_MODEL,            # e.g. "gemma2:27b"
    temperature=0.0,
    num_ctx=32768,
)

# Embeddings
embeddings = OllamaEmbeddings(
    base_url=settings.OLLAMA_BASE_URL,
    model=settings.EMBEDDING_MODEL,      # e.g. "bge-m3"
)
