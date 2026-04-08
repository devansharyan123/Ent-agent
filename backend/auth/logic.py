# backend/auth/logic.py

from sqlalchemy.orm import Session
from services.auth_service import get_user_by_username, verify_password


def login_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)

    if not user:
        return None, "User not found"

    if not verify_password(password, user.password_hash):
        return None, "Invalid password"

    if not user.is_active:
        return None, "User inactive"

    return user, None


def check_role_access(user_role, required_role):
    hierarchy = {
        "Admin": ["Admin", "HR", "Employee"],
        "HR": ["HR", "Employee"],
        "Employee": ["Employee"]
    }

    return required_role in hierarchy[user_role]