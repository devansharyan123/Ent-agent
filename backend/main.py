# backend/main.py

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from auth.logic import login_user
from services.auth_service import create_user

app = FastAPI()


@app.post("/register")
def register(username: str, email: str, password: str, role: str, db: Session = Depends(get_db)):
    user = create_user(db, username, email, password, role)
    return {"message": "User created", "user_id": str(user.id)}


@app.post("/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    user, error = login_user(db, username, password)

    if error:
        return {"error": error}

    return {
        "message": "Login successful",
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role
    }


@app.post("/logout")
def logout():
    """Logout endpoint - frontend handles session clearing"""
    return {"message": "Logout successful"}