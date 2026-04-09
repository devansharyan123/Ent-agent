# Agent Testing Guide

## Prerequisites Checklist

Before testing, ensure:

- [ ] Groq API key is in `backend/.env` (already configured)
- [ ] Database is running and accessible
- [ ] All dependencies are available

## Testing Steps

### Step 1: Verify Imports and Configuration
```bash
cd /home/devansh-aryan/PROG/Capgemini/Ent-agent
python << 'EOF'
import sys
sys.path.insert(0, '.')
print("=" * 60)
print("TESTING IMPORTS AND CONFIGURATION")
print("=" * 60)

try:
    from backend.config import settings
    print("✓ Config module loaded")
    print(f"  - LLM Provider: {settings.llm_provider}")
    print(f"  - LLM Model: {settings.llm_model}")
    print(f"  - API Key set: {bool(settings.groq_api_key)}")
except Exception as e:
    print(f"✗ Config error: {e}")

try:
    from backend.database.session import get_db, engine
    print("✓ Database module loaded")
except Exception as e:
    print(f"✗ Database error: {e}")

try:
    from backend.services.auth_service import create_user
    print("✓ Auth service loaded")
except Exception as e:
    print(f"✗ Auth service error: {e}")

try:
    from backend.agents.tools.retrieval import retrieval_search
    print("✓ Retrieval tool loaded")
except Exception as e:
    print(f"✗ Retrieval tool error: {e}")

try:
    from backend.agents.tools.summarization import summarization_tool
    print("✓ Summarization tool loaded")
except Exception as e:
    print(f"✗ Summarization tool error: {e}")

try:
    from backend.agents.brain import get_agent
    print("✓ Agent brain loaded")
except Exception as e:
    print(f"✗ Agent brain error: {e}")

try:
    from backend.services.agent_service import AgentService
    print("✓ Agent service loaded")
except Exception as e:
    print(f"✗ Agent service error: {e}")

try:
    from backend.main import app
    print("✓ FastAPI app loaded")
except Exception as e:
    print(f"✗ FastAPI app error: {e}")

print("=" * 60)
EOF
```

### Step 2: Start the FastAPI Server
```bash
cd /home/devansh-aryan/PROG/Capgemini/Ent-agent
uvicorn backend.main:app --reload --port 8000
```

The server should start at `http://localhost:8000`

### Step 3: Test Endpoints (in a new terminal)

#### Test 3a: Register a User
```bash
curl -X POST "http://localhost:8000/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "role": "employee"
  }'

# Expected response:
# {"message":"User created","user_id":"<uuid>"}
```

#### Test 3b: Login
```bash
curl -X POST "http://localhost:8000/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }'

# Expected response:
# {"message":"Login successful","user_id":"<uuid>","role":"employee"}
# Save the user_id for next tests
```

#### Test 3c: Get Available Documents
```bash
# Replace <USER_ID> with the user_id from login response
curl -X GET "http://localhost:8000/documents?user_id=<USER_ID>"

# Expected response:
# {"status":"success","documents":[...],"total_documents":N,"user_role":"employee"}
```

#### Test 3d: Ask the Agent a Question
```bash
# Replace <USER_ID> with actual user_id
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<USER_ID>",
    "question": "What is the employee policy?"
  }'

# Expected response:
# {
#   "status": "success",
#   "answer": "Based on the company policies...",
#   "message_id": "<uuid>",
#   "conversation_id": "<uuid>",
#   "sequence_no": 1
# }
# Save the conversation_id
```

#### Test 3e: Get Conversation History
```bash
# Replace <CONVERSATION_ID> with the conversation_id from /ask response
curl -X GET "http://localhost:8000/conversation/<CONVERSATION_ID>?user_id=<USER_ID>"

# Expected response:
# {
#   "status": "success",
#   "conversation_id": "<uuid>",
#   "messages": [
#     {
#       "id": "<uuid>",
#       "question": "What is the employee policy?",
#       "answer": "...",
#       "sequence_no": 1,
#       "created_at": "..."
#     }
#   ],
#   "total_messages": 1
# }
```

## Testing with Python Script

Alternatively, use this Python test script:

