import sys
from backend.services.vector_store import get_embedder
from backend.agents.tools.policy_retrieval_tool import _get_document_chunks
from backend.config import settings
print(settings.llm_model)
query = "what is the leave policy?"
embedder = get_embedder()
emb = embedder.encode(query, convert_to_numpy=True).tolist()
chunks = _get_document_chunks(emb, ["general", "leave"], top_k=5)
for i, c in enumerate(chunks):
    print(f"--- Chunk {i} ---")
    print(c['chunk_text'][:200])
