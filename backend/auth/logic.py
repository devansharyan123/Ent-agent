from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.auth_service import get_user_by_username, verify_password


async def login_user(db: AsyncSession, username: str, password: str):
    user = await get_user_by_username(db, username)

    if not user:
        return None, "Invalid username or password"

    if not verify_password(password, user.password_hash):
        return None, "Invalid username or password"

    if not user.is_active:
        return None, "User inactive"

    return user, None


def check_role_access(user_role, required_role):
    hierarchy = {
        "Admin": ["Admin", "HR", "Employee"],
        "HR": ["HR", "Employee"],
        "Employee": ["Employee"]
    }

    return required_role in hierarchy.get(user_role, [])