```python
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("TESTING AGENT ENDPOINTS")
print("=" * 60)

# Test 1: Register
print("\n1. Testing /register endpoint...")
register_response = requests.post(f"{BASE_URL}/register", json={
    "username": "agent_test_user",
    "email": "agent_test@example.com",
    "password": "testpass123",
    "role": "employee"
})
print(f"Status: {register_response.status_code}")
print(f"Response: {json.dumps(register_response.json(), indent=2)}")
user_id = register_response.json().get("user_id")

# Test 2: Login
print("\n2. Testing /login endpoint...")
login_response = requests.post(f"{BASE_URL}/login", json={
    "username": "agent_test_user",
    "password": "testpass123"
})
print(f"Status: {login_response.status_code}")
print(f"Response: {json.dumps(login_response.json(), indent=2)}")

# Test 3: Get Documents
print("\n3. Testing /documents endpoint...")
docs_response = requests.get(f"{BASE_URL}/documents", params={"user_id": user_id})
print(f"Status: {docs_response.status_code}")
print(f"Response: {json.dumps(docs_response.json(), indent=2)}")

# Test 4: Ask Agent
print("\n4. Testing /ask endpoint...")
ask_response = requests.post(f"{BASE_URL}/ask", json={
    "user_id": user_id,
    "question": "What policies are available?"
})
print(f"Status: {ask_response.status_code}")
print(f"Response: {json.dumps(ask_response.json(), indent=2)}")
conversation_id = ask_response.json().get("conversation_id")

# Test 5: Get Conversation
if conversation_id:
    print(f"\n5. Testing /conversation endpoint...")
    conv_response = requests.get(f"{BASE_URL}/conversation/{conversation_id}", params={"user_id": user_id})
    print(f"Status: {conv_response.status_code}")
    print(f"Response: {json.dumps(conv_response.json(), indent=2)}")

print("\n" + "=" * 60)
print("TESTING COMPLETE")
print("=" * 60)
```

## Expected Database Changes After Testing

After successful testing, check the database:

```sql
-- Check if user was created
SELECT id, username, email, role FROM app.users WHERE username = 'agent_test_user';

-- Check if conversation was created
SELECT id, user_id, created_at FROM app.conversations
WHERE user_id = '<user_id>' LIMIT 1;

-- Check if message was stored
SELECT id, question, answer, sequence_no FROM app.messages
WHERE conversation_id = '<conversation_id>';

-- Check if query was cached
SELECT query, answer, hit_count FROM app.query_cache
WHERE query ILIKE '%policies%' LIMIT 1;
```

## Troubleshooting

### Issue: Agent returns error "Could not generate output"
- **Cause**: Groq API key invalid or API rate limited
- **Solution**:
  1. Verify Groq API key in `backend/.env`
  2. Check Groq dashboard for rate limits
  3. Try a different model from available options

### Issue: "Cannot connect to database"
- **Cause**: PostgreSQL not running or connection string invalid
- **Solution**:
  1. Verify PostgreSQL is running: `pg_isready`
  2. Check database URL in `.env`
  3. Verify firewall/network access

### Issue: "No documents found"
- **Cause**: Vector embeddings not generated for PDFs
- **Solution**:
  1. Run PDF embedding pipeline: `python backend/database/init_db.py`
  2. Populate `vector_store.rag_embeddings` table
  3. Upload PDFs to `/storage/policies/`

### Issue: Agent doesn't remember conversation history
- **Cause**: Conversation history not properly loaded
- **Solution**:
  1. Check that messages are stored in `app.messages` table
  2. Verify `sequence_no` field is incrementing
  3. Check `max_conversation_history` setting (default: 10)

## Next Steps

1. **Implement PDF Embedding Pipeline**
   - Create embeddings for PDFs in `/storage/policies/`
   - Populate `vector_store.rag_embeddings` table
   - Update retrieval tool to use semantic search

2. **Add Vector Search**
   - Replace text pattern matching with pgvector similarity search
   - Update `retrieval.py` to use cosine distance

3. **Implement Caching**
   - Add Redis for distributed caching (optional)
   - Implement cache expiry logic

4. **Add Monitoring/Observability**
   - Integrate LangSmith for tracing
   - Add request logging middleware
   - Create dashboard for agent metrics

5. **Production Deployment**
   - Add authentication tokens (JWT)
   - Implement rate limiting
   - Add request validation
   - Set up error handling and logging
