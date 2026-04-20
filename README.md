
# Enterprise Knowledge Assistant (Agentic AI + RAG)

## Overview

This project implements an Enterprise Knowledge Assistant that enables users to interact with organizational knowledge in a conversational manner. The system combines Agentic AI with Retrieval-Augmented Generation (RAG) to provide accurate, context-aware, and role-based responses.

It is designed to handle enterprise documents, maintain conversation history, and dynamically decide how to respond using a tool-based architecture.

---

## Architecture

The system is structured into multiple layers:

### Presentation Layer
- Streamlit-based user interface
- Chat interface for user interaction
- Login and registration functionality

### Application Layer
- FastAPI backend
- Handles API requests, routing, and business logic

### Intelligence Layer
- LangChain-based agent
- Responsible for decision-making and tool orchestration

### Data Layer
- PostgreSQL for users, conversations, and memory
- Vector database for embeddings and similarity search

### Observability Layer
- LangSmith for tracing, monitoring, and debugging

---

## Features

- Conversational interface for querying enterprise data
- Role-based access control (Admin, HR, Employee)
- Context-aware responses using conversation history
- Document-based question answering using RAG
- Source attribution for responses
- Built-in audit and traceability for responses

---

## RAG Pipeline

The system implements a Retrieval-Augmented Generation pipeline:

- Documents are uploaded and processed
- Text is split into chunks
- Embeddings are generated
- Stored in a vector database
- Relevant chunks are retrieved based on user queries
- Responses are generated using LLM with retrieved context

---

## Tools

The agent dynamically selects from the following tools:

- Policy Retrieval Tool  
  Retrieves answers from documents using RAG

- Summarization Tool  
  Generates concise summaries from documents

- External Knowledge Tool  
  Fetches additional information using LLM

- Comparison Tool  
  Compares two policies and highlights differences

- Recommendation Tool  
  Suggests relevant documents based on user queries


- Audit and Source Attribution Tool  
  Ensures transparency and traceability of AI-generated responses by identifying source documents, tracking contributing content chunks, and providing explainability for the generated answer


---

## Authentication and Roles

A simple authentication system is implemented using PostgreSQL.

Supported roles:
- Admin: Full access
- HR: Access to HR and general policies
- Employee: Limited access

Responses are filtered based on user role to ensure controlled access to information.

---

## Long-Term Memory

The system maintains persistent conversation history using PostgreSQL. This enables:

- Retrieval of past conversations
- Context-aware responses
- Session continuity

---

## Observability

LangSmith is used to track:

- Agent decision flow
- Tool usage
- LLM interactions
- Errors and performance

This helps in debugging and optimizing the system.

---

## Testing

The project includes unit tests covering:

- Role-based access control
- Retrieval logic
- Each tool is tested independently
- Source validation
- Edge cases and negative scenarios
- Database and API failures

Testing is implemented using Pytest with mocking for external dependencies.

---

## Docker Setup

### Build the image
```bash
docker build -t ent-agent .
````

### Run the container

```bash
docker run -p 8000:8000 ent-agent
```

### Using Docker Compose

```bash
docker-compose up --build
```

---

## Installation and Setup

### Clone the repository

```bash
git clone https://github.com/devansharyan123/Ent-agent.git
cd Ent-agent
```

### Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=ent-agent

DATABASE_URL=postgresql://user:password@localhost:5432/project_db
LLM_MODEL=llama-3.1-8b-instant
AGENT_TEMPERATURE=0.7
GROQ_API_KEY=your_key

VECTOR_STORE_DIMENSION=1536
LLM_PROVIDER=groq
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

```

---

## Running the Application

### Start backend

```bash
uvicorn backend.main:app --reload
```

### Start frontend

```bash
streamlit run frontend/app.py
```

---

## Project Flow

User query is processed as follows:

1. User submits a query
2. Agent analyzes intent
3. Appropriate tool is selected
4. If required, relevant documents are retrieved
5. LLM generates response using context
6. Response is returned with sources

---

## Project Structure

```
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

---

## Future Improvements

* User feedback loop for improving response quality
* Multi-tenant support
* Fine-tuned embeddings
* Enhanced UI/UX
* Real-time document updates with automatic re-indexing

---

## Authors

Asmi Krishnatrey, Bhavya Kateja, Devansh Aryan, Pallavi K Kamath, Shanthu Kumar M, Vinaya Shree R

---

## Acknowledgements

LangChain
Groq
FastAPI
Streamlit
PostgreSQL

```

