from dispute_resolution.llm.client import embeddings


def embed_email(subject: str, body: str) -> list[float]:
    """
    Generate embedding for an email using BGE-M3.
    """
    text = f"Subject: {subject}\n\n{body}"
    return embeddings.embed_query(text)
