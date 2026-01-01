from dispute_resolution.services.embedding_service import embed_email
vec = embed_email("Test subject", "Test body")
print(len(vec))