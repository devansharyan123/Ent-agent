# backend/main.py

from backend.database.session import get_db
from backend.services.auth_service import create_user, get_user_by_username, verify_password
from backend.services.rag_service import ask_pipeline, initialize_rag

# Auth imports
from services.auth_service import create_user, get_user_by_username, verify_password

# RAG imports
from services.rag_service import ask_pipeline, initialize_rag
from fastapi import FastAPI, Depends,Request
from sqlalchemy.orm import Session
from uuid import UUID

from backend.routes import conversation
from backend.database.session import get_db
from backend.auth.logic import login_user
from backend.services.auth_service import create_user
from backend.services.agent_service import AgentService
from backend.database.models import User
from backend.database.schemas import UserCreate, UserLogin, AskRequest

app = FastAPI()

# Include routes
app.include_router(conversation.router)

# =========================
# 🚀 STARTUP EVENT
# =========================
@app.on_event("startup")
def startup_event():
    print("🔄 Initializing RAG system...")
    initialize_rag()
    print("✅ RAG Ready")


# =========================
# 👤 REGISTER API
# =========================
@app.post("/register")
def register(
    username: str,
    email: str,
    password: str,
    role: str,
    db: Session = Depends(get_db)
):
    try:
        user = create_user(db, username, email, password, role)

        return {
            "message": "User created successfully",
            "user_id": str(user.id)
        }

    except Exception as e:
        return {"error": str(e)}

# -------- REGISTER --------
@app.post("/register")
def register(request: UserCreate, db: Session = Depends(get_db)):
    user = create_user(
        db,
        request.username,
        request.email,
        request.password,
        request.role
    )

    return {
        "message": "User created",
        "user_id": str(user.id)
    }



# =========================
# 🔐 LOGIN API
# =========================
@app.post("/login")
def login(
    username: str,
    password: str,
    db: Session = Depends(get_db)
):
    user = get_user_by_username(db, username)
async def login(request: Request, db: Session = Depends(get_db)):
    data = await request.json()

    username = data.get("username")
    password = data.get("password")

    user, error = login_user(db, username, password)

    if not user:
        return {"error": "User not found"}

    if not verify_password(password, user.password_hash):
        return {"error": "Invalid password"}

    if not user.is_active:
        return {"error": "User inactive"}

    return {
        "message": "Login successful",
        "user_id": str(user.id),
        "role": user.role
    }


# =========================
# 🧠 ASK API (RAG)
# =========================
@app.post("/ask")
def ask(
    query: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    try:
        # 🔍 Get user role
        user = db.execute(
            "SELECT role FROM app.users WHERE id = :id",
            {"id": user_id}
        ).fetchone()
# -------- ASK AGENT --------
@app.post("/ask")
def ask_agent(request: AskRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == request.user_id).first()

        if not user:
            return {"error": "User not found"}

        role = user[0]

        # 🚀 Run RAG pipeline
        answer = ask_pipeline(role, query)

        return {
            "query": query,
            "role": role,
            "answer": answer
        # Get or create conversation
        conv_id = AgentService.get_or_create_conversation(
            request.user_id,
            request.conversation_id,
            db
        )

        # Execute agent query
        result = AgentService.execute_query(
            request.user_id,
            UUID(conv_id),
            request.question,
            user.role,
            db
        )

        return result

    except Exception as e:
        return {"error": str(e)}


# -------- GET CONVERSATION --------
@app.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: UUID, db: Session = Depends(get_db)):
    try:
        messages = AgentService.get_conversation_history(conversation_id, db)

        return {
            "status": "success",
            "conversation_id": str(conversation_id),
            "messages": messages,
            "total_messages": len(messages)
        }

    except Exception as e:
        return {"error": str(e)}


# =========================
# 🧪 HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {"message": "🚀 Enterprise AI Backend Running"}
# -------- GET DOCUMENTS --------
@app.get("/documents")
def get_documents(user_id: UUID, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return {"error": "User not found"}

        documents = AgentService.get_documents(user.role, db)

        return {
            "status": "success",
            "documents": documents,
            "total_documents": len(documents),
            "user_role": user.role
        }

    except Exception as e:
        return {"error": str(e)}
