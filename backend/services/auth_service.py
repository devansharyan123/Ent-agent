# backend/services/auth_service.py

from sqlalchemy.orm import Session
from backend.database import models
import bcrypt


def hash_password(password: str):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str):
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_user(db: Session, username, email, password, role):
    hashed = hash_password(password)

    user = models.User(
        username=username,
        email=email,
        password_hash=hashed,
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username):
    return db.query(models.User).filter(models.User.username == username).first()