This `context.md` file serves as the "source of truth" for your team. It combines your current file structure with the technical decisions and database architecture we just finalized.

You should place this file in your project root (`Ent-agent/context.md`) so any team member (or AI assistant) can quickly understand the project state.

---

### `context.md`

## 1. Project Overview
[cite_start]**Enterprise Knowledge Assistant** is an agentic AI system designed to interact with organizational knowledge via a conversational interface[cite: 2, 3]. [cite_start]It utilizes a RAG (Retrieval-Augmented Generation) approach to provide role-based, context-aware responses from internal documents[cite: 5, 42].

## 2. Technical Stack
* [cite_start]**Frontend:** Streamlit [cite: 12]
* [cite_start]**Backend:** FastAPI [cite: 17]
* [cite_start]**Orchestration:** LangChain Agent [cite: 21]
* **Database:** PostgreSQL with `pgvector` extension
* [cite_start]**Observability:** LangSmith [cite: 28]

## 3. File Structure
```text
Ent-agent/
├── backend/                # Application & Intelligence Layer
│   ├── agents/             # Agent logic & Tool definitions
│   │   └── tools/          # (Retrieval, Summarization, Comparison, etc.)
│   ├── auth/               # User authentication & RBAC logic
│   ├── database/           # DB Connection, Models, & Init scripts
│   ├── services/           # PDF Processing & Vector logic
│   └── main.py             # Entry point
├── db_scripts/             # SQL Schema files
│   ├── app_schema.sql      # Schema for business/chat data
│   └── vector_schema.sql   # Schema for pgvector data
├── frontend/               # Streamlit UI
├── storage/                # Local policy PDF storage
│   └── policies/           # Subfolders: /hr, /general
├── tests/                  # Unit & Integration tests
├── .env                    # Local environment variables
└── context.md              # Project documentation (this file)
```

## 4. Database Architecture
The system uses a single PostgreSQL instance with two distinct schemas:

### A. `app` Schema (Business Logic)
* **`users`**: Stores credentials and roles (Admin, HR, Employee). Enforces a **single Admin** limit.
* **`conversations` & `messages`**: Manages chat history. Messages use a `sequence_no` for exact replay order.
* **`documents`**: A registry for local files. Stores `file_path`, `checksum` (for change detection), and `category`.
* **`tool_logs`**: Logs agent actions for observability.

### B. `vector_store` Schema (RAG Logic)
* **`document_chunks`**: Stores text fragments linked to `app.documents`.
* **`rag_embeddings`**: Stores `VECTOR(1536)` data using `pgvector` for similarity search.

## 5. Implementation Notes
* **Source of Truth:** PDFs are stored on the local file system; the DB only stores metadata and paths.
* **Initialization:** Run `backend/database/init_db.py` to sync the schema. SQL files are idempotent (use `IF NOT EXISTS`).
* **Extension Requirements:** The `pgvector` extension must be enabled by a superuser (`CREATE EXTENSION IF NOT EXISTS vector;`) before the `vector_store` schema is created.
* [cite_start]**Role-Based Access:** The system must filter document retrieval based on the user's role defined in `app.users`[cite: 42, 43].

## 6. Current Status & Next Steps
1.  **DONE:** Database architecture, Schemas, and Directory structure.
2.  **IN PROGRESS:** SQLAlchemy models (`models.py`) and PDF processing service (`processor.py`).
3.  **UPCOMING:** LangChain agent tool integration and RAG retrieval API development.

---

### For Your Team:
> **Team Lead Note:** Every member should update their `.env` file with the shared PostgreSQL IP. When adding new tools, create a new file in `backend/agents/tools/` and document its behavior in the `app.tool_logs` table.