# backend/main.py

from backend.database.session import get_db
from backend.services.auth_service import create_user, get_user_by_username, verify_password
from backend.services.rag_service import ask_pipeline, initialize_rag

# Auth imports
from services.auth_service import create_user, get_user_by_username, verify_password

# RAG imports
from services.rag_service import ask_pipeline, initialize_rag

app = FastAPI()


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

        if not user:
            return {"error": "User not found"}

        role = user[0]

        # 🚀 Run RAG pipeline
        answer = ask_pipeline(role, query)

        return {
            "query": query,
            "role": role,
            "answer": answer
        }

    except Exception as e:
        return {"error": str(e)}


# =========================
# 🧪 HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {"message": "🚀 Enterprise AI Backend Running"}