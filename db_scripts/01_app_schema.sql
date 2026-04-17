-- ================================
-- FILE 1: app_schema.sql
-- ================================
-- FINAL FILE-SYSTEM BASED SCHEMA
-- Policy PDFs are stored in local folder storage (e.g. /policies)
-- Database stores only indexing metadata + chat/business data

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE SCHEMA IF NOT EXISTS app;

-- USERS (single admin enforced)
CREATE TABLE IF NOT EXISTS app.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('Admin','HR','Employee')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS app_one_admin_only_idx
ON app.users ((role))
WHERE role = 'Admin';

-- CONVERSATIONS
CREATE TABLE IF NOT EXISTS app.conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    title VARCHAR(255) DEFAULT 'New Conversation',
    created_at TIMESTAMP DEFAULT NOW()
);

-- MESSAGES (ordered Q/A pairs)
CREATE TABLE IF NOT EXISTS app.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES app.conversations(id) ON DELETE CASCADE,
    sequence_no INT NOT NULL CHECK (sequence_no > 0),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(conversation_id, sequence_no)
);

-- DOCUMENT REGISTRY
-- Files exist physically in local folder storage
-- Example: policies/hr/recruitment_policy.pdf
CREATE TABLE IF NOT EXISTS app.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_type VARCHAR(50) DEFAULT 'pdf',
        checksum VARCHAR(128),
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    last_indexed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- TOOL LOGS
CREATE TABLE IF NOT EXISTS app.tool_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES app.conversations(id) ON DELETE CASCADE,
    tool_name VARCHAR(100) NOT NULL,
    tool_input JSONB,
    tool_output JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- QUERY CACHE
CREATE TABLE IF NOT EXISTS app.query_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES app.users(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    response_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- INDEXES
CREATE INDEX IF NOT EXISTS idx_app_users_username ON app.users(username);
CREATE INDEX IF NOT EXISTS idx_app_conversations_user_id ON app.conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_app_messages_conversation_seq ON app.messages(conversation_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_app_documents_category ON app.documents(category);
CREATE INDEX IF NOT EXISTS idx_app_tool_logs_conversation_id ON app.tool_logs(conversation_id);