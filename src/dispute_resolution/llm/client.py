from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from ..config import settings

# LLM for reasoning, decision-making, summarization
llm = ChatOllama(
    base_url=settings.OLLAMA_BASE_URL,  # http://localhost:11434
    model=settings.LLM_MODEL,           # "gemma2:27b"
    temperature=0.0,                    # Deterministic for decisions
    num_ctx=32768,                      # Large context for long email threads
    # Optional: increase if you have GPU memory
    # num_gpu=1,
)

# Embeddings for vector search and storage
embeddings = OllamaEmbeddings(
    base_url=settings.OLLAMA_BASE_URL,
    model=settings.EMBEDDING_MODEL,     # "bge-m3"
)