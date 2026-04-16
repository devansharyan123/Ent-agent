<<<<<<< HEAD
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chat_models import ChatOpenAI
from backend.services.rag_loader import load_documents

from backend.services.rag_loader import load_documents

# 🔹 Embedding model
embedding = HuggingFaceEmbeddings()

# 🔹 Vector DB (RAM)
vectordb = Chroma(embedding_function=embedding)

# 🔹 LLM
llm = ChatOpenAI()

# 🔐 ROLE FILTER
def filter_docs_by_role(user_role, docs):
=======
from backend.database.session import SessionLocal
from backend.database.models import DocumentChunk, RagEmbedding, Document
from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer

ROLE_PERMISSIONS = {
    "admin": ["admin", "hr", "general"],
    "hr": ["hr", "general"],
    "employee": ["general"]
}
>>>>>>> c93a7a2d68f9e88bdc32de05e6b86c3eaa302fcc

_embedder = None

<<<<<<< HEAD
    return [
        d for d in docs
        if d.metadata.get("category") in allowed[user_role]
    ]


# 📦 LOAD + CHUNK + STORE (RUN ON STARTUP)
def initialize_rag():

    documents = load_documents()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )

    chunks = splitter.split_documents(documents)

    vectordb.add_documents(chunks)

    print("✅ RAG Initialized")


# 🔍 QUERY
def query_rag(user_role, query):

    results = vectordb.similarity_search(query, k=5)

    filtered = filter_docs_by_role(user_role, results)

    if not filtered:
        return None, "Access denied or no relevant data."

    context = "\n".join([doc.page_content for doc in filtered])

    return context, None


# 🧠 FINAL PIPELINE
def ask_pipeline(user_role, query):

    context, error = query_rag(user_role, query)

    if error:
        return error

    prompt = f"""
    Answer ONLY from the context.

    Context:
    {context}

    Question:
    {query}
    """

    response = llm.invoke(prompt)

    return response.content
=======

def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-mpnet-base-v2")
    return _embedder


def retrieve_with_role_filter(query: str, user_role: str, top_k: int = 5):
    """
    1. Embed the query
    2. Search pgvector for similar chunks
    3. Filter by role permissions
    """
    user_role_normalized = str(user_role or "").strip().lower()
    allowed_categories = ROLE_PERMISSIONS.get(user_role_normalized, [])
    if not allowed_categories:
        return []

    db = SessionLocal()
    try:

        embedder = get_embedder()
        query_embedding = embedder.encode(query)

        embedding_count = db.query(RagEmbedding).count()
        if embedding_count == 0:
            return []
        results = db.query(
            DocumentChunk.chunk_text,
            Document.file_name,
            Document.category
        ).join(
            RagEmbedding, RagEmbedding.chunk_id == DocumentChunk.id
        ).join(
            Document, Document.id == DocumentChunk.document_id
        ).filter(
            Document.category.in_(allowed_categories),
            Document.is_active == True
        ).order_by(
            RagEmbedding.embedding.op('<->')(query_embedding)
        ).limit(top_k).all()

        formatted_results = [
            {
                "text": r[0],
                "source": r[1],
                "category": r[2]
            }
            for r in results
        ]

        return formatted_results

    except Exception as e:
        print(f"Error in retrieve_with_role_filter: {str(e)}")
        return []
    finally:
        db.close()
>>>>>>> c93a7a2d68f9e88bdc32de05e6b86c3eaa302fcc
