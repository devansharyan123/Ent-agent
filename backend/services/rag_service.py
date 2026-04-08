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

    allowed = {
        "Admin": ["admin", "hr", "general"],
        "HR": ["hr", "general"],
        "Employee": ["general"]
    }

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