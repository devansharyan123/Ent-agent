-- ================================
-- FILE 2: vector_schema.sql
-- ================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS vector_store;

-- DOCUMENT CHUNKS
-- Chunks are generated from files in the policies folder
CREATE TABLE IF NOT EXISTS vector_store.document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES app.documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL CHECK (chunk_index >= 0),
    chunk_text TEXT NOT NULL,
    page_number INT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);
look the embeddings 
-- EMBEDDINGS
CREATE TABLE IF NOT EXISTS vector_store.rag_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id UUID NOT NULL UNIQUE REFERENCES vector_store.document_chunks(id) ON DELETE CASCADE,
    embedding VECTOR(1536) NOT NULL,
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',
    created_at TIMESTAMP DEFAULT NOW()
);

-- INDEXES
CREATE INDEX IF NOT EXISTS idx_vector_chunks_document_id
ON vector_store.document_chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_vector_embeddings_vector
ON vector_store.rag_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);