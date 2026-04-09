from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.routes import conversation
from backend.database.session import get_db
from backend.auth.logic import login_user
from backend.services.auth_service import create_user

app = FastAPI()
app.include_router(conversation.router)


# -------- REQUEST MODELS --------

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


# -------- REGISTER --------

@app.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    user = create_user(
        db,
        data.username,
        data.email,
        data.password,
        data.role
    )

    return {
        "message": "User created",
        "user_id": str(user.id)
    }


# -------- LOGIN --------

@app.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user, error = login_user(db, data.username, data.password)

    if error:
        return {"error": error}

    return {
        "message": "Login successful",
        "user_id": str(user.id),
        "role": user.role
    }